# Panduan Petugas — CKG Robot

Alat ini mengisi pendaftaran dan pemeriksaan CKG di portal Sehat Indonesiaku
secara otomatis. Kamu tetap yang login dan yang menentukan datanya; robot yang
mengetik dan mengklik.

---

## BAGIAN 1 — Pemasangan (sekali saja)

**1. Unduh Setup CKG Robot**

Masuk ke **ckg-robot.netlify.app**, klik **Unduh CKG Robot**. Berkasnya
`CKG-Robot-Setup.exe`. Python sudah termasuk di dalamnya — tidak perlu
memasang Python sendiri.

**2. Jalankan Setup**

Klik ganda berkasnya, lalu **Lanjut → Pasang**. Setup mengunduh pustaka dan
browser robot (butuh internet, sekitar 2–5 menit; ada jendela hitam yang
menutup sendiri bila selesai).

> Bila muncul **"Windows protected your PC"**, klik **More info** lalu
> **Run anyway**. Windows memperingatkan semua program tanpa sertifikat
> penerbit berbayar — bukan tanda berbahaya. Unduh Setup hanya dari website.

**3. Ikon CKG Robot**

Setelah selesai ada ikon **CKG Robot** di Desktop dan Start Menu. Di Start
Menu juga ada **CKG Robot - folder data** untuk membuka folder `data\`,
`hasil\`, dan `template\`.

Chrome tidak wajib. Kalau ada, itu yang dipakai; kalau tidak, browser cadangan
yang dipasang Setup.

> **Masih memakai versi ZIP?** Tidak perlu memasang Setup. Perbarui saja
> lewat tombol **Perbarui** di aplikasi — ikon CKG Robot di Desktop muncul
> sendiri setelah pembaruan. (Cara lama ZIP: pasang Python dengan centang
> "Add Python to PATH", ekstrak ZIP ke folder tetap, klik ganda `pasang.bat`.)

**4. Akun CKG Robot**

Aplikasi memakai **login online**: akunnya sama dengan akun website
**ckg-robot.netlify.app** (email + kata sandi). Belum punya? Daftar di website
atau lewat **Daftar akun baru** di halaman masuk aplikasi, lalu tunggu
**disetujui admin**. `buat_akun.bat` tidak dipakai lagi.

> Akun ini **bukan** akun portal Sehat Indonesiaku. Lupa kata sandi? Minta
> admin menggantinya dari halaman Kelola Petugas.

**Versi baru** dipasang dari dalam aplikasi: tekan **Perbarui sekarang** bila
muncul pita "Versi baru tersedia". Tidak perlu mengunduh ZIP lagi.

---

## BAGIAN 2 — Menyiapkan data peserta

**5. Ambil template**

Buka folder `template\`, pilih yang sesuai:

| Template | Untuk |
|---|---|
| `Template CKG SEKOLAH.xlsx` | murid SD sampai SMA |
| `Template DEWASA-LANSIA (parameter).xlsx` | dewasa/lansia, belum ada angka hasil ukur |
| `Template DEWASA-LANSIA (real data).xlsx` | dewasa/lansia, angka hasil ukur sudah ada |

**6. Isi di Excel, lalu simpan sebagai CSV**

`File → Save As → CSV (Comma delimited)`, taruh berkasnya di folder **`data\`**.

Yang perlu diperhatikan:

* **Jangan mengubah urutan atau jumlah kolom.** Program mengenali data dari
  posisi kolomnya, bukan dari judulnya.
* Kolom NIK dan Tanggal Lahir sudah diatur formatnya — NIK 16 digit tidak akan
  terpotong, dan tanggal apa pun bentuk ketikannya akan menjadi `dd/mm/yyyy`.
* Untuk CKG Sekolah, **nama sekolah harus sama persis dengan tulisan di
  portal**. Contoh: portal menulis `SMP KELUARGA KUSUMA MARSUDIRINI`, bukan
  nama panjang dengan "Tanjung Priok" di belakangnya.

---

## BAGIAN 3 — Menjalankan (setiap kali dipakai)

**7. Klik ikon CKG Robot di Desktop**

Halaman aplikasi muncul sendiri di browser, dan jendela hitamnya mengecil ke
taskbar — **jangan ditutup selama bekerja**. Masuk dengan akun yang tadi kamu
buat. Ikonnya diklik lagi padahal aplikasi masih jalan? Halamannya dibukakan
lagi; tidak ada yang rusak.

**8. Pilih pekerjaannya**

| Pilihan | Isi |
|---|---|
| **Jenis CKG** | biarkan "Ikuti isi berkas" — program mengenalinya sendiri |
| **Alur CKG** | tiga pilihan — lihat tabel di bawah |
| **Berkas data** | berkas CSV yang tadi kamu taruh di `data\` |
| **Nomor data** | satu nomor, rentang (`1-1000`), atau gabungan (`1-500, 640`) |
| **Jumlah pekerja** | 1 browser. Naikkan hanya bila kamu punya beberapa akun puskesmas |

> **Beberapa pekerja sekaligus.** Tiap pekerja membuka browsernya sendiri dan
> harus **dilogin sendiri dengan akun puskesmas yang BERBEDA** — sesi login
> menempel pada browsernya. Datanya dibagi berselang-seling, jadi tidak ada
> peserta yang dikerjakan dua kali.
> Jangan memakai satu akun yang sama di dua browser: belum pernah diuji, dan
> risikonya pendaftaran ganda.

**Memilih alur:**

| Alur | Untuk berkas seperti apa |
|---|---|
| **Pendaftaran → Selesai** | semuanya peserta baru. Yang dijawab portal "sudah menerima layanan" dilewati begitu saja — paling cepat |
| **Pendaftaran → Pelayanan → Selesai** | bercampur: sebagian belum terdaftar, sebagian sudah hadir tapi formnya belum diisi. Yang "sudah menerima layanan" **dilanjutkan** lewat halaman pelayanan. Lebih lambat ±30 detik untuk tiap peserta seperti itu |
| **Pelayanan → Selesai** | semuanya sudah terdaftar, tinggal diisi formnya. Tanpa pendaftaran sama sekali. Peserta yang **formnya sudah diinput** langsung dilewati tanpa dibuka |

> Portal menjawab "sudah menerima layanan" untuk **dua keadaan berbeda**:
> peserta yang pemeriksaannya memang tuntas, dan peserta yang baru hadir tapi
> formnya kosong. Dari halaman pendaftaran keduanya tidak bisa dibedakan —
> hanya halaman pelayanan yang tahu. Itulah kenapa perlakuannya jadi pilihan.

**9. Tekan "Buka browser & mulai"**

Jendela browser baru terbuka di halaman portal.

**10. Login sendiri di jendela itu**

Pakai akun puskesmasmu. Ada captcha, jadi harus dikerjakan manusia.
Sesudah masuk, kembali ke halaman aplikasi dan tekan
**"Saya sudah login — lanjutkan"**.

**11. Tunggu**

Kemajuan, tabel hasil, dan catatan prosesnya berjalan sendiri.
Satu peserta penuh sekitar **3–4 menit**.

**12. Unduh hasilnya**

Di atas tabel ada rekap jumlah tiap status. Tekan **⬇ Unduh Excel** untuk
mengunduhnya: lembar **Hasil** berisi No, NIK, Nama, Tanggal Lahir, dan Status
dengan warna; lembar **Rekap** berisi jumlah tiap status dan totalnya.

> **Unduh dulu sebelum menjalankan batch berikutnya.** Tabel hasil diganti
> setiap kali kamu menekan "Buka browser & mulai" lagi. Riwayat lengkapnya
> tetap tersimpan sebagai CSV di folder `hasil\`.

### Alur khusus: Sapu Belum Pemeriksaan (tanpa berkas)

Untuk peserta **dewasa/lansia (≥ 18 tahun)** yang sudah terdaftar dan ada di tab
**Belum Pemeriksaan** halaman **Pelayanan**, tapi pemeriksaannya belum diinput
dan tidak ada berkas datanya. Robot mengambil peserta dari atas daftar (anak
dilewati), membaca NIK & jenis kelamin di halaman detailnya, lalu mengerjakannya
seperti **Pelayanan → Selesai**: Mulai Pemeriksaan, semua form, Selesaikan Layanan.

1. Pada **Alur CKG**, klik kartu **Sapu Belum Pemeriksaan**.
2. Isi **Jumlah peserta** (1–500 per jalan) dan **Jumlah browser** (1–10).
3. Pilih jawaban untuk semua peserta: **gizi** (Normal/Kurus/Gemuk), **tensi** &
   **gula** (Normal/Tinggi/Rendah), **merokok**, **batuk**, **kontak TBC**,
   **rontgen**, **tajam penglihatan**, **serumen**, **karies**, **gigi hilang**,
   **geriatri**. Bawaannya semua normal; yang diganti berwarna kuning.
4. Tekan **Buka browser & mulai**, login portal di tiap browser, lalu **Saya sudah login**.

Angka BB, TB, lingkar perut, tensi, dan gula diambil dalam rentang parameter yang
dipilih (sama dengan Template DEWASA-LANSIA parameter), tetap untuk NIK yang sama.
Pertanyaan lain dijawab normal/negatif; riwayat DM dijawab Tidak.

> **Jawaban berlaku sama untuk SEMUA peserta dalam satu kali jalan.** Pakai hanya
> bila hasil peserta memang sesuai; yang berbeda jalankan terpisah atau input manual.

> **Beberapa browser = beberapa akun.** Tiap browser login dengan akun puskesmas
> yang BERBEDA. Jumlah peserta dibagi rata dan tiap peserta hanya dikerjakan satu
> browser.

Coba dulu dengan `mode uji = ya`: pada alur ini robot hanya mencatat angka &
jawaban yang akan diisi, tanpa menekan Mulai Pemeriksaan.

### Alur khusus: Tatalaksana Gigi (tanpa berkas)

Untuk peserta dengan hasil **gigi berlubang** yang tatalaksananya **sudah
diberikan** tapi belum dicatat di portal. Tidak perlu berkas data: robot
membuka **Tatalaksana → Daftar Tatalaksana**, memasang filter
**2026 · Gigi · Gigi berlubang**, lalu mengerjakan tab
**Belum Pencatatan Tatalaksana** dari atas.

1. Pada **Alur CKG**, klik kartu **Tatalaksana Gigi**.
2. Isi **Jumlah peserta** (1–500 per jalan). Yang sudah dicatat keluar dari
   daftar portal, jadi menjalankan lagi otomatis melanjutkan.
3. Periksa **Jawaban form tatalaksana** — dipakai sama untuk semua peserta.
   Bawaannya: Diagnosis Ya **K02**, Tindakan Ya **23.4**, Obat Tidak (tidak ada
   indikasi medis), Edukasi Ya, Kontrol/rujuk Tidak (Lainnya). Yang diganti dari
   bawaan berwarna kuning.
4. Tekan **Buka browser & mulai**, login portal, lalu **Saya sudah login**.
   Alur ini selalu satu browser, sekitar **10 detik** per peserta.

> **Jawaban harus sesuai tatalaksana yang benar-benar diberikan.** Robot tidak
> memeriksa rekam medis. Kalau sebagian peserta mendapat tatalaksana berbeda,
> jalankan terpisah dengan jawaban yang sesuai, atau catat manual. Obat "Ya" dan
> "Kontrol rutin" tidak tersedia di aplikasi (perlu resep/tanggal).

Robot mencocokkan NIK di halaman detail sebelum mengisi, mengirim form **hanya
bila** semua isian tercatat di form, dan menyatakan **tuntas** hanya bila status
di portal menjadi **Selesai tatalaksana**. Hasilnya lewat **⬇ Unduh Excel**.

> **Satu akun portal = satu tempat login.** Selama robot bekerja, jangan membuka
> portal dengan akun yang sama di browser atau komputer lain.

---

## Arti status di tabel hasil

| Status | Warna | Artinya |
|---|---|---|
| `tuntas` | hijau | selesai penuh, semua form terisi |
| `sudah_pelayanan` | kelabu | portal menyatakan peserta sudah dilayani |
| `ckg_sekolah` | hijau kebiruan | sudah diperiksa lewat jalur CKG Sekolah, bukan CKG Umum |
| `puskesmas_berbeda` | ungu | sudah diperiksa PUSKESMAS LAIN — keterangannya menyebut puskesmas dan tanggalnya |
| `sekolah_berbeda` | ungu | sudah selesai diperiksa, tapi di SEKOLAH LAIN — keterangannya menyebut sekolah, kelas, dan puskesmasnya |
| `kelas_berbeda` | ungu | sekolahnya sama, kelasnya yang berbeda dari yang tertulis di CSV |
| `tidak_valid` | oranye | portal menolak datanya |
| `tidak_ditemukan` | kuning | tidak ada di daftar — periksa NIK, sekolah, atau kelasnya |
| `gagal_...` | merah | ketemu tapi langkahnya gagal; boleh dijalankan ulang |
| `sudah_tatalaksana` | kelabu | (Tatalaksana Gigi) status di portal sudah "Selesai tatalaksana" — dilewati |
| `gagal_isi` | merah | (Tatalaksana Gigi) isian form tidak cocok dengan jawaban yang dipilih — form **tidak dikirim** |

Yang hijau, kelabu, dan ungu tidak akan dikerjakan lagi kalau kamu menjalankan
ulang — untuk yang ungu, muridnya memang sudah diperiksa; yang perlu dibetulkan
nama sekolah/kelas di datanya. Yang merah dan kuning akan dicoba lagi.

---

## Aturan yang menghemat waktumu

**Satu kali jalan boleh sampai ratusan peserta** (sudah diuji sampai 1000).
Batch berhenti sendiri setelah 3 kegagalan beruntun. Tutup browsernya, jalankan
lagi dengan **rentang yang sama** — yang sudah selesai dilewati otomatis.

**Jangan utak-atik jendela browser yang sedang dikerjakan robot.**
Memindahkan, menutup, atau menumpuknya dengan jendela lain bisa membuat
langkahnya meleset.

**Komputermu harus menyala selama pekerjaan berjalan.**
Robotnya jalan di komputermu, bukan di server.

---

## Kalau ada masalah

| Yang terjadi | Lakukan |
|---|---|
| "Python tidak ditemukan" (versi ZIP) | Pasang ulang Python, centang "Add Python to PATH" — atau pakai Setup dari website |
| "Playwright belum terpasang" | Jalankan `pasang.bat` sekali lagi |
| Tombol Unduh Excel bilang openpyxl belum ada | Jalankan `pasang.bat` sekali lagi |
| Halaman aplikasi tidak terbuka sendiri | Buka browser, ketik `localhost:8765` |
| Diminta login terus | Jangan tutup jendela browsernya di tengah batch |
| Lupa kata sandi akun CKG Robot | Minta admin menggantinya (Kelola Petugas) |
| "Akun belum disetujui admin" | Kabari admin, lalu masuk lagi setelah disetujui |
| "Versi ini sudah tidak boleh dipakai" | Tekan **Perbarui sekarang** di pita merah |
| "Terlalu banyak percobaan" | Salah sandi 5 kali. Tunggu 5 menit |
| Banyak peserta `tidak_ditemukan` | Periksa NIK-nya; untuk murid, periksa juga nama sekolah dan kelasnya |
| Batch berhenti sendiri | Normal setelah 3 gagal beruntun. Tutup browser, jalankan lagi dengan rentang sama |

Kalau ada peserta yang gagal dan sebabnya tidak jelas, tangkapan layar saat
gagal tersimpan otomatis di `hasil\gagal\` — kirimkan berkas itu beserta
catatan prosesnya.

---

## Yang TIDAK dilakukan alat ini

* Tidak menyimpan atau membaca kata sandimu. Login selalu kamu sendiri.
* Tidak mengubah data yang sudah ada di portal selain yang memang diisi.
* Tidak bisa dijalankan dari komputer lain — halaman aplikasi hanya mengendalikan
  robot yang berjalan di komputer tempat `aplikasi.bat` dijalankan.
