# Menyalakan login online (Supabase)

Sekali saja, sekitar 15 menit. Folder `supabase\` ini **tidak ikut** paket ZIP
untuk petugas.

## 1. Buat proyek Supabase

1. Daftar/masuk di **supabase.com**, lalu **New project**.
2. Isi nama (mis. `ckg-robot`), buat *database password* (simpan baik-baik;
   tidak dipakai aplikasi), pilih region **Southeast Asia (Singapore)**.
3. Tunggu sampai proyeknya siap (±2 menit).

## 2. Matikan konfirmasi email

**Authentication → Sign In / Providers → Email** → matikan **Confirm email** → Save.

Email bawaan Supabase hanya terkirim ke anggota tim proyek, bukan ke petugas.
Tanpa langkah ini pendaftar tidak akan pernah bisa masuk. Persetujuan admin
menggantikan peran konfirmasi email.

## 3. Pasang tabel dan fungsinya

**SQL Editor → New query** → tempel **seluruh** isi `skema.sql` → **Run**.
Harus muncul *Success. No rows returned*.

## 4. Ambil alamat & kunci publik

**Project Settings → API Keys** (atau tombol **Connect**):

- **Project URL**, mis. `https://abcdxyz.supabase.co`
- **Publishable key** (`sb_publishable_...`) — atau di proyek lama: **anon public** key (`eyJ...`)

> ⚠️ **Jangan** pakai/kirim kunci **secret** / **service_role**. Kunci itu
> membuka seluruh database.

## 5. Nyalakan di aplikasi

Buat berkas `inti\login_online.json`:

```json
{"mode": "online",
 "supabase_url": "https://abcdxyz.supabase.co",
 "kunci_publik": "sb_publishable_..."}
```

Tutup jendela hitam aplikasi, lalu buka lagi `aplikasi.bat`. Halaman masuk
sekarang meminta **Email** dan ada tombol **Daftar akun baru**.

Untuk kembali ke login lama (akun.dat): ganti `"online"` menjadi `"lokal"`,
atau hapus berkasnya.

## 6. Jadikan dirimu admin

1. Di aplikasi, **Daftar akun baru** dengan emailmu.
2. Di Supabase **SQL Editor**, jalankan (ganti emailnya):

   ```sql
   update public.petugas set peran = 'admin', status = 'aktif'
    where email = 'emailmu@contoh.com';
   ```
3. Masuk di aplikasi. Tombol **👥 Kelola Petugas** muncul di kanan atas.

Semua pengelolaan berikutnya dari halaman itu: setujui/tolak pendaftar,
nonaktifkan akun, buatkan akun, ganti sandi yang lupa, lepas komputer lama,
batas komputer per akun, versi minimal, dan pengumuman.

## 7. Bagikan paketnya

Jalankan `buat_paket.bat` seperti biasa — `inti\login_online.json` ikut
terbawa, jadi semua petugas otomatis memakai login online.

## Kalau ada masalah

| Pesan di aplikasi | Penyebab |
|---|---|
| Email belum dikonfirmasi | Langkah 2 belum dilakukan |
| Server login belum disiapkan | `skema.sql` belum dijalankan (langkah 3) |
| Server login tidak menjawab… mungkin sedang di-pause | Proyek gratis tidur setelah seminggu tanpa aktivitas → buka dasbor Supabase, tekan **Restore** |
| Tidak bisa menghubungi server login | Internet komputer itu putus |

**Batasan yang perlu diingat:** kode aplikasi bisa dibaca, jadi orang yang
paham pemrograman tetap bisa melewati pemeriksaan ini. Login online adalah
pintu untuk mengatur siapa yang memakai, bukan pengaman dari pembobol.

## 8. Website berlogin (ckg-robot.netlify.app)

Website memakai akun yang sama. ZIP & PDF disimpan di bucket **privat**
`paket` di Supabase Storage, bukan di Netlify.

1. Jalankan `tambahan-website.sql` di SQL Editor (sekali).
2. Deploy folder `Website CKG Robot` ke Netlify (tab **Deploys** → seret folder).
3. Buka website, masuk sebagai admin → **Panel admin** → unggah
   `CKG-Robot.zip` dan `Panduan-CKG-Robot.pdf`.

Versi baru cukup diunggah ulang lewat Panel admin — tidak perlu deploy ulang
Netlify. Petugas baru bisa mendaftar dari website maupun dari aplikasi.

