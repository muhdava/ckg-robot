"""
Pengaturan pusat. Ubah nilai di sini saja — file lain tidak perlu disentuh.
"""
from pathlib import Path

# ---------------------------------------------------------------- lokasi berkas
# Kode tinggal di `inti/`, sedangkan yang disentuh petugas - pengaturan,
# data, dan hasil - ada di folder induknya. Karena itu AKAR naik satu
# tingkat: semua jalur di bawah ini menunjuk ke folder aplikasi, bukan
# ke folder kode.
AKAR = Path(__file__).resolve().parent.parent

# Versi aplikasi (tahun.bulan.tanggal, angka 2 digit). Dipakai login online:
# admin bisa menolak versi yang lebih lama dari "versi minimal". Naikkan
# setiap kali membuat paket yang perlu dipakai semua petugas.
VERSI = "2026.10.14.1303"
PROYEK = AKAR.parent
DATA = AKAR / "data"
# Tempat menaruh berkas MENTAH (.xlsx dari sekolah/puskesmas) yang belum
# diubah jadi CSV. Dipisah dari `data/` supaya yang siap jalan dan yang
# masih mentah tidak pernah tertukar di daftar pilihan.
MENTAH = AKAR / "mentah"

# Sumber data peserta (CSV yang sama dengan yang dipakai macro V7)
# Data uji (1 peserta) — untuk membangun & memverifikasi alur.
# Ganti ke baris di bawahnya bila sudah mau memakai data sungguhan.
CSV_PESERTA = DATA / "datackg2.csv"
# CSV_PESERTA = DATA / "data-uji.csv"
# CSV_PESERTA = PROYEK / "Real Data" / "datackg_realdata.csv"

# Folder hasil: CSV keluaran + tangkapan layar saat gagal
HASIL = AKAR / "hasil"
GAMBAR_GAGAL = HASIL / "gagal"

# Profil browser yang menetap, supaya cukup login SEKALI.
# Sesi login tersimpan di sini dan dipakai lagi pada run berikutnya.
PROFIL_BROWSER = AKAR / ".profil-browser"

# ---------------------------------------------------------------- alamat portal
PORTAL = "https://sehatindonesiaku.kemkes.go.id"
HAL_PENDAFTARAN = f"{PORTAL}/ckg-pendaftaran-individu"
# Peserta yang sudah "Sedang Pemeriksaan" tidak lagi muncul di halaman
# pendaftaran � harus dicari dari halaman pelayanan.
HAL_PELAYANAN = f"{PORTAL}/ckg-pelayanan"
# Pendaftaran murid memakai rute tersendiri, dengan filter Sekolah+Kelas
# di atas daftarnya.
HAL_SEKOLAH = f"{PORTAL}/ckg-pendaftaran-anak-sekolah"
# Murid punya halaman pelayanan SENDIRI, terpisah dari `/ckg-pelayanan` milik
# alur individu. Tab dan tombolnya sama (Belum/Sedang/Selesai + "Mulai"), tapi
# daftarnya baru muncul setelah filter Sekolah + Kelas dipasang.
HAL_PELAYANAN_SEKOLAH = f"{PORTAL}/ckg-pelayanan-sekolah"
HOST_FORM = "form.kemkes.go.id"          # domain form skrining (SurveyJS)

# ---------------------------------------------------------------- batch
# Baris CSV yang diproses: BARIS_AWAL sampai BARIS_AWAL + JUMLAH_DATA - 1
# (baris 1 = baris pertama data; CSV tidak punya baris judul)
BARIS_AWAL = 1133
JUMLAH_DATA = 1

