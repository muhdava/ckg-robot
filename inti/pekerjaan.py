"""
Inti pemrosesan satu batch, terpisah dari cara menjalankannya.

`run.py` (terminal) dan `server.py` (aplikasi) memakai fungsi yang SAMA di sini,
supaya tidak ada dua salinan alur yang perlahan berbeda perilakunya.

Bedanya cuma cara berkomunikasi:
  * terminal  -> mencetak ke layar, menunggu Enter
  * aplikasi  -> memanggil `lapor()` dan menunggu `tanda_login`
"""
from __future__ import annotations

import re
import threading
import time
from datetime import datetime

import config
import layanan
import pendaftaran
import peserta
import portal
import sekolah
from browser import simpan_gambar


class Pekerjaan:
    """
    Satu batch yang sedang berjalan, beserta keadaannya.

    Dipakai aplikasi untuk menampilkan kemajuan tanpa perlu tahu isi alurnya,
    dan untuk menghentikan batch di tengah jalan.
    """

    def __init__(self) -> None:
        self.keadaan = "siap"        # siap | menunggu-login | berjalan | selesai | gagal
        self.pesan = ""
        self.catatan: list[str] = []      # baris log, terbaru di bawah
        self.hasil: list[dict] = []
        self.total = 0
        self.selesai = 0
        self.berkas_hasil = ""
        self.akun = ""            # nama akun portal yang dipakai pekerja ini
        self.minta_berhenti = False
        self.tanda_login = threading.Event()
        self._kunci = threading.Lock()

    # ------------------------------------------------------------- pelaporan
    def lapor(self, teks: str) -> None:
        with self._kunci:
            self.catatan.append(f"{datetime.now():%H:%M:%S}  {teks}")
            del self.catatan[:-400]        # cukup 400 baris terakhir

    def ringkasan(self) -> dict:
        with self._kunci:
            return {
                "keadaan": self.keadaan,
                "pesan": self.pesan,
                "total": self.total,
                "selesai": self.selesai,
                "berkas_hasil": self.berkas_hasil,
                "catatan": self.catatan[-120:],
                "hasil": self.hasil,
            }


def kategori_sekolah(orang) -> bool:
    """
    Apakah peserta ini dikerjakan lewat alur CKG Sekolah.

    Bawaannya MENGIKUTI DATA (`kategori = auto`), sehingga berkas dan alur tidak
    mungkin bertentangan. Pengaturan hanya dipakai bila sengaja dipaksa.
    """
    pilihan = config.KATEGORI.strip().lower()
    if pilihan == "sekolah":
        return True
    # Balita memakai alur pendaftaran dewasa, jadi di sini ia "bukan sekolah".
    if pilihan in ("dewasa", "balita"):
        return False
    return bool(getattr(orang, "dari_sekolah", False))


def _sebutan(orang) -> str:
    return f"baris {orang.baris_csv} · {orang.nama}"


# Status yang berarti "portalnya sedang bermasalah", bukan "datanya salah".
# HANYA ini yang diulang: mengulang `tidak_valid` atau `tidak_ditemukan` cuma
# membuang waktu, sebab jawabannya akan sama persis berapa kali pun dicoba.
GAGAL_SEMENTARA = {"error", "gagal", "gagal_mulai", "gagal_konfirmasi",
                   "gagal_detail", "tanpa_tiket", "layanan_sebagian",
                   # Daftar pilihan yang terbuka kosong juga kerusakan portal,
                   # dan memuat ulang halamannya kerap membuatnya terisi lagi.
                   "daftar_kosong"}

# Jejak yang membuktikan peserta SUDAH sampai di daftar layanan. Sesudah titik
# itu, mengulang dari awal bukan cuma boros - MERUSAK: pendaftarannya diulang,
# portal menjawab "sudah menerima layanan", dan pada alur Pendaftaran->Selesai
# peserta yang sebenarnya tinggal disapu malah tercatat `sudah_pelayanan`.
_SUDAH_DI_LAYANAN = ("daftar layanan:", "form terisi:", "pelayanan tab:",
                     "buka detail via:", "'Mulai Pemeriksaan'",
                     "tanggal pemeriksaan:")


def _sampai_daftar_layanan(halaman, r: dict) -> bool:
    """Benar bila peserta ini sudah pernah masuk daftar layanan."""
    try:
        if "detail-pemeriksaan" in (halaman.url or ""):
            return True
    except Exception:
        pass
    ket = r.get("keterangan", "") if isinstance(r, dict) else ""
    return any(x in ket for x in _SUDAH_DI_LAYANAN)


