"""
Penjalan utama — proses satu batch peserta.

Cara pakai:
    python run.py

Atur di config.py:
    BARIS_AWAL, JUMLAH_DATA   -> batch mana yang dikerjakan
    MODE_UJI = True           -> berhenti sebelum "Daftarkan" (tidak mencatat data)

Catatan penting: JANGAN menutup jendela browser selama batch berjalan.
Sesi login portal tidak bisa dipakai ulang oleh proses baru.
"""
from __future__ import annotations

import csv
from datetime import datetime

import config
import layanan
import pekerjaan
import pendaftaran
import peserta
from browser import buka_browser, simpan_gambar, sudah_login


JUDUL_HASIL = ["baris_csv", "nik", "nama", "status", "keterangan", "tiket", "waktu"]


class CatatanHasil:
    """
    Penulis CSV hasil yang menyimpan SETIAP peserta begitu selesai.

    Dulu seluruh hasil baru ditulis setelah batch usai. Kalau batch panjang
    berhenti di tengah � browser tertutup, listrik mati, kesalahan tak terduga �
    catatan peserta yang sudah terlanjur diproses di portal ikut hilang, dan
    tidak ada cara mengetahui sampai mana pekerjaannya.
    """

    def __init__(self, tanda: str = "") -> None:
        config.siapkan_folder()
        stempel = datetime.now().strftime("%Y%m%d-%H%M%S")
        # `tanda` membedakan berkas antar pekerja. Stempel waktunya hanya
        # sampai detik, jadi dua pekerja yang mulai bersamaan akan menulis ke
        # berkas yang sama - dan yang satu menimpa yang lain tanpa suara.
        self.tujuan = config.HASIL / f"hasil-{stempel}{tanda}.csv"
        self._berkas = self.tujuan.open("w", newline="", encoding="utf-8-sig")
        self._tulis = csv.writer(self._berkas)
        self._tulis.writerow(JUDUL_HASIL)
        self._berkas.flush()

    def tambah(self, b: dict) -> None:
        self._tulis.writerow([b.get("baris"), b.get("nik"), b.get("nama"), b.get("status"),
                              b.get("keterangan"), b.get("tiket"), b.get("waktu", "")])
        self._berkas.flush()      # langsung ke disk, bukan menunggu buffer penuh

    def tutup(self) -> None:
        try:
            self._berkas.close()
        except Exception:
            pass


def urai_nomor(teks: str) -> list[int]:
    """
    Ubah tulisan pilihan baris jadi daftar nomor.

    Menerima "1089", "1089-1092", "1089,1095", atau campurannya.
    Nomor ganda dibuang dan urutannya dirapikan supaya pemrosesan tetap
    mengikuti urutan CSV.
    """
    nomor: set[int] = set()
    for bagian in teks.replace(";", ",").split(","):
        bagian = bagian.strip()
        if not bagian:
            continue
        if "-" in bagian:
            awal, _, akhir = bagian.partition("-")
            try:
                a, b = int(awal.strip()), int(akhir.strip())
            except ValueError:
                continue
            nomor.update(range(min(a, b), max(a, b) + 1))
        else:
            try:
                nomor.add(int(bagian))
            except ValueError:
                continue
    return sorted(nomor)


# Status yang berarti "tidak perlu diulang".
#   tuntas          -> seluruh layanan sudah ditutup
#   sudah_pelayanan -> portal menolak karena peserta memang sudah dilayani
#   ckg_umum        -> sama, dan popupnya menyebut layanannya "CKG Umum":
#                      murid ini sudah diperiksa lewat jalur umum, jadi di CKG
#                      Sekolah memang tidak ada lagi yang bisa dikerjakan.
#                      Tanpa ini ia diulang tiap jalan, sekitar semenit sekali,
#                      dan hasilnya akan selalu sama.
#   sekolah_berbeda -> popupnya menyebut SEKOLAH LAIN: muridnya sudah selesai
#   kelas_berbeda      diperiksa, hanya terdaftar di sekolah/kelas yang bukan
#                      seperti di CSV. Mengulangnya tidak mengubah apa pun -
#                      yang perlu diperbaiki datanya, bukan jalannya.
# Status lain (gagal, error, layanan_sebagian, tanpa_tiket) SENGAJA tidak
# masuk daftar: itu pekerjaan yang belum tuntas dan memang harus diulang.
#   ckg_sekolah       -> popupnya menyebut layanannya "CKG Sekolah": orangnya
#                        sudah diperiksa, hanya lewat jalur sekolah.
#   puskesmas_berbeda -> diperiksa PUSKESMAS LAIN. Catatannya milik mereka;
#                        mengulangnya di sini tidak akan pernah berhasil.
SELESAI = {"tuntas", "sudah_pelayanan", "ckg_umum",
           "sekolah_berbeda", "kelas_berbeda",
           "ckg_sekolah", "puskesmas_berbeda"}