# ---------------------------------------------------------------- tahap kerja
# "pendaftaran" = daftar saja
# "konfirmasi"  = lewati pendaftaran, langsung konfirmasi hadir + mulai
#                 pemeriksaan (untuk peserta yang sudah punya tiket)
# "layanan"     = buka halaman pemeriksaan lalu petakan daftar layanannya
# "isi"         = buka halaman pemeriksaan lalu ISI form-formnya
# "penuh"       = daftar -> konfirmasi hadir -> mulai -> isi semua form
# "keduanya"    = daftar lalu langsung dilanjutkan
# "pelayanan"   = TANPA pendaftaran: cari NIK langsung di halaman pelayanan,
#                 tekan Mulai, lalu isi semua form. Untuk peserta yang sudah
#                 terdaftar dan tinggal dilayani.
# "daftar_pelayanan" = daftar dulu; peserta yang dijawab "sudah menerima
#                 layanan" TIDAK dilewati, melainkan dilanjutkan lewat halaman
#                 pelayanan lalu formnya disapu. Untuk berkas bercampur:
#                 sebagian belum terdaftar, sebagian sudah hadir tapi belum
#                 diperiksa.
# Alur yang dijalankan:
#   penuh            daftar -> konfirmasi hadir -> mulai -> isi form
#   daftar_pelayanan sama, tapi yang "sudah dilayani" dilanjutkan lewat pelayanan
#   daftar_konfirmasi yang sudah terdaftar TAPI BELUM hadir: dicari NIK-nya
#                    di daftar pendaftaran, dikonfirmasi hadir, baru disapu
#   pelayanan        tanpa pendaftaran; yang ada di tab Selesai DILEWATI
#   pelayanan_sapu   sama, tapi tab Selesai IKUT DIBUKA lalu form yang masih
#                    kosong diisi. Portal menaruh orang di tab Selesai
#                    berdasarkan status ORANGNYA, bukan kelengkapan formnya -
#                    keduanya bisa berbeda, dan mode ini yang memeriksanya.
TAHAP = "penuh"

# Kategori peserta. "auto" = ikuti isi CSV-nya (disarankan);
# "dewasa" / "sekolah" / "balita" memaksa kategori tertentu. Bawaannya auto supaya berkas dan alur tidak mungkin
# bertentangan - kesalahan yang pernah membuat berkas sekolah dijalankan lewat
# alur individu tanpa ada yang memberi tahu.
KATEGORI = "auto"

# Berapa lama menunggu nomor tiket terbit sesudah "Daftarkan dengan NIK".
# Portal kadang lama sekali di sini, dan menyerah terlalu cepat membuat peserta
# yang SEBENARNYA terdaftar tercatat "tanpa tiket" lalu tidak bisa dilanjutkan.
# Penantiannya berhenti begitu tiket muncul, jadi angka besar tidak memperlambat
# kasus normal - hanya menaikkan batas kasus terburuk.
# Pendaftaran murid: tekan "Cek NIK" dulu, atau ketik seluruh identitasnya
# sendiri? Cek NIK menarik data Dukcapil - lebih cepat dan pasti cocok -
# tapi bagi murid ia sering menjawab data yang tidak diinginkan petugas.
# Dimatikan atas permintaan: alur sekolah mengisi semuanya manual.
CEK_NIK_SEKOLAH = False

# Berapa kali satu peserta diulang bila yang gagal ternyata PORTALNYA -
# tenggat habis, halaman menggantung, modal yang tidak merespons. Hanya
# kegagalan semacam itu yang diulang; data yang memang salah tidak.
PERCOBAAN_ULANG = 3
# Berapa kali peserta yang tetap GAGAL dicoba lagi di akhir batch, sesudah
# peserta lain selesai (portal yang padat biasanya sudah pulih). 0 = mati.
ULANG_AKHIR = 1

# Jeda sebelum mencoba lagi bila yang gagal ternyata JARINGAN (detik).
# Galat jaringan tidak sembuh dalam sepersekian detik, jadi mengulang
# secepatnya hanya membakar peserta: pada 3 Sep tiga murid berturut-turut
# tercatat 'error' dalam 6 detik hanya karena internet putus sesaat.
JEDA_JARINGAN = 30
# Cadangan alamat domisili murid bila "Lokasi Sekolah" di portal kosong dan
# alamat murid tidak menyebut kelurahan (lihat sekolah.isi_alamat). Kosong =
# tidak ditebak; murid itu tetap gagal dengan keterangan yang jelas.
KELURAHAN_DOMISILI_SEKOLAH = ""

TUNGGU_TIKET_MS = 45_000

# Berapa lama menunggu peserta yang baru didaftarkan muncul di daftar. Portal
# butuh sesaat sebelum peserta baru bisa dicari.
TUNGGU_MUNCUL_MS = 12_000

# Berapa kali halaman daftar layanan dimuat ulang bila isinya tidak ter-render.
# Portal ini kadang menampilkan daftar kosong; refresh membereskannya.
REFRESH_DAFTAR = 3

# Berapa kali daftar layanan disapu ulang untuk mengejar form yang gagal.
SWEEP_PUTARAN = 3
# Batas jumlah form per peserta; 0 = tanpa batas.
# Dipakai untuk mencoba beberapa form dulu sebelum dilepas penuh.
MAKS_FORM = 0