def _ulangi_dari_layanan(halaman, orang, r: dict, sekolahan: bool,
                         jejak_layanan: list, percobaan: int = 2) -> None:
    """
    Ulangi HANYA bagian pelayanannya - pendaftarannya jangan disentuh lagi.

    USAHANYA MENINGKAT TIAP PERCOBAAN, tidak mengulang hal yang sama.
    Versi pertama selalu menyapu ULANG DI HALAMAN YANG SAMA, dan hasil 3 Sep
    membuktikan itu sia-sia: pada tiga murid, DELAPAN form
    "Pelayanan oleh Nakes" gagal dengan sebab yang sama persis - "form tidak
    ter-render" - di ketiga percobaan, dan percobaan ke-2 dan ke-3 mencatat
    "form terisi: 0". Halaman yang rusak disapu tiga kali tetap rusak.

    Jadi sekarang:
      percobaan 2 -> MUAT ULANG halaman detailnya, baru sapu. Form yang tidak
                     ter-render hampir selalu soal render, dan itulah obatnya.
      percobaan 3+ -> keluar dan MASUK LAGI lewat halaman pelayanan, sehingga
                     seluruh keadaan halaman dibangun dari nol.
    Sapuan hanya mengisi yang MASIH KOSONG, jadi mengulanginya tetap aman.
    """
    try:
        di_detail = "detail-pemeriksaan" in (halaman.url or "")
    except Exception:
        di_detail = False

    if di_detail and percobaan <= 2:
        r["keterangan"] = (r.get("keterangan", "")
                           + " | diulang: muat ulang halaman detail lalu sapu")
        try:
            halaman.reload(wait_until="domcontentloaded")
            portal.tunggu_siap(halaman, portal.js_dan(portal.JS_TIDAK_MEMUAT,
                                                      portal.ADA_BARIS_LAYANAN),
                               8_000, "daftar layanan sesudah muat ulang")
        except Exception as e:
            r["keterangan"] += f" | muat ulang gagal ({type(e).__name__})"
        layanan.petakan_layanan(halaman, r, jejak_layanan)
        layanan.sweep_layanan(halaman, orang, r, jejak_layanan)
        return

    r["keterangan"] = (r.get("keterangan", "")
                       + " | diulang: masuk lagi lewat halaman pelayanan")
    (sekolah.pelayanan_saja if sekolahan else layanan.pelayanan_saja)(
        halaman, orang, r, jejak_layanan)

    # BUKTI DARI PERCOBAAN SEBELUMNYA TIDAK DIBUANG. Percobaan ulang yang tidak
    # menemukan peserta bukan bantahan atas percobaan yang sudah menemukannya
    # di tab "Selesai Pemeriksaan", atau atas popup portal yang menyebut ia
    # sudah diperiksa. Pengguna sendiri menetapkan (7 Sep): ada di tab Selesai
    # berarti datanya sudah diinput puskesmas kita.
    if r.get("status") == "tidak_ditemukan":
        ket = r.get("keterangan", "")
        # Tulisannya beda antar alur: "pelayanan tab: Selesai Pemeriksaan"
        # (sekolah), "tab: ..." dan "tab (sudah terbuka): ..." (dewasa).
        if (re.search(r"tab[^|]*:\s*Selesai Pemeriksaan", ket)
                or r.get("portal_dilayani")):
            r["keterangan"] = ket + (" | percobaan sebelumnya sudah menemukannya"
                                     " SELESAI diperiksa - itu yang dipakai,"
                                     " bukan 'tidak ketemu' percobaan ulang")
            r["status"] = "sudah_pelayanan"


# Ciri galat JARINGAN, bukan galat portal. Dikumpulkan dari galat yang
# benar-benar muncul di catatan: "net::ERR_INTERNET_DISCONNECTED" saat internet
# putus, dan "Page.goto: Timeout 45000ms" saat jaringannya hidup tapi merangkak.
_GALAT_JARINGAN = re.compile(
    r"net::ERR_|ERR_INTERNET_DISCONNECTED|ERR_NAME_NOT_RESOLVED|ERR_CONNECTION"
    r"|ERR_NETWORK|ERR_TIMED_OUT|ERR_PROXY|ERR_ADDRESS|ERR_SSL"
    r"|Page" + chr(92) + r".goto: Timeout", re.I)


def _galat_jaringan(r: dict) -> bool:
    """Benar bila kegagalannya soal koneksi, bukan soal portal atau data."""
    return bool(_GALAT_JARINGAN.search((r or {}).get("keterangan", "")))


def _tunggu_jaringan(halaman, kerja) -> None:
    """
    Beri jeda sebelum mencoba lagi ketika yang putus adalah JARINGAN.

    Galat jaringan tidak sembuh dalam sepersekian detik. Tanpa jeda, ketiga
    percobaan habis dalam hitungan detik dan pesertanya tercatat "error" -
    lalu peserta BERIKUTNYA mengalami hal yang sama, satu demi satu. Pada
    3 Sep tiga murid berturut-turut hangus dalam 6 detik hanya karena
    internet putus sesaat.

    Ditunggu sepotong-sepotong supaya tombol Berhenti tetap menyahut, dan
    diakhiri lebih awal bila browser sudah melaporkan dirinya daring lagi.
    """
    jeda = max(0, int(getattr(config, "JEDA_JARINGAN", 30)))
    if not jeda:
        return
    kerja.lapor(f"    galat jaringan - menunggu {jeda} detik sebelum mencoba lagi")
    sisa = jeda
    daring_semula = _daring(halaman)
    while sisa > 0 and not kerja.minta_berhenti:
        try:
            halaman.wait_for_timeout(2_000)
        except Exception:
            time.sleep(2)
        sisa -= 2
        # Pulih lebih cepat: kalau tadinya putus dan sekarang tersambung lagi,
        # tidak ada gunanya menghabiskan sisa jeda.
        if not daring_semula and _daring(halaman):
            kerja.lapor(f"    jaringan tersambung lagi setelah {jeda - sisa} detik")
            return
    if not _daring(halaman):
        kerja.lapor("    jaringan MASIH terputus menurut browser")