def sudah_dikerjakan() -> tuple[set[str], dict[str, int]]:
    """
    Kumpulkan NIK yang sudah selesai dari SEMUA CSV hasil sebelumnya.

    Dipakai agar batch panjang yang putus di tengah bisa dijalankan ulang
    begitu saja: peserta yang sudah beres dilewati sendiri, tanpa kamu perlu
    membaca CSV lalu menghitung baris mana yang belum.
    """
    selesai: set[str] = set()
    rekap: dict[str, int] = {}
    if not config.HASIL.exists():
        return selesai, rekap
    for berkas in sorted(config.HASIL.glob("hasil-*.csv")):
        try:
            isi = berkas.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        except Exception:
            continue
        for baris in csv.DictReader(isi):
            status = (baris.get("status") or "").strip()
            nik = (baris.get("nik") or "").strip()
            if not nik:
                continue
            rekap[status] = rekap.get(status, 0) + 1
            if status in SELESAI:
                selesai.add(nik)
    return selesai, rekap


def ditolak_sebelumnya() -> set[str]:
    """
    NIK yang jawaban TERAKHIR portal atasnya `tidak_valid`.

    Di dalam satu jalan status ini memang sudah tidak diulang (lihat
    `pekerjaan.GAGAL_SEMENTARA`), tapi menjalankan ulang rentang yang sama
    mengirimnya lagi - dan portal menolak lagi dengan kalimat yang sama.
    Permintaan pengguna 13 Sep: data tidak valid jangan diulang.

    Yang dihitung status TERAKHIR per NIK, bukan "pernah ditolak": orang yang
    dulu ditolak lalu berhasil sesudah datanya dibetulkan tidak boleh ikut
    tercatat ditolak. Berkas hasil diurutkan menurut namanya, dan namanya
    memuat tanggal-jam, jadi urutannya memang urutan waktu.
    """
    terakhir: dict[str, str] = {}
    if not config.HASIL.exists():
        return set()
    for berkas in sorted(config.HASIL.glob("hasil-*.csv")):
        try:
            isi = berkas.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        except Exception:
            continue
        for baris in csv.DictReader(isi):
            nik = (baris.get("nik") or "").strip()
            if nik:
                terakhir[nik] = (baris.get("status") or "").strip()
    return {nik for nik, status in terakhir.items() if status == "tidak_valid"}


def pilah_yang_dilewati(batch: list) -> tuple[list, int, int]:
    """
    Sisakan peserta yang masih perlu dikerjakan. (sisa, n_selesai, n_ditolak)

    Dua alasan melewati dihitung TERPISAH, sebab artinya berlawanan: yang
    selesai sudah beres, yang ditolak justru perlu datanya dibetulkan. Kabar
    "dilewati - sudah selesai sebelumnya" untuk keduanya menyesatkan.
    """
    sisa = buang_yang_selesai(batch)
    n_selesai = len(batch) - len(sisa)
    n_ditolak = 0
    if not config.ULANG_TIDAK_VALID:
        ditolak = ditolak_sebelumnya()
        if ditolak:
            tetap = [p for p in sisa if p.kunci not in ditolak]
            n_ditolak = len(sisa) - len(tetap)
            sisa = tetap
            if n_ditolak:
                print(f"         {n_ditolak} dari batch ini dilewati karena sebelumnya "
                      "ditolak portal (tidak_valid)")
    return sisa, n_selesai, n_ditolak


def buang_yang_selesai(batch: list) -> list:
    """Sisakan peserta yang memang masih perlu dikerjakan."""
    if not config.LEWATI_SUDAH_SELESAI:
        return batch
    selesai, rekap = sudah_dikerjakan()
    if not selesai:
        return batch
    # `kunci`, bukan `nik`: bayi tanpa NIK semuanya ber-NIK kosong, dan
    # menyamakan mereka lewat kolom itu membuat satu bayi yang sudah
    # selesai MELEWATKAN SELURUH bayi lain di berkas yang sama.
    sisa = [p for p in batch if p.kunci not in selesai]
    dilewati = len(batch) - len(sisa)
    print(f"Riwayat: {len(selesai)} peserta sudah selesai pada run sebelumnya "
          f"({', '.join(f'{k}={v}' for k, v in sorted(rekap.items()))})")
    if dilewati:
        print(f"         {dilewati} dari batch ini dilewati karena sudah selesai")
    return sisa