# Berapa banyak browser (dan karenanya akun puskesmas) boleh dipakai sekaligus.
#
# SATU SUMBER untuk dua tempat: pilihan di halaman aplikasi dan penjaga di sisi
# server. Dulu angkanya ditulis dua kali - kalau yang satu diubah dan yang lain
# tidak, pilihan di layar tetap terlihat ada tapi diam-diam dipangkas server.
#
# Tiap pekerja butuh AKUN PUSKESMAS SENDIRI yang login terpisah, jadi angka ini
# batas atas, bukan sasaran: sebanyak-banyaknya sejumlah akun yang benar-benar
# dipunyai. Tiap browser tambahan juga memakan memori dan menambah beban ke
# portal.
MAKS_PEKERJA = 10

# Tekan "Selesaikan Layanan" setelah semua form terisi.
# Ini menutup pelayanan peserta di portal, jadi dinyalakan sendiri
# setelah hasil pengisian dipastikan benar.
SELESAIKAN_LAYANAN = True

# Hentikan batch bila sekian peserta gagal BERTURUT-TURUT. Gejala khas
# browser yang melambat; meneruskannya hanya merusak peserta berikutnya.
# 0 = jangan pernah berhenti sendiri.
BERHENTI_SETELAH_GAGAL = 3

# ---------------------------------------------------------------- keamanan
# True  = jalankan semua langkah TAPI berhenti sebelum klik "Daftarkan",
#         sehingga TIDAK ada data peserta yang benar-benar tercatat di portal.
# False = pendaftaran sungguhan.
MODE_UJI = False

# ---------------------------------------------------------------- perilaku browser
TAMPILKAN_BROWSER = True    # False = jalan di latar belakang (headless)
PERLAMBAT_MS = 0            # mis. 250 untuk memperlambat agar mudah diamati
BROWSER = "chrome"          # "chrome" pakai Chrome yang sudah terpasang; None = Chromium bawaan Playwright

# Batas waktu (milidetik)
TIMEOUT_UMUM = 15_000       # menunggu elemen biasa
TIMEOUT_PINDAH_HALAMAN = 45_000   # portal ini kadang lambat

# ---------------------------------------------------------------- nomor cadangan
# Dipakai bila kolom No HP peserta kosong
NOHP_CADANGAN = "81210076973"


def siapkan_folder() -> None:
    """Buat folder hasil bila belum ada."""
    for f in (HASIL, GAMBAR_GAGAL, PROFIL_BROWSER, DATA, MENTAH):
        f.mkdir(parents=True, exist_ok=True)


# ==================================================================
#  Pengaturan dari berkas teks
# ==================================================================
# Nilai di atas adalah bawaan. Bila ada `pengaturan.txt`, isinya menimpa
# nilai bawaan itu — supaya pemakaian sehari-hari tidak perlu menyunting
# kode Python, di mana satu tanda kutip yang hilang membuat seluruh program
# gagal jalan dengan pesan yang tidak bisa dimengerti.
BERKAS_PENGATURAN = AKAR / "pengaturan.txt"

# kunci di pengaturan.txt -> (nama variabel, jenis)
_DIKENAL = {
    "berkas csv": ("CSV_PESERTA", "berkas"),
    "baris awal": ("BARIS_AWAL", "angka"),
    "jumlah data": ("JUMLAH_DATA", "angka"),
    "tahap": ("TAHAP", "teks"),
    "kategori": ("KATEGORI", "teks"),
    "cek nik sekolah": ("CEK_NIK_SEKOLAH", "boolean"),
    "percobaan ulang": ("PERCOBAAN_ULANG", "angka"),
    "ulang di akhir batch": ("ULANG_AKHIR", "angka"),
    "jeda galat jaringan": ("JEDA_JARINGAN", "angka"),
    "kelurahan domisili sekolah": ("KELURAHAN_DOMISILI_SEKOLAH", "teks"),
    "mode uji": ("MODE_UJI", "boolean"),
    "selesaikan layanan": ("SELESAIKAN_LAYANAN", "boolean"),
    "lewati sudah selesai": ("LEWATI_SUDAH_SELESAI", "boolean"),
    "ulang tidak valid": ("ULANG_TIDAK_VALID", "boolean"),
    "maks pekerja": ("MAKS_PEKERJA", "angka"),
    "sweep putaran": ("SWEEP_PUTARAN", "angka"),
    "refresh daftar": ("REFRESH_DAFTAR", "angka"),
    "tunggu tiket": ("TUNGGU_TIKET_MS", "angka"),
    "tunggu muncul": ("TUNGGU_MUNCUL_MS", "angka"),
    "maks form": ("MAKS_FORM", "angka"),
    "tampilkan browser": ("TAMPILKAN_BROWSER", "boolean"),
    "nomor hp cadangan": ("NOHP_CADANGAN", "teks"),
    "berhenti setelah gagal": ("BERHENTI_SETELAH_GAGAL", "angka"),
    "timpa form": ("TIMPA_FORM", "teks"),
}