def _daring(halaman) -> bool:
    """Apa kata browser tentang koneksinya. Petunjuk, bukan jaminan."""
    try:
        return bool(halaman.evaluate("() => navigator.onLine"))
    except Exception:
        return True


def _bersihkan_halaman(halaman, kerja) -> None:
    """
    Kembalikan halaman ke keadaan bisa dipakai sebelum percobaan berikutnya.

    Kegagalan biasanya meninggalkan sesuatu di layar - modal pemilih yang macet,
    popup galat, dialog yang tak tertutup - dan benda-benda itu akan menjatuhkan
    percobaan berikutnya dengan sebab yang sama. Mengulang tanpa membersihkan
    berarti mengulang kegagalan yang sama tiga kali.
    """
    try:
        portal.tutup_modal(halaman)
        pesan = portal.tutup_popup_galat(halaman)
        if pesan:
            kerja.lapor(f"    popup galat ditutup sebelum diulang: {pesan}")
        halaman.wait_for_timeout(1200)
    except Exception:
        pass


def _lanjut_ke_pelayanan(halaman, orang, r: dict, jejak_layanan: list) -> None:
    """
    Dewasa/lansia sesudah terdaftar: LANGSUNG ke halaman pelayanan.

    KHUSUS DEWASA/LANSIA. Sempat dipakai juga untuk murid, lalu diralat
    pengguna di hari yang sama (29 Sep): CKG Sekolah MASIH meminta konfirmasi
    hadir. Murid kembali lewat `sekolah.penuh`, persis seperti sebelumnya.

    Sejak akhir Sep 2026 portal tidak lagi meminta "Konfirmasi Hadir" -
    peserta yang tiketnya terbit langsung muncul di halaman pelayanan, tab
    Belum Pemeriksaan (keterangan pengguna, 29 Sep). Jalur lama justru
    memutar: buka halaman pendaftaran, cari NIK, cari tombol konfirmasi yang
    kini tidak ada, baru jatuh ke halaman pelayanan sebagai cadangan.

    JALUR LAMA TETAP DISIMPAN SEBAGAI CADANGAN. Bila peserta ternyata tidak
    ada di halaman pelayanan - misalnya portal kembali meminta konfirmasi
    hadir untuk sebagian peserta - barulah dicoba lewat konfirmasi hadir.
    Syaratnya: ia belum pernah sampai di daftar layanan, supaya pemeriksaan
    yang sudah berjalan tidak dimulai ulang.

    """
    r["keterangan"] += " | langsung ke halaman pelayanan (tanpa konfirmasi hadir)"
    layanan.pelayanan_saja(halaman, orang, r, jejak_layanan)
    if (r.get("status") in ("tidak_ditemukan", "gagal_mulai")
            and not _sampai_daftar_layanan(halaman, r)):
        r["keterangan"] += " | tak ada di pelayanan - dicoba lewat konfirmasi hadir"
        r["status"] = "belum"
        layanan.penuh(halaman, orang, r, jejak_layanan)


def _vonis_popup_bila_tak_ada(halaman, r: dict) -> None:
    """
    Peserta yang kata portal SUDAH DILAYANI tapi tak ada di halaman pelayanan.

    Halaman pelayanan hanya memuat "pelayanan hari ini atau riwayat yang
    belum selesai dicatat" - begitu bunyi keterangan portal di kepalanya.
    Pemeriksaan yang sudah tuntas berbulan-bulan lalu TIDAK tampil di ketiga
    tabnya. Pada 30 Sep tiga peserta divonis `tidak_ditemukan` padahal
    popup pendaftaran mereka sendiri menyebut tanggal pemeriksaannya: 21 Feb,
    23 Apr, dan 17 Jun 2026. Mencari lebih lama tidak akan menemukan apa pun.

    Keterangan portal itulah yang dipakai - aturan yang sama sudah berlaku di
    alur sekolah (`sekolah.penuh`, vonis paling akhir). Puskesmas pemeriksanya
    dibandingkan ULANG di sini, dari halaman pelayanan yang tak tertutup popup:
    Seorang peserta diperiksa puskesmas lain, tapi pembandingan saat popup
    masih terbuka gagal membaca nama puskesmas kita dan ia lolos sebagai
    `sudah_pelayanan`.
    """
    if r.get("status") != "tidak_ditemukan":
        return
    ket = r.get("keterangan", "")
    m = re.search(r"sudah menerima \(pe\)layanan \(([^)]*)\)", ket)
    if not m:
        return
    rinci = m.group(1)
    layanan_ = re.search(r"layanan: ([^,)]+)", rinci)
    pemeriksa = re.search(r"puskesmas pemeriksa: ([^,)]+)", rinci)
    tanggal = re.search(r"tanggal pemeriksaan: ([^,)]+)", rinci)
    if layanan_ and re.search(r"ckg\s*sekolah", layanan_.group(1), re.I):
        r["status"] = "ckg_sekolah"
    elif pemeriksa and portal.puskesmas_lain(halaman, pemeriksa.group(1)):
        r["status"] = "puskesmas_berbeda"
    else:
        r["status"] = "sudah_pelayanan"
    r["keterangan"] += (" | tak tampil di halaman pelayanan karena pemeriksaannya"
                        f" sudah lama selesai ({tanggal.group(1) if tanggal else 'tanggal tak disebut'})"
                        f" - dipakai keterangan portal: {r['status']}")


