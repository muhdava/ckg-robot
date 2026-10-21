# CKG Robot — catatan untuk Claude Code

Aplikasi Python + Playwright yang mengisi pendaftaran & pemeriksaan **Cek Kesehatan Gratis** di portal
`sehatindonesiaku.kemkes.go.id` dari data Excel/CSV puskesmas. Dipakai gratis oleh nakes. Pemilik/admin:
akun GitHub **muhdava**. Berbicara dengan pemilik dalam **bahasa Indonesia**. README.md berisi daftar fitur
dan riwayat perubahan lengkap — baca bagian yang relevan sebelum mengubah sesuatu.

Proyek ini dikerjakan dari **dua PC**. Repo ini (`muhdava/ckg-robot`) dan repo website
(`muhdava/website-ckg-robot`, folder saudara `../Website CKG Robot`) adalah satu-satunya yang tersinkron.

## Setiap sesi

1. **Awal:** `git pull` di repo ini dan di repo website sebelum mengubah apa pun. Bila ada perubahan lokal
   yang belum di-commit, tanyakan dulu ke pemilik.
2. **Akhir setiap pembaruan:** catat di README → *Riwayat perubahan* (dan *Fitur* bila fitur berubah),
   pindai nama & NIK sungguhan, commit, **push**. Jangan tinggalkan pekerjaan yang belum di-push —
   PC lain tidak akan melihatnya.
3. Pengetahuan yang perlu diketahui kedua PC ditulis di **berkas ini** (atau README), bukan hanya di memori
   Claude — memori tidak ikut tersinkron.

## Aturan keras (data & kebenaran)

- **Jangan pernah commit data peserta**: `data/`, `hasil/`, `mentah/`, `.profil-browser*/`, `akun.dat`,
  skrip perapian khusus sekolah di `alat/`. `.gitignore` menjaganya — jangan dilonggarkan.
- **Pindai sebelum commit**: NIK 16 digit dan nama orang sungguhan di komentar/dokumen. Catatan kasus
  ditulis "seorang murid/peserta", bukan namanya (12 Okt 2026: 70+ nama bocor ke komentar dan ZIP).
- **NIK salah/terpotong tidak dijalankan** — NIK yang mungkin menunjuk orang lain tidak pernah dikirim.
- **Nilai pemeriksaan tidak diubah atau dikarang** (BB/TB/Hb/dll.). Mengisi nilai bawaan hanya bila
  pemilik memilihnya secara sadar; laporkan kolom mana yang diisi bawaan.
- **Nama sekolah harus persis tulisan portal.**
- No. HP di data = hotline puskesmas — bukan data pribadi, boleh.
- **Supabase**: yang boleh ada di paket, website, dan workflow hanya URL proyek + **publishable key**
  (sudah ada di `inti/login_online.json`). Kunci secret/service_role tidak pernah ditulis di mana pun.
- Gambar panduan/website hanya dari demo atau server uji dengan **data rekaan**.

## Susunan singkat

| Lokasi | Isi |
|---|---|
| `inti/` | server lokal (`server.py`, port 8765), alur portal, konverter, pembaruan, halaman HTML |
| `inti/config.py` | `VERSI` (dicap `buat_paket.bat`), konstanta waktu & perilaku |
| `inti/sapu_pelayanan.py` | alur Sapu Belum Pemeriksaan (tanpa CSV): baris tab Belum → identitas di detail → `pekerjaan._coba_peserta` |
| `inti/tatalaksana.py` | alur Tatalaksana Gigi (tanpa CSV): daftar → detail → form → status; temuan portal di docstring-nya |
| `pemasang/` | naskah Inno Setup + penyiap Python embeddable untuk Setup.exe |
| `panduan/` | sumber `Panduan CKG Robot.pdf` → `python panduan/cetak.py` |
| `supabase/` | SQL (jalankan berurutan, lihat README) + `PANDUAN SUPABASE.md` |
| `uji/` | `mock_supabase.py` — Supabase tiruan untuk uji (lihat `uji/BACA INI.md`) |
| `alat/` | cap_versi, buat_demo_web, buat_admin_web (→ repo website), buat_template_sekolah, buat_ikon |

## Rilis

1. Uji perubahan (server tiruan untuk alur login/pembaruan).
2. `buat_paket.bat`, jawab **t**. Mencap `VERSI` = `YYYY.MM.DD.HHMM`, membuat
   `../CKG-Robot-<tgl>.zip` dan (bila Inno Setup 6 terpasang) `../CKG-Robot-Setup-<tgl>.exe`.
   Pemindaian nama di ZIP sebelum dibagikan.
