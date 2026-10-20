"""
Menjalankan beberapa pekerja berdampingan, masing-masing dengan browser sendiri.

KENAPA BROWSER TERPISAH, BUKAN TAB TERPISAH
    Sesi login portal menempel pada PROFIL browser, bukan pada tab. Beberapa tab
    dalam satu browser berarti satu akun mengerjakan beberapa peserta sekaligus -
    dan bagaimana portal menanggapinya belum pernah kita buktikan. Profil
    terpisah membuat tiap pekerja bisa memakai akun puskesmas yang berbeda,
    yang di mata portal sama saja dengan dua petugas bekerja bersamaan.

    Satu folder profil tidak boleh dipakai dua browser sekaligus. Chrome akan
    menolak, atau lebih buruk, merusak profilnya.

YANG DIJAGA DI SINI
    * Pembagian data TIDAK BOLEH bertindih. Peserta yang sama dikerjakan dua
      pekerja berarti pendaftaran ganda di portal, dan itu tidak bisa dibatalkan.
    * Tiap pekerja menulis berkas hasilnya sendiri.
    * Login tiap pekerja dilakukan manusia, satu per satu (ada captcha).

YANG TIDAK BISA DIPARALELKAN
    `config.TAHAP` dan `config.KATEGORI` adalah variabel modul. Semua pekerja
    dalam satu perintah memakai alur dan kategori yang SAMA - itu memang selalu
    begitu dalam pemakaian nyata, jadi keduanya ditetapkan sekali sebelum
    pekerja dijalankan dan tidak disentuh lagi sesudahnya.
"""
from __future__ import annotations

import threading

import config
import layanan
import pekerjaan
import pendaftaran
import portal
import run as terminal
from browser import buka_browser, sudah_login


def bagi_rata(batch: list, jumlah: int) -> list[list]:
    """
    Bagi peserta ke beberapa pekerja, berselang-seling.

    Berselang-seling (1,4,7 / 2,5,8 / 3,6,9), bukan dipotong blok, supaya
    pekerjaan berat dan ringan tersebar merata: berkas peserta biasanya
    terurut, dan satu blok bisa saja seluruhnya peserta yang sudah dilayani
    sementara blok lain seluruhnya peserta baru.
    """
    jumlah = max(1, min(jumlah, len(batch) or 1))
    bagian = [[] for _ in range(jumlah)]
    for i, orang in enumerate(batch):
        bagian[i % jumlah].append(orang)
    return [b for b in bagian if b]


class Pekerja:
    """Satu browser + satu bagian data + satu berkas hasil."""

    def __init__(self, nomor: int, batch: list, kerjakan=None, total: int = 0) -> None:
        self.nomor = nomor
        self.batch = batch
        # Alur tanpa berkas (Tatalaksana Gigi) memberi fungsinya sendiri:
        # kerjakan(halaman, kerja, catatan). Bawaannya batch dari CSV.
        self.kerjakan = kerjakan
        self.kerja = pekerjaan.Pekerjaan()
        self.kerja.total = total or len(batch)
        self.profil = config.PROFIL_BROWSER.parent / f"{config.PROFIL_BROWSER.name}-{nomor}"
        self.utas: threading.Thread | None = None

    # -------------------------------------------------------------- jalannya
    def _jalan(self) -> None:
        k = self.kerja
        try:
            k.lapor(f"Pekerja {self.nomor}: {k.total} peserta · profil "
                    f"{self.profil.name}")
            with buka_browser(profil=self.profil) as (_konteks, halaman):
                halaman.goto(config.PORTAL, wait_until="domcontentloaded")
                halaman.wait_for_timeout(2500)

                if not sudah_login(halaman):
                    k.keadaan = "menunggu-login"
                    k.pesan = (f"Login akun untuk pekerja {self.nomor} di jendela "
                               "browsernya, lalu tekan tombol di bawah.")
                    k.lapor("Menunggu login…")
                    k.tanda_login.wait()
                    halaman.wait_for_timeout(1500)

                if not sudah_login(halaman):
                    k.keadaan = "gagal"
                    k.pesan = "Sepertinya belum login."
                    return

                k.keadaan = "berjalan"
                k.pesan = ""
                # Dibaca SESUDAH login terbukti, sekali saja: sebelum login
                # kepala halaman belum memuat nama siapa pun.
                k.akun = portal.nama_akun(halaman)
                k.lapor(f"Login terdeteksi{' sebagai ' + k.akun if k.akun else ''}. "
                        "Mulai bekerja.")

                catatan = terminal.CatatanHasil(tanda=f"-p{self.nomor}")
                k.berkas_hasil = catatan.tujuan.name
                jejak: list = []
                jejak_layanan: list = []
                try:
                    if self.kerjakan:
                        self.kerjakan(halaman, k, catatan)
                    else:
                        pekerjaan.kerjakan_batch(halaman, self.batch, k, catatan,
                                                 jejak, jejak_layanan)
                finally:
                    catatan.tutup()
                    # Nama berkas jejak dibedakan juga, kalau tidak pekerja
                    # terakhir menimpa rekaman pekerja lainnya.
                    pendaftaran.simpan_jejak(jejak, f"-p{self.nomor}")
                    layanan.simpan_jejak(jejak_layanan, f"-p{self.nomor}")

            if k.keadaan != "gagal":
                k.keadaan = "selesai"
                k.pesan = k.pesan or "Selesai."
        except Exception as e:
            k.keadaan = "gagal"
            k.pesan = f"{type(e).__name__}: {' '.join(str(e).split())[:250]}"
            k.lapor(k.pesan)

    def mulai(self) -> None:
        self.utas = threading.Thread(target=self._jalan, daemon=True)
        self.utas.start()

    def hidup(self) -> bool:
        return bool(self.utas and self.utas.is_alive())


