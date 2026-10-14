# CKG Robot — input otomatis Cek Kesehatan Gratis

Robot yang mengisi pendaftaran dan pemeriksaan **Cek Kesehatan Gratis (CKG)** di portal
**Sehat Indonesiaku** (`sehatindonesiaku.kemkes.go.id`) secara otomatis dari data Excel/CSV.
Ditulis dengan Python + Playwright, berjalan di komputer petugas, dan dikendalikan lewat
halaman web lokal (`localhost:8765`).

- **Website & unduhan:** https://ckg-robot.netlify.app/ (akun disetujui admin)
- **Panduan lengkap:** `Panduan CKG Robot.pdf` (juga tombol 📖 *Baca Panduan* di aplikasi)
- **Dibuat oleh:** Muhammad Dava Aryoga (Pasukan Putih Lagoa)
- **Bukan aplikasi resmi Kementerian Kesehatan RI.** Kebenaran data tetap tanggung jawab petugas.

---

## Fitur

### Pengisian otomatis
- **Tiga jenis CKG:** Dewasa/Lansia, CKG Sekolah (SD–SMA), Balita (termasuk balita tanpa NIK).
- **Lima alur kerja:** Pendaftaran → Selesai · Pendaftaran → Pelayanan → Selesai (disarankan) ·
  Pendaftaran → Konfirmasi Hadir → Selesai · Pelayanan → Selesai · Pelayanan → Selesai (sapu tab Selesai).
- **Per peserta:** daftar (tiket) → konfirmasi hadir (sekolah) → mulai pemeriksaan → isi **semua**
  form (SurveyJS) → periksa ulang form kosong → catat hasil.
- **Beberapa browser sekaligus**, masing-masing dengan akun portal sendiri; data dibagi rata.
- **Tidak dibatasi jumlah** — sudah diuji 1.000 peserta sekali jalan.
- **Bisa dilanjutkan:** jalankan lagi dengan nomor yang sama, yang sudah tuntas dilewati otomatis.

### Tahan terhadap portal yang padat/berubah
- **429 Too Many Requests / 502–504:** menunggu bertahap (15 dtk–1,5 mnt), muat ulang, lanjut.
- **Halaman macet sesudah Kirim** ("Kembali ke Halaman Utama"): muat ulang, form terisi dikirim,
  form kosong diisi, daftar layanan dilanjutkan dari status barisnya.
- **Pengulangan:** tiap peserta sampai 3 percobaan, plus **putaran ulang di akhir batch** untuk yang
  tetap gagal. Berhenti sendiri setelah 3 kegagalan beruntun (tanda browser melambat).
- Mengenali peserta yang sudah dilayani di puskesmas/sekolah/kelas/jalur lain — tidak didaftarkan dua kali.
- Menerima bentuk lama **dan** baru portal (perubahan Sep 2026: pendaftaran 2 halaman, status baru, kelompok lipat).

### Data
- **Siapkan data dari Excel:** register sekolah, skrining TBC, buku kunjungan, template, atau bentuk bebas
  (kolom dikenali dari judulnya). Lembar Laporan/Rekap/Perlu Dicek dilewati.
- Tanggal lahir & jenis kelamin disamakan dengan NIK (digit 7–12). NIK rusak Excel (angka, `3,17E+15`,
  terpotong `0000`), kembar, atau bukan 16 digit dilaporkan; yang bukan 16 digit tidak dikirim ke portal.
- **Murid tanpa hasil pemeriksaan DITAHAN** (tidak masuk CSV) supaya tidak tercatat dengan nilai bawaan.
- **Template untuk sekolah** (`Template DATA SISWA (untuk sekolah).xlsx`): NIK terkunci teks, kolom
  **Cek NIK** otomatis, baris bermasalah berwarna, lembar Petunjuk untuk operator sekolah.