def _kerjakan_satu(halaman, orang, sekolahan: bool, kerja,
                   jejak: list, jejak_layanan: list) -> dict:
    """Satu kali percobaan penuh untuk satu peserta."""
    r = None
    # NIK YANG BUKAN 16 ANGKA TIDAK DIKIRIM. Portal mengunci "Selanjutnya"
    # selama kolom NIK belum 16 digit, jadi macro hanya menunggu "halaman 2"
    # yang tak pernah terbuka - 3 percobaan terbuang per peserta (SMPN 136,
    # NIK rusak notasi ilmiah "3,17204E+15" yang terbaca 8 digit). Peserta
    # tanpa NIK (balita "Tidak punya NIK") tidak tersentuh: NIK-nya kosong.
    # NAMA TANPA SATU HURUF PUN ("94", "11,3") = kolom nama di sumbernya
    # tertimpa angka. Portal menolaknya diam-diam seperti NIK rusak (SMPN 136,
    # 7 Okt: lima murid, masing-masing tiga percobaan terbuang).
    # Murid sekolah TIDAK ditolak di sini: alur sekolah mengambil identitasnya
    # lewat "Cek NIK" (lihat sekolah.daftar_murid).
    if not sekolahan and not any(ch.isalpha() for ch in (orang.nama or "")):
        return pendaftaran.HasilDaftar(
            nama=orang.nama, nik=orang.kunci, baris=orang.baris_csv, status="tidak_valid",
            keterangan=f"nama {orang.nama!r} tidak berisi huruf - tidak dikirim ke portal. "
                       "Isi nama murid yang benar dulu.",
            tiket="")
    nik = (orang.nik or "").strip()
    if nik and (len(nik) != 16 or not nik.isdigit()):
        return pendaftaran.HasilDaftar(
            nama=orang.nama, nik=orang.kunci, baris=orang.baris_csv, status="tidak_valid",
            keterangan=f"NIK {nik!r} bukan 16 angka - tidak dikirim ke portal "
                       "(tombol Selanjutnya terkunci). Betulkan NIK-nya dulu.",
            tiket="")
    try:
        if config.TAHAP in ("konfirmasi", "layanan", "isi",
                            "pelayanan", "pelayanan_sapu"):
            # Peserta sudah punya tiket -> langsung ke tahap layanan.
            r = pendaftaran.HasilDaftar(nama=orang.nama, nik=orang.kunci,
                                        baris=orang.baris_csv, status="belum",
                                        keterangan="", tiket="")
        elif sekolahan:
            r = sekolah.daftar_murid(halaman, orang, jejak)
        else:
            r = pendaftaran.daftar_peserta(halaman, orang, jejak)

        # Portal menjawab "sudah menerima layanan" untuk DUA keadaan yang
        # berbeda: peserta yang pemeriksaannya memang sudah tuntas, dan
        # peserta yang baru hadir tapi formnya belum diisi. Dari halaman
        # pendaftaran keduanya tak bisa dibedakan - hanya halaman pelayanan
        # yang tahu, lewat tab Belum/Sedang/Selesai.
        #
        # Karena itu perlakuannya jadi pilihan:
        #   "penuh"            -> dilewati, cepat. Cocok bila hampir semua
        #                         memang sudah beres.
        #   "daftar_pelayanan" -> dilanjutkan lewat halaman pelayanan lalu
        #                         formnya disapu. Lebih lambat sekitar
        #                         setengah menit per peserta, tapi tidak ada
        #                         yang tertinggal.
        if (r["status"] == "sudah_terdaftar"
                and config.TAHAP in ("penuh", "daftar_pelayanan",
                                     "daftar_konfirmasi")):
            # Popup "Individu sudah terdaftar" berbeda artinya dari "sudah
            # menerima layanan": pendaftarannya ADA, tapi belum tentu sudah
            # dikonfirmasi hadir - dan halaman pendaftaran tidak bisa
            # membedakan keduanya. Jadi jangan divonis apa-apa di sini;
            # diteruskan persis seperti murid yang baru saja didaftarkan:
            # cari NIK di daftar, konfirmasi hadir bila tombolnya ada, lalu
            # lanjut ke pemeriksaan.
            r["keterangan"] += " | sudah terdaftar: lanjut cari NIK untuk konfirmasi hadir"
            # Portal SENDIRI yang bilang pendaftarannya ada. Itu izin untuk
            # menyapu kelas lain bila NIK-nya tidak ketemu di kelas yang
            # tertulis di CSV - lihat `sekolah.cari_di_kelas_lain`.
            r["portal_akui"] = True
            if sekolahan:
                # Popup masih menutupi formulir yang ber-URL sama dengan
                # daftar murid - daftarnya harus diminta dimuat ulang.
                sekolah.penuh(halaman, orang, r, jejak_layanan, muat_ulang=True)
            else:
                _lanjut_ke_pelayanan(halaman, orang, r, jejak_layanan)

        elif (sekolahan and r["status"] == "tidak_valid"
                and config.TAHAP in ("penuh", "daftar_pelayanan",
                                     "daftar_konfirmasi")):
            # DATA DITOLAK PORTAL BUKAN AKHIR CERITA.
            #
            # "Data peserta tidak valid" - baik saat diketik manual maupun
            # sesudah diulang dengan Cek NIK - hanya berarti portal menolak
            # MENDAFTARKAN identitas itu lagi. Ternyata sebabnya justru
            # NIK-nya SUDAH TERDAFTAR di sistem: muridnya ada, hanya tidak
            # bisa didaftarkan dua kali. Memvonis `tidak_valid` di sini
            # menghentikan murid yang sebenarnya tinggal dikonfirmasi hadir
            # lalu diperiksa. Keputusan pengguna, 4 Sep.
            #
            # Daftar konfirmasi hadir yang jadi hakimnya:
            #   ada, belum dikonfirmasi  -> dikonfirmasi lalu diperiksa
            #   ada, sudah hadir         -> dilanjutkan ke halaman pelayanan
            #   TIDAK ada di sana        -> halaman pelayanan tetap ditengok
            #                               dulu, sebab murid yang pemeriksaannya
            #                               sudah dimulai memang hilang dari
            #                               daftar pendaftaran
            #
            # dan di halaman pelayanan:
            #   tab Belum/Sedang -> dikerjakan
            #   tab Selesai      -> sudah_pelayanan
            #   tidak ada        -> tidak_ditemukan
            #
            # Statusnya dikosongkan lebih dulu supaya `penuh` bebas
            # menetapkan hasilnya sendiri; alasan penolakannya tetap tersimpan
            # di keterangan, jadi tidak ada keterangan yang hilang.
            r["keterangan"] += (" | ditolak portal, TAPI diteruskan: cari NIK"
                                " untuk konfirmasi hadir")
            r["status"] = "belum"
            sekolah.penuh(halaman, orang, r, jejak_layanan, muat_ulang=True)
            # PENOLAKAN PORTAL TIDAK BOLEH HILANG DARI STATUSNYA.
            #
            # Bila sesudah semua penelusuran muridnya memang tidak ada di mana
            # pun, yang paling menjelaskan keadaannya bukan "tidak ditemukan"
            # melainkan penolakan yang sudah terjadi lebih dulu: datanya ditolak
            # saat diketik manual DAN saat diulang dengan Cek NIK, lalu NIK-nya
            # juga tidak ada di daftar konfirmasi hadir maupun pelayanan. Tidak
            # ada satu pun tanda ia pernah terdaftar - jadi ini soal DATA.
            #
            # `tidak_ditemukan` disimpan untuk keadaan yang berbeda: data yang
            # DITERIMA portal (valid, atau dijawab "sudah menerima pelayanan")
            # tapi NIK-nya tidak ketemu di kedua daftar itu. Keputusan
            # pengguna, 4 Sep - 12 dari 12 `tidak_ditemukan` pada jalan
            # 12:04 ternyata semuanya data yang ditolak.
            if r.get("status") == "tidak_ditemukan":
                r["keterangan"] += (" | tidak ada jejak pendaftaran sama sekali"
                                    " - dikembalikan ke tidak_valid")
                r["status"] = "tidak_valid"

        elif (config.TAHAP == "daftar_konfirmasi"
                and r["status"] == "sudah_pelayanan"):
            # Peserta yang SUDAH TERDAFTAR tapi BELUM dikonfirmasi hadir
            # tidak tertangani alur mana pun sebelum ini, dan itulah data
            # yang menyangkut:
            #
            #   "penuh"            -> berhenti begitu pendaftaran menjawab
            #                         "sudah menerima layanan"
            #   "daftar_pelayanan" -> langsung ke halaman pelayanan, padahal
            #                         yang belum hadir memang BELUM ADA di
            #                         sana -> tidak_ditemukan
            #
            # Jalur ini mengirimnya ke daftar pendaftaran lebih dulu: cari
            # NIK, konfirmasi hadir bila tombolnya ada, baru lanjut. Bila
            # barisnya ternyata sudah bertanda "Sudah Hadir" - tanpa tombol
            # konfirmasi, hanya "Ganti Tanggal" - langkahnya diteruskan ke
            # halaman pelayanan seperti biasa.
            r["keterangan"] += " | dilanjutkan: cari NIK lalu konfirmasi hadir"
            # "sudah menerima layanan" = portal mengakui pendaftarannya ada,
            # jadi kelas lain boleh disapu bila NIK-nya tidak ketemu di kelas
            # yang tertulis di CSV - lihat `sekolah.cari_di_kelas_lain`.
            r["portal_akui"] = True
            # Lebih dari sekadar "ada": popupnya berbunyi murid ini TELAH
            # SELESAI DIPERIKSA, lengkap dengan tanggal dan puskesmasnya. Itu
            # keterangan portal tentang muridnya sendiri, dan tetap benar
            # walaupun sesudah ini ia tidak ketemu di daftar mana pun - lihat
            # vonis terakhir di `sekolah.penuh`.
            r["portal_dilayani"] = True
            if sekolahan:
                # Popup penolakan masih menutupi formulir, dan formulir itu
                # ber-URL sama dengan daftar murid - jadi daftarnya harus
                # diminta dimuat ulang secara tegas.
                sekolah.penuh(halaman, orang, r, jejak_layanan,
                              muat_ulang=True)
            else:
                # Konfirmasi hadir sudah tidak diminta portal untuk dewasa
                # (29 Sep), jadi halaman pelayanan didatangi lebih dulu; jalur
                # konfirmasi tinggal cadangan di dalam `_lanjut_ke_pelayanan`.
                _lanjut_ke_pelayanan(halaman, orang, r, jejak_layanan)

        elif (config.TAHAP == "daftar_pelayanan"
                and r["status"] == "sudah_pelayanan"):
            r["keterangan"] += " | dilanjutkan lewat halaman pelayanan"
            (sekolah.pelayanan_saja if sekolahan else layanan.pelayanan_saja)(
                halaman, orang, r, jejak_layanan)
            _vonis_popup_bila_tak_ada(halaman, r)

        elif r["status"] in ("belum", "terdaftar"):
            # "pelayanan_sapu" jalannya SAMA - bedanya hanya peserta di
            # tab Selesai ikut dibuka, dan itu diputuskan di dalam
            # `layanan.buka_dari_pelayanan`, bukan di percabangan ini.
            if config.TAHAP in ("pelayanan", "pelayanan_sapu"):
                # Tanpa pendaftaran sama sekali: cari NIK di halaman
                # pelayanan, tekan Mulai, isi formnya.
                (sekolah.pelayanan_saja if sekolahan else layanan.pelayanan_saja)(
                    halaman, orang, r, jejak_layanan)
            elif config.TAHAP in ("layanan", "isi"):
                layanan.buka_dan_petakan(halaman, orang, r, jejak_layanan)
            elif config.TAHAP in ("penuh", "daftar_pelayanan",
                                  "daftar_konfirmasi"):
                # Murid dicari lewat Sekolah+Kelas dan MASIH dikonfirmasi
                # hadir (ralat pengguna 29 Sep); dewasa langsung ke pelayanan.
                if sekolahan:
                    sekolah.penuh(halaman, orang, r, jejak_layanan)
                else:
                    _lanjut_ke_pelayanan(halaman, orang, r, jejak_layanan)
            elif config.TAHAP in ("konfirmasi", "keduanya"):
                layanan.jalankan(halaman, orang, r, jejak_layanan)
    except Exception as e:
        gambar = simpan_gambar(halaman, f"error_{orang.baris_csv}")
        # JEJAK YANG SUDAH TERKUMPUL JANGAN DIBUANG. Versi lama mengganti
        # seluruh hasil dengan kotak baru, sehingga peserta yang gagal di
        # langkah kesepuluh terlihat persis sama dengan yang gagal di
        # langkah pertama: keterangannya cuma nama galat. Padahal justru di
        # jejak itulah letak petunjuknya - sampai mana ia berhasil.
        sebelum = (r or {}).get("keterangan", "").strip(" |")
        r = dict(baris=orang.baris_csv, nik=orang.kunci, nama=orang.nama, status="error",
                 keterangan=(f"{sebelum} | " if sebelum else "")
                            + f"{type(e).__name__}: " + " ".join(str(e).split())[:300],
                 tiket=(r or {}).get("tiket", ""))
        kerja.lapor(f"    ERROR — bukti disimpan: {gambar}")
    return r