# Form yang BOLEH DIISI ULANG walau portal sudah menandainya selesai - hanya
# berlaku pada alur "Pelayanan -> Selesai (sapu)". Dipisahkan koma, dicocokkan
# ke judul barisnya, tidak peduli besar-kecil huruf.
#
# KENAPA JADI PENGATURAN, BUKAN DAFTAR TETAP DI KODE. Isinya berubah menurut
# pekerjaan: bulan lalu yang perlu dibetulkan "Tingkat Aktivitas Fisik" (robot
# sendiri pernah mengisinya 5,5 lalu 30,30), sekarang "Kesehatan Jiwa" yang
# terlanjur terekam bergejala. Waktu keduanya sama-sama tertulis di kode, satu
# jalan perbaikan Kesehatan Jiwa IKUT mengubah jawaban aktivitas fisik peserta
# yang sudah benar - terjadi 7 Sep, dan pengguna yang menemukannya.
#
# Menimpa jawaban yang sudah ada tidak bisa dibatalkan, jadi bawaannya SATU
# saja: yang sedang dikerjakan. Kosongkan kalau tidak ada yang perlu ditimpa.
TIMPA_FORM = "kesehatan jiwa"

# Lewati peserta yang pada run sebelumnya sudah tercatat selesai.
LEWATI_SUDAH_SELESAI = True

# Jalankan lagi peserta yang pada run sebelumnya DITOLAK portal (tidak_valid).
# Bawaannya tidak: jawaban portal atas data yang sama tidak berubah berapa
# kali pun dicoba. Nyalakan sesudah datanya dibetulkan tanpa mengganti NIK.
ULANG_TIDAK_VALID = False

# Kesalahan pembacaan pengaturan, ditampilkan run.py di awal.
CATATAN_PENGATURAN: list[str] = []


def _boolean(teks: str) -> bool | None:
    t = teks.strip().lower()
    if t in ("ya", "true", "1", "aktif", "nyala"):
        return True
    if t in ("tidak", "false", "0", "mati", "nonaktif"):
        return False
    return None


def muat_pengaturan() -> None:
    """Baca `pengaturan.txt` bila ada, lalu timpa nilai bawaan di atas."""
    if not BERKAS_PENGATURAN.exists():
        return
    global CSV_PESERTA
    for nomor, baris in enumerate(
            BERKAS_PENGATURAN.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        isi = baris.split("#", 1)[0].strip()
        if not isi:
            continue
        if "=" not in isi:
            CATATAN_PENGATURAN.append(f"baris {nomor}: tidak ada tanda '=' — dilewati")
            continue
        kunci, _, nilai = isi.partition("=")
        kunci, nilai = kunci.strip().lower(), nilai.strip()
        if kunci not in _DIKENAL:
            CATATAN_PENGATURAN.append(f"baris {nomor}: pengaturan '{kunci}' tidak dikenal")
            continue
        nama, jenis = _DIKENAL[kunci]
        if jenis == "angka":
            if not nilai.lstrip("-").isdigit():
                CATATAN_PENGATURAN.append(f"baris {nomor}: '{nilai}' bukan angka — dipakai bawaan")
                continue
            globals()[nama] = int(nilai)
        elif jenis == "boolean":
            b = _boolean(nilai)
            if b is None:
                CATATAN_PENGATURAN.append(
                    f"baris {nomor}: '{nilai}' bukan ya/tidak — dipakai bawaan")
                continue
            globals()[nama] = b
        elif jenis == "berkas":
            # Nama berkas saja dicari di folder data lebih dulu - di situlah
            # tempatnya sekarang - baru di akar, supaya pengaturan lama
            # yang menyebut berkas di akar tetap terbaca.
            if Path(nilai).is_absolute():
                calon = Path(nilai)
            else:
                calon = DATA / nilai
                if not calon.exists():
                    calon = AKAR / nilai
            if not calon.exists():
                CATATAN_PENGATURAN.append(f"baris {nomor}: berkas '{nilai}' tidak ada — dipakai bawaan")
                continue
            globals()[nama] = calon
        else:
            globals()[nama] = nilai


muat_pengaturan()