### Hasil & laporan
- Tabel hasil berwarna per status, **Unduh Excel** (Hasil + Rekap), CSV hasil per peserta di `hasil\`.
- **Buat Laporan:** data asli + kolom Hasil; untuk CKG Sekolah ditambah **Rekap per Kelas**,
  **Perlu Tindakan** (dengan langkahnya), dan **Hb Rendah** (derajat anemia WHO).
- Tangkapan layar setiap kegagalan di `hasil\gagal\`.

### Akun, keamanan, dan pembaruan (login online)
- **Login online (Supabase):** petugas mendaftar (website atau aplikasi), **disetujui admin**.
  Izin diperiksa saat masuk dan setiap kali pekerjaan dimulai. Batas komputer per akun, versi minimal,
  pengumuman. Login portal tetap dilakukan petugas sendiri (captcha); kata sandi portal tidak disimpan.
- **Kelola Petugas** (aplikasi & `ckg-robot.netlify.app/kelola/`): setujui/tolak, nonaktifkan,
  buatkan akun, **ubah data petugas** (nama, puskesmas, no. HP, email), ganti sandi, lepas komputer, pengumuman, **rekap pemakaian** (jumlah per hari/petugas,
  peringatan bila kegagalan melonjak), unduh daftar petugas.
- **Pembaruan dari dalam aplikasi:** admin *Terbitkan pembaruan* → petugas melihat pita
  **Versi baru tersedia** → *Perbarui sekarang*: unduh → cek SHA-256 → cadangkan → pasang → mulai ulang.
  Tombol **Periksa pembaruan** + pemeriksaan otomatis tiap jam. Data & pengaturan tidak disentuh.
- **Skrining TBC diisi sesuai temuan** (batuk, gejala, rontgen, kontak, mata, telinga, gigi, merokok, DM) dari
  kolom `rinci` yang ditulis pengekstrak lembar Skrining TBC.
- **Pengumuman admin sampai saat robot bekerja:** aplikasi menanyakan pengumuman tiap 2 menit (server paling
  sering sekali per 90 detik). Isi baru → kotak *Pengumuman baru dari admin*, notifikasi Windows, judul tab
  berkedip; sekali per isi. Akun yang dinonaktifkan di tengah batch diberi tahu (batch berjalan tetap selesai).
- **Setup.exe (Inno Setup) dengan Python bawaan:** petugas baru tidak perlu memasang Python. Dipasang per
  pengguna di `%LOCALAPPDATA%\CKG Robot` (tanpa izin administrator), ikon CKG Robot di Desktop & Start Menu,
  pintasan "folder data", uninstall dari Control Panel (data, hasil, pengaturan ditinggal). Pustaka diunduh
  saat Setup berjalan; bila gagal (tanpa internet) dipasang otomatis saat aplikasi pertama dibuka.
- **Ikon & shortcut** untuk pemasangan ZIP juga: dibuat `pasang.bat`, atau otomatis sekali setelah pembaruan.
  Jendela hitam mengecil sendiri ke taskbar begitu aplikasi siap (muncul lagi bila ada galat).
- **Data peserta tidak pernah dikirim ke server akun** — hanya ke portal. Rekap pemakaian berisi angka saja.

### Website (repo terpisah: `website-ckg-robot`)
Halaman berlogin, unduhan dari penyimpanan privat (tautan sementara), demo interaktif aplikasi untuk latihan,
dan Kelola Petugas untuk admin.

---

## Pemasangan (petugas)

1. Daftar di **ckg-robot.netlify.app**, tunggu disetujui admin, unduh **Setup**.
2. Jalankan `CKG-Robot-Setup.exe` → Lanjut → Pasang (butuh internet). Bila muncul *Windows protected your PC*:
   **More info → Run anyway** (Setup belum bersertifikat berbayar).
3. Setiap kali bekerja: klik ikon **CKG Robot** di Desktop, masuk dengan email & kata sandi akun CKG Robot.

Cara lama (ZIP): pasang Python 3.14 64-bit (centang *Add python.exe to PATH*), ekstrak ZIP ke folder tetap,
klik ganda `pasang.bat` sekali — ikon Desktop ikut dibuat.

Langkah bergambar: `Panduan CKG Robot.pdf`.

## Susunan repo

```
aplikasi.bat          buka aplikasi (halaman web lokal); pakai python\ bawaan bila ada
pasang.bat            pemasangan sekali per komputer (+ shortcut); dipanggil Setup dengan /setup
jalankan.bat          versi terminal
buat_paket.bat        membuat ZIP rilis + Setup.exe (mencap nomor versi otomatis)
buat_akun.bat         akun mode lokal (tidak dipakai di login online)
pengaturan.txt        pengaturan lanjutan
inti/                 kode program (server, alur, portal, form, konverter, pembaruan, halaman)
inti/login_online.json  alamat & kunci PUBLISHABLE Supabase (aman publik)
template/             template Excel data peserta
supabase/             skema SQL & panduan menyalakan login online (tidak ikut ZIP)
pemasang/             naskah Inno Setup + penyiap Python bawaan (tidak ikut ZIP)
panduan/              sumber Panduan CKG Robot.pdf (python panduan/cetak.py) (tidak ikut ZIP)
uji/                  Supabase tiruan untuk uji login & pembaruan (tidak ikut ZIP)
CLAUDE.md             aturan & cara kerja untuk Claude Code (dua PC pengembang)
requirements-dev.txt  pustaka tambahan pengembang
alat/                 alat pengembang: cap_versi, buat_demo_web, buat_admin_web, buat_template_sekolah, buat_ikon
```

Tidak ada di repo (lihat `.gitignore`): `data/`, `hasil/`, `mentah/`, `.profil-browser*/`, `akun.dat`,
cadangan, dan skrip perapian khusus sekolah — semuanya berisi data peserta atau sesi login.

## Arti status

| Status | Artinya |
|---|---|
| `tuntas` | selesai penuh, form terisi |
| `sudah_pelayanan` | portal menyatakan peserta sudah dilayani |
| `ckg_sekolah` / `ckg_umum` | sudah diperiksa lewat jalur CKG yang lain |
| `puskesmas_berbeda` | sudah diperiksa puskesmas lain |
| `sekolah_berbeda` / `kelas_berbeda` | murid tercatat di sekolah/kelas lain |
| `tidak_valid` | portal menolak datanya (NIK/nama/tanggal lahir) — betulkan dulu |
| `tidak_ditemukan` | tidak ada di daftar — periksa NIK, sekolah, kelas |
| `gagal_*`, `tanpa_tiket`, `layanan_sebagian` | gagal sementara — bisa diulang |

## Pengaturan yang sering dipakai (`pengaturan.txt`)

| Kunci | Bawaan | Arti |
|---|---|---|
| `lewati sudah selesai` | ya | peserta yang sudah tuntas dilewati |
| `ulang tidak valid` | tidak | coba lagi peserta yang ditolak portal |
| `percobaan ulang` | 3 | percobaan per peserta saat gagal sementara |
| `ulang di akhir batch` | 1 | putaran ulang untuk yang tetap gagal (0 = mati) |
| `berhenti setelah gagal` | 3 | batch berhenti setelah N gagal beruntun |
| `kelurahan domisili sekolah` | (kosong) | cadangan domisili murid bila Lokasi Sekolah di portal kosong |

## Rilis & pembaruan (admin)

1. Ubah kode → uji → `buat_paket.bat` (jawab **t**: tanpa data peserta). Nomor versi `tahun.bulan.tanggal.jammenit`
   dicap otomatis ke `inti/config.py`. Bila **Inno Setup 6** terpasang, `CKG-Robot-Setup-<tanggal>.exe` ikut dibuat
   (Python embeddable diunduh sekali dari python.org ke `pemasang/cache/`, versi sama dengan Python komputer ini).
2. Aplikasi → **Kelola Petugas → Terbitkan pembaruan** → pilih ZIP, tulis catatan.
   Setup diunggah lewat **Panel admin website** (tidak wajib tiap rilis — Setup lama langsung ditawari pembaruan).
3. Commit & push repo ini, catat perubahan di **Riwayat perubahan** di bawah.
4. Bila tampilan berubah: `python alat\buat_demo_web.py` dan/atau `python alat\buat_admin_web.py`, lalu push repo website.

SQL Supabase dijalankan sekali, berurutan: `skema.sql` → `tambahan-website.sql` →
`tambahan-website-2-aturan-berkas.sql` → `tambahan-pembaruan.sql` → `tambahan-pemantauan.sql` →
`tambahan-ubah-email.sql`
(panduan: `supabase/PANDUAN SUPABASE.md`).

---

## Riwayat perubahan

### 14 Okt 2026 — skrining TBC diisi sesuai data (belum dirilis, menunggu uji di portal)
- **Temuan skrining TBC dijawab sesuai data**, bukan lagi Normal/Tidak untuk semua: batuk (lebih/kurang dari
  2 minggu), BB turun, demam, keringat malam, kelenjar, radiografi toraks + **hasil rontgen** (Normal / Abnormal TBC /
  Abnormal non TBC), kontak TBC (serumah/erat), jenis TBC indeks, metode dahak, serumen, tajam penglihatan, karies,
  gigi hilang, merokok (+ jenis rokok, paparan asap), riwayat DM. Bunyi pertanyaan & pilihan dibaca dari form portal.
- Pengekstrak skrining TBC menulis kolom 35 `rinci`; `form.aturan_rinci()` memetakannya ke pertanyaan (radio,
  dropdown, kolom angka). Pilihan yang tidak ditemukan dibiarkan kosong (terlapor), tidak ditebak. Pertanyaan tidak
  wajib tanpa data (lama merokok, batang/hari, kadar CO) dikosongkan, tidak diisi 0.
- Isian wajib yang tidak ada di berkas mengikuti keputusan pengguna: indeks Bakteriologis, dahak "Tidak dilakukan",
  perokok = rokok konvensional & terpapar asap, visus Snellen Normal, riwayat DM dijawab Tidak.
- NIK dibuang bila tanggal lahir **dan** jenis kelamin sama-sama tidak cocok (mungkin NIK orang lain); pesan
  kode provinsi tidak sah diperjelas; peserta "tidak hadir" dilewati.
- Pengisian form: lintasan ketiga untuk pertanyaan lanjutan, berhenti begitu tidak ada yang baru.
- Komentar kode: dua nama peserta yang tertinggal disamarkan.
- **Internet putus saat percobaan ulang tidak lagi menghentikan browser pekerja.** Galat di jalur "lanjutkan dari
  daftar layanan" (percobaan ke-2/3 dan putaran ulang akhir batch) kini dicatat `error`, ditunggu jaringannya, lalu
  dicoba lagi. Sebelumnya `net::ERR_NAME_NOT_RESOLVED` menghentikan kedua browser di 76/81 (uji jalan 14 Okt).
- Soal yang sengaja dikosongkan (mis. lama merokok) tidak lagi dilaporkan "soal radio kosong".
- Uji jalan 14 Okt (data TBC 13 Okt): 26 tuntas, 47 sudah_pelayanan, form terkirim sesuai data.

### 2026.10.13.0840
- **Admin mengubah data petugas**: Kelola Petugas → Lainnya → *Ubah data petugas* (nama, puskesmas, no. HP,
  email), di aplikasi dan di website (`kelola/`). Email ditolak bila formatnya salah atau sudah dipakai akun lain;
  mengubah email meminta konfirmasi.
- SQL baru **`supabase/tambahan-ubah-email.sql`** (`admin_ganti_email`) — jalankan sekali; tanpa itu nama/puskesmas/
  no. HP tetap bisa diubah, email memberi petunjuk menjalankan SQL.
- Server uji (`uji/mock_supabase.py`) meniru `admin_ganti_email`; Panduan PDF & PANDUAN SUPABASE §12.

### 2026.10.12.2216
- **Pengumuman admin langsung sampai**, juga selagi robot bekerja: `/api/kabar` ditanya halaman tiap 2 menit,
  kotak *Pengumuman baru dari admin* + notifikasi Windows + judul tab berkedip, sekali per isi (diingat per
  browser). Pita pengumuman ikut berganti/hilang. Tanpa perubahan SQL.
- Akun dinonaktifkan admin di tengah batch → pita & kotak merah; batch berjalan tetap selesai, batch baru ditolak.
- Izin notifikasi diminta saat petugas menekan *Buka browser & mulai*.
- Demo website, petunjuk Kelola Petugas, dan Panduan PDF disesuaikan.

### 12 Okt 2026 — kerja dari dua PC (tanpa rilis)
- `CLAUDE.md` di kedua repo: aturan data, alur rilis, jebakan lingkungan, langkah PC pengembang baru.
- Sumber panduan PDF dipindah ke `panduan/` (sebelumnya hanya di folder sementara), server uji ke `uji/`,
  `requirements-dev.txt`. Ketiganya tidak ikut ZIP maupun pembaruan.

### 2026.10.12.2131
- **Panduan PDF** (19 halaman) diperbarui untuk Setup: langkah Setup bergambar, peringatan SmartScreen,
  ikon & folder data, tabel masalah, dan cara admin mengunggah Setup.

### 2026.10.12.2121
- **Setup.exe** untuk petugas baru: Python ikut dibundel, ikon & Start Menu, uninstall dari Control Panel.
  Dibuat otomatis oleh `buat_paket.bat` (Inno Setup 6), ~13 MB.
- **Ikon CKG Robot** (kotak hijau toska + palang putih, sama dengan logo website) untuk shortcut, Setup, dan tab browser.
- **Shortcut Desktop & Start Menu** untuk pemasangan ZIP: dibuat `pasang.bat`, atau otomatis sekali setelah pembaruan
  (tidak menimpa shortcut milik salinan CKG Robot lain; tidak muncul lagi bila sengaja dihapus).
- Jendela hitam **mengecil sendiri** ke taskbar setelah aplikasi siap; muncul lagi bila ada galat. Ikon diklik saat
  aplikasi masih jalan → halamannya dibukakan.
- `aplikasi.bat` memasang pustaka yang kurang **otomatis** (tidak lagi menyuruh menjalankan `pasang.bat`).
- Pembaruan tidak pernah menyentuh `python\` bawaan dan `pemasang\`.
- Website: tombol unduh utama → Setup (cadangan ZIP bila Setup belum diunggah), baris unggah Setup di Panel admin,
  langkah pemasangan & tanya jawab baru.

### 2026.10.12.1458
- Nama & NIK peserta sungguhan di komentar kode **disamarkan** sebelum repo diterbitkan
  (hanya komentar/dokumentasi, logika tidak berubah).
- Repo GitHub `ckg-robot` dibuat; README berisi fitur & riwayat ini.

### 2026.10.12.1422
- **Template DATA SISWA untuk sekolah** — NIK teks + validasi, kolom *Cek NIK*, warna, lembar Petunjuk
  (diuji di Excel sungguhan).
- **Konverter menahan murid tanpa hasil pemeriksaan**; kolom yang diisi nilai bawaan disebut di laporan;
  centang *Ikutkan murid tanpa hasil pemeriksaan*.
- **Putaran ulang di akhir batch** untuk peserta yang tetap gagal sementara.
- **Laporan sekolah**: lembar Rekap per Kelas, Perlu Tindakan, Hb Rendah.
- **Rekap pemakaian** (angka saja) ke Supabase + kartu di Kelola Petugas dengan peringatan lonjakan gagal.
- **Penjaga Supabase harian** (GitHub Actions di repo website) + **unduh daftar petugas** (cadangan CSV).
- **Kelola Petugas di website** (`/kelola/`, khusus admin, rapi di HP).

### 2026.10.12.1320
- **Panduan PDF baru** (18 halaman) untuk login online: daftar akun, persetujuan admin, pembaruan dari
  aplikasi, bagian khusus admin; semua gambar baru dengan data rekaan. `PANDUAN PETUGAS.md` disesuaikan.

### 2026.10.07.2058
- **Nomor versi** di kepala aplikasi dan tombol **Periksa pembaruan**; pemeriksaan otomatis tiap jam.

### 2026.10.07.2020
- **Pembaruan dari dalam aplikasi**: terbitkan dari Kelola Petugas, pita *Versi baru tersedia*,
  *Perbarui sekarang* (cek ukuran & SHA-256, versi di ZIP harus sama, cadangan `cadangan-versi/`,
  batal otomatis bila gagal di tengah, `aplikasi.bat.baru` ditukar saat dibuka berikutnya, mulai ulang sendiri).
- Versi di bawah *versi minimal* tetap bisa masuk tetapi tidak bisa memulai pekerjaan.
- `buat_paket.bat` mencap nomor versi otomatis.

### 2026.10.07
- **Login online lewat Supabase**: daftar → disetujui admin; periksa izin saat masuk & mulai; batas komputer;
  versi minimal; pengumuman; halaman **Kelola Petugas**; `jalankan.bat` ikut wajib login.
- **Website** ckg-robot.netlify.app: halaman berlogin, unduhan dari penyimpanan privat, demo interaktif.
- Template contoh memakai NIK palsu (sebelumnya ada contoh dengan identitas sungguhan).
- Nama di data yang berupa angka didaftarkan lewat **Cek NIK** (nama dari Dukcapil).
- Domisili murid: bila *Lokasi Sekolah* di portal kosong, wilayah dipilih bertingkat
  (pengaturan *kelurahan domisili sekolah*).
- Form yang ditolak portal berulang kali: pesan galatnya dibaca & dicatat, pengiriman dihentikan.

### 6 Okt 2026
- **Penanganan 429 Too Many Requests** dan layar 502/503/504.
- **Halaman tertahan sesudah Kirim** dipulihkan (form terisi dikirim, kosong diisi, daftar dilanjutkan).
- "Daftar layanan kosong" ternyata masih di halaman form → form diisi dulu.
- NIK bukan 16 digit ditolak sebelum dikirim ke portal.
- Form **Kebugaran Jasmani** (kini radio) memakai nilai dari data, bukan selalu "Baik sekali".

### 2–5 Okt 2026
- **Tampilan aplikasi baru** (penunjuk langkah, kartu alur, panel samping).
- Batas "25 peserta" dicabut (diuji 1.000); nomor data awal `1-100`.
- **Panduan PDF** + tombol **📖 Baca Panduan** (bisa dibuka tanpa masuk).
- Konverter memilih lembar data dan melewati lembar Laporan/Rekap/Perlu Dicek; berkas gabungan → satu CSV per lembar.

### 29 Sep 2026 — portal berubah
- Pendaftaran perorangan jadi 2 halaman (tombol *Daftarkan*); status Nakes "Selesai/Belum/Sedang Pemeriksaan";
  kelompok layanan bisa dilipat; konfirmasi hadir tidak lagi diperlukan untuk dewasa/lansia (sekolah tetap);
  kalender tanpa kuota. Robot menerima bentuk lama **dan** baru.

### Agustus – September 2026
- **CKG Sekolah** jalan ujung ke ujung (SD–SMA): pencarian murid per sekolah & kelas, konfirmasi hadir,
  nomor form khusus sekolah, status `sekolah_berbeda` / `kelas_berbeda` / `puskesmas_berbeda` / `ckg_umum`.
- **Konverter Excel** di aplikasi: register sekolah, skrining TBC, buku kunjungan, bentuk bebas; balita & balita tanpa NIK.
- **Beberapa pekerja** (browser) sekaligus dengan profil terpisah; **Unduh Excel**; **Buat Laporan**.
- Akun aplikasi lokal (PBKDF2), pembatas percobaan masuk.
- Pengulangan otomatis untuk kegagalan sementara; alur *sapu tab Selesai* dan *konfirmasi hadir*.

### 9–10 Agustus 2026 — versi Playwright siap produksi
- Pengganti macro UI.Vision. Dewasa/Lansia diuji 100 peserta: 91 beres, 9 ditolak portal karena data,
  nol kegagalan program. Aplikasi web lokal, dua alur (pendaftaran / pelayanan), template Excel,
  `ambil_data_srq.py`, `buat_paket.bat`.

### Juli 2026 — era macro UI.Vision
- Macro CKG Dewasa (V7), Remaja, dan CKG Sekolah berbasis UI.Vision — dasar seluruh temuan portal yang
  kemudian dipindahkan ke versi Playwright.