def _coba_peserta(halaman, orang, kerja, jejak: list, jejak_layanan: list,
                 r_awal: dict | None = None) -> dict:
    """Kerjakan satu peserta, dengan pengulangan untuk kegagalan sementara."""
    sekolahan = kategori_sekolah(orang)
    r = r_awal or {}
    # DIULANG BILA PORTALNYA YANG BERMASALAH, bukan datanya. Kegagalan
    # seperti tenggat habis, halaman menggantung, atau modal yang tidak
    # merespons hampir selalu sementara - dan menyerah pada percobaan
    # pertama membuat peserta yang sebenarnya baik-baik saja tercatat
    # gagal. Yang datanya memang salah (`tidak_valid`, `tidak_ditemukan`)
    # TIDAK diulang: jawabannya akan sama persis berapa kali pun dicoba.
    for percobaan in range(1, max(1, config.PERCOBAAN_ULANG) + 1):
        # Percobaan pertama putaran ULANG AKHIR juga melanjutkan dari daftar
        # layanan bila peserta sudah sampai di sana - mendaftar ulang membuat
        # portal menjawab "sudah menerima layanan" dan form yang kosong
        # tertinggal.
        if (percobaan > 1 or r_awal) and _sampai_daftar_layanan(halaman, r):
            # Sudah pernah masuk daftar layanan -> jangan mendaftar ulang.
            _ulangi_dari_layanan(halaman, orang, r, sekolahan,
                                 jejak_layanan, percobaan)
        else:
            r = _kerjakan_satu(halaman, orang, sekolahan, kerja,
                               jejak, jejak_layanan)
        if r.get("status") not in GAGAL_SEMENTARA:
            break
        if percobaan >= max(1, config.PERCOBAAN_ULANG):
            r["keterangan"] = (r.get("keterangan", "")
                               + f" | menyerah setelah {percobaan} percobaan")
            break
        kerja.lapor(f"    percobaan {percobaan} gagal ({r.get('status')})"
                    f" - diulang")
        _bersihkan_halaman(halaman, kerja)
        if _galat_jaringan(r):
            _tunggu_jaringan(halaman, kerja)
        if kerja.minta_berhenti:
            # DITANDAI, bukan diam-diam ditinggalkan. Tanpa catatan ini
            # hasilnya terlihat sama persis dengan kegagalan yang sudah
            # habis 3 percobaan - padahal artinya jauh berbeda: yang ini
            # BELUM SELESAI DIUJI, dan besar kemungkinan berhasil bila
            # dijalankan ulang. Terjadi pada seorang murid (4 Sep):
            # "gagal" tanpa keterangan apa pun soal percobaan, karena
            # pekerjaannya dihentikan tepat di tengah pengulangan.
            r["keterangan"] = (r.get("keterangan", "")
                               + f" | DIHENTIKAN saat percobaan ke-{percobaan}"
                                 " - belum tuntas diuji, jalankan ulang")
            break
    if percobaan > 1 and r.get("status") not in GAGAL_SEMENTARA:
        # "berhasil" dulu ditempelkan pada SEMUA status yang tidak diulang,
        # termasuk `tidak_ditemukan` - catatan seorang murid berakhir "tak ada
        # di daftar pelayanan | berhasil pada percobaan ke-2".
        kata = ("berhasil" if r.get("status") not in
                ("tidak_ditemukan", "tidak_valid", "daftar_kosong")
                else "diputuskan")
        r["keterangan"] = (r.get("keterangan", "")
                           + f" | {kata} pada percobaan ke-{percobaan}")
    return r