def siapkan(batch: list, jumlah: int) -> list[Pekerja]:
    """Bagi batch lalu siapkan pekerjanya. Belum dijalankan."""
    return [Pekerja(i, bagian) for i, bagian in enumerate(bagi_rata(batch, jumlah), start=1)]


def _nomor_baris(hasil: dict):
    """Kunci urut: nomor baris CSV. Yang tak bernomor ditaruh paling belakang."""
    nomor = hasil.get("baris")
    try:
        return (0, int(nomor))
    except (TypeError, ValueError):
        return (1, 0)


def ringkas(daftar: list[Pekerja]) -> dict:
    """Gabungan keadaan semua pekerja, untuk ditampilkan aplikasi."""
    semua = [p.kerja for p in daftar]
    # "selesai" hanya bila SEMUA pekerja sudah berhenti. Bawaan yang salah di
    # sini pernah menghentikan pemantauan halaman: sesaat sesudah dimulai
    # kedua pekerja masih berkeadaan "siap" (sedang membuka browser), tidak ada
    # yang cocok dengan syarat mana pun, dan nilai bawaannya "selesai" membuat
    # halaman mengira pekerjaan sudah beres lalu berhenti menanya selamanya.
    if any(k.keadaan == "berjalan" for k in semua):
        keadaan = "berjalan"
    elif any(k.keadaan == "menunggu-login" for k in semua):
        keadaan = "menunggu-login"
    elif any(k.keadaan == "siap" for k in semua):
        keadaan = "berjalan"           # browsernya sedang dibuka
    elif semua and all(k.keadaan == "gagal" for k in semua):
        keadaan = "gagal"
    else:
        keadaan = "selesai"
    return {
        "keadaan": keadaan,
        "total": sum(k.total for k in semua),
        "selesai": sum(k.selesai for k in semua),
        # Diurutkan menurut nomor baris CSV, bukan urutan selesainya.
        # Data dibagi BERSELANG-SELING (1,3,5 ke pekerja 1; 2,4,6 ke pekerja 2),
        # jadi menggabung apa adanya menghasilkan 1,3,5,...,2,4,6 - tabelnya
        # terbaca acak dan berkas Excel-nya ikut acak. Diurutkan di sini, satu
        # tempat, supaya tabel dan ekspor tidak mungkin berbeda urutan.
        "hasil": sorted((b for k in semua for b in k.hasil), key=_nomor_baris),
        "pekerja": [{
            "nomor": p.nomor,
            "keadaan": p.kerja.keadaan,
            "pesan": p.kerja.pesan,
            "total": p.kerja.total,
            "sudah": p.kerja.selesai,
            "berkas": p.kerja.berkas_hasil,
            "akun": p.kerja.akun,
            "catatan": p.kerja.catatan[-40:],
        } for p in daftar],
    }