**Demo interaktif** (`Website CKG Robot\demo\`) dibuat dari `inti\antarmuka.html`
oleh `python alat\buat_demo_web.py`. Jalankan ulang skrip itu setiap kali
tampilan aplikasi berubah, lalu deploy ulang folder website ke Netlify.
Demonya ikut terkunci: hanya akun aktif yang bisa membukanya.

## 9. Aturan akses berkas lewat Dashboard (bila SQL ditolak)

Bila `tambahan-website-2-aturan-berkas.sql` ditolak (*must be owner of table
objects*): **Storage → Policies → bucket `paket` → New policy → For full
customization**, buat empat aturan, Target roles: **authenticated**:

| Nama | Operasi | Definisi |
|---|---|---|
| petugas aktif boleh unduh | SELECT | `bucket_id = 'paket' and public._petugas_aktif()` |
| admin boleh unggah | INSERT | `bucket_id = 'paket' and public._admin()` |
| admin boleh ganti | UPDATE | `bucket_id = 'paket' and public._admin()` |
| admin boleh hapus | DELETE | `bucket_id = 'paket' and public._admin()` |

## 10. Pembaruan aplikasi dari dalam aplikasi

Sekali: jalankan `tambahan-pembaruan.sql` di SQL Editor.

Setiap rilis:
1. Klik ganda `buat_paket.bat` → nomor versi (tahun.bulan.tanggal.jammenit) dicap
   otomatis, ZIP muncul di folder induk.
2. Aplikasi → **👥 Kelola Petugas → Terbitkan pembaruan** → pilih ZIP-nya, tulis
   catatan perubahan → **Unggah & terbitkan**.
3. Petugas melihat pita **"Versi baru … tersedia"** saat masuk berikutnya, lalu
   menekan **Perbarui sekarang**: unduh → cocokkan SHA-256 → cadangkan → pasang →
   aplikasi mulai ulang sendiri. Data, hasil, dan pengaturan.txt tidak disentuh.
4. Agar WAJIB: isi **Versi minimal** dengan versi itu. Versi lama tetap bisa masuk,
   tapi tidak bisa memulai pekerjaan sampai diperbarui.

Jangan unggah ZIP lewat Panel admin website: versi & sidiknya tidak akan tercatat
dan tombol Perbarui di aplikasi petugas menolak paket itu.

Petugas yang memasang versi SEBELUM fitur ini (≤ 2026.10.07) perlu mengunduh ZIP
sekali lagi dari website. Sesudah itu semua lewat tombol.

## 11. Rekap pemakaian, penjaga harian, Kelola Petugas di website

Sekali: jalankan `tambahan-pemantauan.sql` di SQL Editor.

- **Rekap pemakaian** muncul di Kelola Petugas (aplikasi & website): jumlah
  peserta per hari dan per petugas, dengan tanda merah bila >= 30% gagal.
- **Penjaga harian**: repo website berisi `.github/workflows/jaga-supabase.yml`
  yang memanggil fungsi `ping` tiap pagi, supaya proyek gratis tidak tertidur.
  Cek di GitHub → repo `website-ckg-robot` → tab **Actions**. GitHub mematikan
  jadwal bila repo 60 hari tanpa commit - aktifkan lagi di tab yang sama.
- **Kelola Petugas di website**: `https://ckg-robot.netlify.app/kelola/`
  (hanya admin). Bila `inti\admin.html` berubah: `python alat\buat_admin_web.py`,
  lalu commit & push repo website.
- **Cadangan**: tombol **⬇ Unduh daftar** di Kelola Petugas menyimpan daftar
  petugas sebagai CSV. Simpan sesekali.

## 12. Admin mengubah data & email petugas

Sekali: jalankan `tambahan-ubah-email.sql` di SQL Editor.

Kelola Petugas → **Lainnya** → **✎ Ubah data petugas**: nama, puskesmas,
no. HP, dan email. Nama/puskesmas/no. HP sudah jalan tanpa SQL ini (fungsi
`admin_ubah` dari `skema.sql`); **email** butuh fungsi `admin_ganti_email`
karena email adalah nama masuk akun (tabel `auth.users`). Email baru langsung
berlaku; petugas masuk dengan email baru, kata sandinya tetap. Email yang sudah
dipakai akun lain ditolak.