def tanya_batch(semua: list) -> list:
    """
    Tanyakan baris mana yang mau diproses.

    Ditanyakan setelah login supaya tidak perlu mengubah config.py tiap kali
    ganti peserta. Menekan Enter berarti memakai BARIS_AWAL/JUMLAH_DATA.
    """
    tersedia = {p.baris_csv for p in semua}
    print(f"Data    : {len(semua)} peserta (baris {min(tersedia)}..{max(tersedia)})")
    jawab = input("Nomor data yang diinput [mis. 1089 / 1089-1092 / 1089,1095] "
                  f"(Enter = {config.BARIS_AWAL} x{config.JUMLAH_DATA}): ").strip()
    if not jawab:
        return peserta.ambil_batch(semua, config.BARIS_AWAL, config.JUMLAH_DATA)

    diminta = urai_nomor(jawab)
    if not diminta:
        print("  (tidak terbaca — memakai pengaturan config)")
        return peserta.ambil_batch(semua, config.BARIS_AWAL, config.JUMLAH_DATA)

    hilang = [n for n in diminta if n not in tersedia]
    if hilang:
        print(f"  [PERHATIAN] tidak ada di CSV: {hilang}")
    return [p for p in semua if p.baris_csv in set(diminta)]


def main() -> int:
    # Login online: versi terminal pun wajib masuk - kalau tidak, jalankan.bat
    # menjadi jalan pintas yang melewati persetujuan admin.
    import akun_online
    if akun_online.aktif() and not akun_online.masuk_terminal():
        print("Tidak bisa melanjutkan tanpa akun yang disetujui.")
        return 1
    print("=" * 66)
    print("CKG Dewasa/Lansia — Playwright")
    print("MODE UJI (tidak mendaftarkan sungguhan)" if config.MODE_UJI else "MODE SUNGGUHAN")
    print("=" * 66)

    if config.BERKAS_PENGATURAN.exists():
        print(f"Pengaturan dibaca dari {config.BERKAS_PENGATURAN.name}")
    for catatan in config.CATATAN_PENGATURAN:
        print(f"  [PERHATIAN] pengaturan.txt {catatan}")

    semua = peserta.baca_csv()
    print(f"\nCSV    : {len(semua)} peserta di {config.CSV_PESERTA.name}")
    print(f"Tahap  : {config.TAHAP}"
          f" | lewati yang sudah selesai: {'ya' if config.LEWATI_SUDAH_SELESAI else 'tidak'}")
    if not semua:
        print("\n[BERHENTI] CSV kosong.")
        return 1

    hasil: list[dict] = []
    jejak: list = []
    jejak_layanan: list = []

    with buka_browser() as (konteks, halaman):
        halaman.goto(config.PORTAL, wait_until="domcontentloaded")
        halaman.wait_for_timeout(2500)

        if not sudah_login(halaman):
            print("\n>> Silakan LOGIN manual di jendela browser, lalu tekan Enter di sini.")
            input()
            halaman.wait_for_timeout(1500)
        if not sudah_login(halaman):
            print("\n[BERHENTI] belum login.")
            return 2
        print("Login  : OK\n")

        batch = buang_yang_selesai(tanya_batch(semua))
        if not batch:
            print("\n[BERHENTI] tidak ada peserta yang perlu dikerjakan "
                  "(semua sudah selesai, atau pilihan kosong).")
            return 1
        print(f"\nAkan diproses {len(batch)} peserta:")
        for p in batch:
            print(f"  baris {p.baris_csv:>5}  {p.nama} ({p.nik})")
        print()

        catatan = CatatanHasil()
        print(f"Hasil ditulis berjalan ke: {catatan.tujuan}\n")

        # Inti pemrosesan ada di pekerjaan.py, dipakai bersama aplikasi
        # (server.py) supaya alurnya tidak bercabang jadi dua salinan.
        kerja = pekerjaan.Pekerjaan()
        pekerjaan.kerjakan_batch(halaman, batch, kerja, catatan, jejak, jejak_layanan)
        hasil.extend(kerja.hasil)
        for baris_log in kerja.catatan:
            print("  " + baris_log)
        if kerja.pesan:
            print(f"\n[BERHENTI] {kerja.pesan}")

        catatan.tutup()
        peta = pendaftaran.simpan_jejak(jejak)
        peta2 = layanan.simpan_jejak(jejak_layanan)
        print(f"\nHasil  : {catatan.tujuan}")
        print(f"Struktur pendaftaran: {peta}")
        print(f"Struktur layanan    : {peta2}")
        print("\nTekan Enter untuk menutup browser.")
        input()

    print("\nRingkasan:")
    for r in hasil:
        print(f"  baris {r['baris']:>3}  {r['status']:<16} {r['nama'][:28]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
