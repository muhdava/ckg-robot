# Template data peserta

Pilih satu sesuai peserta yang mau dikerjakan, isi di Excel, lalu **Simpan
Sebagai → CSV (Comma delimited)** dan taruh berkas CSV-nya di folder `data\`.

Jangan mengubah urutan atau jumlah kolomnya — program mengenali tata letak dari
posisi kolom, bukan dari judulnya.

| Template | Kolom | Untuk |
|---|---|---|
| `Template CKG SEKOLAH.xlsx` | 25 | murid SD sampai SMA |
| `Template DATA SISWA (untuk sekolah).xlsx` | 16 | **dikirim ke operator sekolah**: NIK terkunci teks, kolom "Cek NIK" otomatis, lembar Petunjuk. Hasilnya langsung lewat "Siapkan data dari Excel" |
| `Template CKG BALITA.xlsx` | 18 | balita 0-6 tahun yang sudah ber-NIK |
| `Template CKG BALITA TANPA NIK.xlsx` | 21 | bayi yang NIK-nya belum terbit |
| `Template DEWASA-LANSIA (parameter).xlsx` | 33 | dewasa/lansia, tanpa angka hasil ukur |
| `Template DEWASA-LANSIA (real data).xlsx` | 34 | dewasa/lansia, dengan angka hasil ukur dan No HP |

## Kalau datanya masih mentah

Tidak perlu menyalin manual ke template. Buka kartu **"Ubah berkas mentah
(.xlsx) jadi CSV siap jalan"** di aplikasi, pilih berkasnya, lalu pilih
sasarannya:

| Sasaran di aplikasi | Kolom | Menghasilkan bentuk seperti |
|---|---|---|
| CKG Sekolah | 24 | `Template CKG SEKOLAH.xlsx` |
| Balita 0-6 th | 18 | `Template CKG BALITA.xlsx` |
| Balita TANPA NIK | 21 | `Template CKG BALITA TANPA NIK.xlsx` |
| Dewasa/Lansia (parameter) | 33 | `Template DEWASA-LANSIA (parameter).xlsx` |
| Dewasa/Lansia (real data) | 34 | `Template DEWASA-LANSIA (real data).xlsx` |

Kolom dipetakan dari JUDULNYA, jadi berkas posyandu yang cuma punya NIK, Nama,
Tanggal Lahir, Jenis Kelamin, dan Alamat pun bisa dipakai - sisanya diisi nilai
bawaan, dan aplikasi menyebutkan persis kolom mana saja yang memakai bawaan.

Dua sasaran Dewasa/Lansia itu bedanya cuma tiga kolom: **real data** punya
No HP, Berat Badan, dan Tinggi Badan. Pilih **real data** bila berkasnya
membawa angka hasil ukur, **parameter** bila tidak - di sana angkanya
diturunkan sendiri dari kata `Normal`.

Sasaran **Dewasa/Lansia** dan **Balita TANPA NIK** harus dipilih sendiri,
tidak ditebak otomatis: kolom identitasnya sama persis dengan sasaran lain,
jadi menebaknya justru berisiko salah. Untuk Dewasa/Lansia, aplikasi juga
memperingatkan bila ada baris yang umurnya di bawah 60 tahun - berguna untuk
menangkap berkas yang salah pilih sasaran.

## Parameter atau real data?

**Parameter** dipakai kalau kamu belum punya angka hasil pemeriksaan. Kolomnya
diisi kata — `Normal`, `Rendah`, `Tinggi`, `Kurus`, `Gemuk` — lalu program
menurunkan angkanya sendiri, tetap sama tiap kali dijalankan untuk orang yang
sama.

**Real data** dipakai kalau angkanya sudah ada: gula darah, tekanan darah,
berat, dan tinggi diisi angka sungguhan dan dipakai apa adanya.

Keduanya dikenali otomatis — tidak ada pengaturan yang perlu diubah.

## Khusus CKG Sekolah

Kolom 15–19 (Berat, Tinggi, Gula Darah, Tekanan Darah, Hemoglobin) menerima
**angka sungguhan** kalau sekolahnya punya. Kalau diisi kata `Normal`, angkanya
diturunkan dari NIK — tetap konsisten, tapi rumusnya dibuat untuk orang dewasa,
sehingga untuk anak sekolah hasilnya bisa kelewat besar (mis. tekanan 130-an).
Untuk murid, mengisi angkanya sendiri jauh lebih baik.

Nama sekolah harus **sama persis** dengan tulisan di portal. Contoh: portal
menulis `SMP KELUARGA KUSUMA MARSUDIRINI`, bukan nama panjang dengan
"Tanjung Priok" di belakangnya.

## Template CKG BALITA.xlsx

Untuk peserta **0-6 tahun**. Alur pendaftarannya sama dengan Dewasa/Lansia,
bedanya portal memunculkan bagian **Data Wali** begitu tanggal lahir terisi -
robot mengisinya dari data peserta sendiri.

**Berat dan tinggi badan tidak diisi di sini.** Keduanya diturunkan dari umur
dan jenis kelamin memakai tabel WHO. Yang kamu isi hanya parameternya:

| Kolom | Pilihan | Artinya |
|---|---|---|
| Berat Lahir | Kurus / Normal / Gemuk | 2000-2500 / 2600-3500 / 3600-4200 **gram** |
| Berat Saat Ini | Kurus / Normal / Gemuk | sama, kolom kedua form Berat Lahir |
| Status Gizi | Kurus / Normal / Gemuk | 0,80-0,90x / 0,95-1,05x / 1,15-1,30x berat ideal |
| Riwayat Imunisasi | Ya / Tidak | dipakai form Hepatitis B dan Imunisasi Rutin |

Bayi yang **NIK-nya belum terbit** tidak bisa lewat template ini - pakai
`Template CKG BALITA TANPA NIK.xlsx` di bawah. Nomor sementara dari klinik pasti
ditolak portal.

### Kolom NIK, Tanggal Lahir, dan No HP sudah dikunci formatnya

Sampai baris 1004, ketiganya tidak bisa dirusak Excel: NIK 16 digit tidak
berubah jadi 3,17203E+15, tanggal apa pun bentuk ketikannya menjadi
`dd/mm/yyyy`, dan angka 0 di depan nomor HP tidak hilang. Penguncian yang sama
sudah dipasang ulang di ketiga template lainnya - sebelumnya format itu hanya
menempel di baris contoh, sehingga baris ke-7 dan seterusnya tetap rusak saat
data ditempel banyak sekaligus.

## Template CKG BALITA TANPA NIK.xlsx

Untuk bayi yang **NIK-nya belum terbit** - di buku kunjungan biasanya tertulis
"Bayi Nyonya ...". Robot mendaftarkannya lewat centang **"Tidak punya NIK"** di
halaman 1, lalu tombol **"Daftarkan tanpa NIK"** di halaman 3. Tidak ada Cek NIK
dan tidak ada "Gunakan Data" - seluruh identitasnya berasal dari berkas ini.

Susunannya 21 kolom, beda dari template balita biasa di dua hal:

1. **Kolom NIK peserta dihapus.** Memang itu intinya.
2. **Data wali jadi WAJIB dan lengkap** - empat kolom berurutan di kolom 5-8
   (NIK, Nama, Tanggal Lahir, Jenis Kelamin), urutannya sama persis dengan blok
   data peserta di sebelah kirinya. NIK, nama, tanggal lahir, dan jenis
   kelamin. Portal menuliskannya sendiri: *"Pengisian data wali wajib bagi
   peserta balita dan yang tidak memiliki NIK"*, dan di jalur ini tidak
   disediakan pilihan "Daftarkan tanpa data wali". NIK wali harus 16 digit;
   kalau tidak, barisnya tidak akan dikenali sebagai balita tanpa NIK sama
   sekali.

**Nomor HP tinggal satu kolom, "No HP Wali"**, dan boleh dikosongkan (dipakai
nomor hotline puskesmas). Di portal nomor itu diketik ke kolom WhatsApp
*peserta*, lalu nomor wali cukup dicentang "Nomor sama dengan peserta" - jadi
satu kolom memang melayani keduanya.

Kolom parameter di ujungnya (Berat Lahir, Berat Saat Ini, Riwayat Imunisasi,
Status Gizi) sama persis dengan template balita biasa, termasuk berat dan tinggi
yang tidak diisi di sini melainkan diturunkan dari tabel WHO.

### Namanya jadi kunci - tulis persis

Peserta ini dicari di daftar portal lewat **namanya**, sebab NIK-nya tidak ada.
Berlaku di dua tempat: konfirmasi hadir di halaman pendaftaran, dan pencarian di
halaman pelayanan. Keduanya menyediakan mode pencarian Nama.

Karena itu nama di kolom **Nama** harus ditulis apa adanya dan konsisten -
itulah satu-satunya pegangan robot atas bayi ini. Kalau ada dua bayi bernama
persis sama di daftar yang sama, robot mengambil yang pertama dan menuliskan
peringatan "PERHATIAN: N baris bernama sama" di berkas hasil, jadi periksa
keterangan itu bila muncul. Membedakan namanya sejak di berkas (mis.
menambahkan nama depan ibunya) jauh lebih aman.