3. Pemilik menerbitkan ZIP di **Kelola Petugas → Terbitkan pembaruan**; Setup & PDF diunggah di
   **Panel admin website**. Claude tidak menerbitkan sendiri.
4. Commit `inti/config.py` yang sudah dicap + README, push.
5. Bila halaman aplikasi berubah: `python alat/buat_demo_web.py` / `alat/buat_admin_web.py`, push repo website.

## Jebakan lingkungan (Windows)

- Shell Bash di sini mengubah `\b`, `\a` di heredoc menjadi karakter kontrol. Skrip berisi backslash ditulis
  dengan alat Write ke berkas `.py`, bukan heredoc.
- PowerShell 5.1 `Get-Content`/`Set-Content` merusak UTF-8 tanpa BOM (→ `â†’`). Baca/tulis teks dengan Python.
- `.bat` wajib **CRLF** (`.gitattributes` = `* -text`). Tulis ulang dengan Python bila perlu.
- Portal hanya mengizinkan **satu sesi per akun**: robot yang login mengeluarkan in-app browser/Chrome yang
  memakai akun sama (20 Okt 2026). Saat menguji, jangan andalkan sesi portal di browser lain.
- Uji alur di portal sungguhan: nyalakan `mode uji = ya` di pengaturan salinan uji dulu (isi tanpa Kirim),
  baru kirim sungguhan sedikit peserta dengan izin pemilik.
- Aplikasi milik pemilik sering sedang jalan di **port 8765** — uji di port lain (8799) dan jangan
  mematikan prosesnya.
- Folder repo ini berisi `.git`, sehingga shortcut tidak dibuat otomatis di sini (sengaja); buat manual
  dengan `python inti/pintasan.py`.
- Python embeddable (Setup): `._pth` harus memuat `..\inti`; uji pasang di jalur pendek (MAX_PATH).
- Excel COM lewat PowerShell untuk uji di Excel sungguhan; pywin32 tidak terpasang.

## Lingkungan pengembang

PC kedua (G:) sejak 20 Okt 2026 punya Inno Setup 6 (`winget install --id JRSoftware.InnoSetup -e --scope user`),
jadi bisa membuat Setup.exe; Chrome tidak ada, robot & `panduan/cetak.py` memakai Chromium Playwright.
`buat_paket.bat` dari PowerShell: `cmd /c "echo t| \"<jalur lengkap>\buat_paket.bat\""`.

```
pip install -r requirements-dev.txt
python -m playwright install chromium
```
Butuh juga: Git, Google Chrome, Python 3.14 64-bit (versi ini yang dibundel Setup), Inno Setup 6
(hanya PC yang membuat rilis Setup).

## Menyiapkan PC pengembang baru

Susunan di bawah folder induk harus **sama persis** di semua PC (nama subfolder dipakai `alat/` dan CLAUDE.md).
Letak folder induk boleh berbeda per PC:

| PC | Folder induk | Folder memori Claude |
|---|---|---|
| PC pertama | `D:\Project Claude Code\Macro RPA CKG\` | `D--Project-Claude-Code-Macro-RPA-CKG` |
| PC kedua (D: kosong/tidak bisa ditulisi) | `G:\Project\CKG Robot\` | `G--Project-CKG-Robot` |

Karena nama folder memori diturunkan dari jalur induk, memori Claude kedua PC terpisah. Salin manual bila perlu.
Jalur relatif (`../Website CKG Robot`, `AKAR.parent` di `alat/`) tetap jalan di mana pun induknya.

Contoh di PC pertama:

```
D:\Project Claude Code\Macro RPA CKG\          <- dibuka di Claude Code
    CLAUDE.md                                   <- dibuat manual, isinya di bawah
    Playwright Version\   = git clone https://github.com/muhdava/ckg-robot.git
    Website CKG Robot\    = git clone https://github.com/muhdava/website-ckg-robot.git
```

`CLAUDE.md` di folder induk tidak ada di repo mana pun; isinya cukup:

```
@Playwright Version/CLAUDE.md
@Website CKG Robot/CLAUDE.md
```

Memori Claude (opsional, sekali): salin isi folder `%USERPROFILE%\.claude\projects\<folder memori PC lama>\memory`
ke `%USERPROFILE%\.claude\projects\<folder memori PC baru>\memory` (lihat tabel di atas). Desktop pemilik ada di
OneDrive, jadi bisa lewat OneDrive atau flashdisk.

Bila PC baru tidak punya Git: `winget install --id Git.Git -e` dan `winget install --id GitHub.cli -e`,
lalu pemilik sendiri menjalankan `gh auth login` (repo website privat) dan `gh auth setup-git`.
Google Chrome dan Inno Setup 6 belum terpasang di PC kedua (20 Okt 2026).