def kerjakan_batch(halaman, batch: list, kerja: Pekerjaan,
                   catatan_hasil, jejak: list, jejak_layanan: list) -> None:
    """
    Proses seluruh batch. Satu-satunya tempat alur per peserta ditentukan.

    `catatan_hasil` harus punya `.tambah(dict)` — CSV hasil ditulis per peserta
    supaya batch yang putus tidak kehilangan catatan.
    """
    kerja.total = len(batch)
    beruntun = 0
    berhenti_beruntun = False
    diproses: list[tuple[int, object]] = []        # (indeks di kerja.hasil, peserta)

    # Nama dengan catatan administrasi ("(EM)", ", SE", "*") ditolak portal dan
    # membuat tombol Selanjutnya mati selamanya. Sudah dirapikan saat CSV
    # dibaca, tapi petugas HARUS tahu - yang didaftarkan bukan lagi tulisan
    # persis di berkasnya.
    nomor_batch = {o.baris_csv for o in batch}
    dirapikan = [x for x in peserta.NAMA_DIBERSIHKAN if x[0] in nomor_batch]
    if dirapikan:
        kerja.lapor(f"{len(dirapikan)} nama dirapikan agar diterima portal:")
        for nomor_baris, asli, bersih in dirapikan[:10]:
            kerja.lapor(f"    baris {nomor_baris}: {asli}  ->  {bersih}")
        if len(dirapikan) > 10:
            kerja.lapor(f"    ... dan {len(dirapikan) - 10} lagi")

    for nomor, orang in enumerate(batch, start=1):
        if kerja.minta_berhenti:
            kerja.lapor("Dihentikan oleh pengguna.")
            break

        # Nama akun dicoba lagi selama masih kosong. Halaman pendaratan
        # sesudah login belum tentu memuat kepala berisi nama akun; halaman
        # kerja yang sebenarnya hampir pasti memuatnya. Ongkosnya nol begitu
        # terbaca sekali - sesudah itu tidak pernah dibaca lagi.
        if not kerja.akun:
            kerja.akun = portal.nama_akun(halaman)
            if kerja.akun:
                kerja.lapor(f"    akun portal: {kerja.akun}")
            elif nomor == 1:
                kerja.lapor("    nama akun tak terbaca. Yang ada di kepala halaman: "
                            f"{portal.kepala_halaman(halaman)}")
        kerja.lapor(f"[{nomor}/{len(batch)}] {_sebutan(orang)}")
        r = _coba_peserta(halaman, orang, kerja, jejak, jejak_layanan)

        r["waktu"] = datetime.now().strftime("%H:%M:%S")
        # Tanggal lahir tidak pernah dikembalikan alur pendaftaran maupun
        # pelayanan - keduanya bekerja dengan NIK. Diambil dari datanya sendiri
        # supaya ekspor hasil bisa memuatnya tanpa membaca CSV ulang.
        lahir = getattr(orang, "tanggal_lahir", None)
        r["tgl_lahir"] = (lahir.strftime("%d/%m/%Y") if lahir
                          else getattr(orang, "tgl_lahir_teks", "") or "")
        kerja.hasil.append(dict(r))
        diproses.append((len(kerja.hasil) - 1, orang))
        kerja.selesai = nomor
        catatan_hasil.tambah(r)
        # Berapa lama penantian benar-benar makan waktu, dibanding jeda tetap
        # yang digantikannya. Tanpa angka ini, "sudah lebih cepat" cuma perasaan.
        w = portal.ringkas_waktu()
        if w["langkah"]:
            pesan = (f"    waktu tunggu: {w['detik']}s "
                     f"(cara lama {w['dulu']}s, hemat {w['hemat']}s)")
            if w.get("lambat"):
                pesan += f" · terlama: {', '.join(w['lambat'])}"
            if w["gagal"]:
                pesan += f" · tak terdeteksi: {', '.join(w['gagal'][:3])}"
            kerja.lapor(pesan)

        kerja.lapor(f"    {r['status']}"
                    + (f" · tiket {r['tiket']}" if r.get("tiket") else "")
                    + (f" · {r['keterangan'][:160]}" if r.get("keterangan") else ""))

        # Browser yang melambat membuat langkah yang tadinya lancar mulai gagal
        # berturut-turut. Meneruskannya hanya merusak peserta berikutnya,
        # padahal obatnya cuma menutup browser lalu menjalankan ulang.
        beruntun = beruntun + 1 if r["status"] in ("gagal", "error") else 0
        if config.BERHENTI_SETELAH_GAGAL and beruntun >= config.BERHENTI_SETELAH_GAGAL:
            kerja.pesan = (f"Dihentikan: {beruntun} peserta gagal berturut-turut. "
                           "Biasanya browser sudah melambat — tutup browsernya, "
                           "jalankan lagi dengan rentang yang sama.")
            kerja.lapor(kerja.pesan)
            berhenti_beruntun = True
            break

    # PUTARAN ULANG DI AKHIR BATCH.
    #
    # Pengulangan di atas terjadi saat itu juga - kalau portal sedang padat
    # (429, halaman macet), tiga percobaan beruntun bisa gagal semua padahal
    # beberapa menit kemudian lancar. Peserta itu dulu harus dijalankan ulang
    # manual dengan rentang yang sama. Sekarang dicoba sekali lagi di akhir,
    # sesudah peserta lain selesai. Tidak dijalankan bila batch dihentikan
    # petugas, atau berhenti karena gagal beruntun (browsernya yang melambat).
    for putaran in range(1, max(0, config.ULANG_AKHIR) + 1):
        if kerja.minta_berhenti or berhenti_beruntun:
            break
        sisa = [(i, o) for i, o in diproses if kerja.hasil[i].get("status") in GAGAL_SEMENTARA]
        if not sisa:
            break
        kerja.lapor(f"Putaran ulang {putaran}: {len(sisa)} peserta yang gagal dicoba sekali lagi")
        for k, (indeks, orang) in enumerate(sisa, start=1):
            if kerja.minta_berhenti:
                kerja.lapor("Dihentikan oleh pengguna.")
                break
            kerja.lapor(f"[ulang {k}/{len(sisa)}] {_sebutan(orang)}")
            _bersihkan_halaman(halaman, kerja)
            lama = kerja.hasil[indeks]
            r = _coba_peserta(halaman, orang, kerja, jejak, jejak_layanan, r_awal=dict(lama))
            r["keterangan"] = (r.get("keterangan", "")
                               + f" | putaran ulang di akhir batch (sebelumnya {lama.get('status')})")
            r["waktu"] = datetime.now().strftime("%H:%M:%S")
            r["tgl_lahir"] = lama.get("tgl_lahir", "")
            kerja.hasil[indeks] = dict(r)          # tabel menampilkan hasil TERAKHIR
            catatan_hasil.tambah(r)                 # CSV: baris baru, yang terakhir berlaku
            kerja.lapor(f"    {r['status']}"
                        + (f" · tiket {r['tiket']}" if r.get("tiket") else "")
                        + (f" · {r['keterangan'][:160]}" if r.get("keterangan") else ""))
