# Katalog Form CKG Umum — DEWASA & LANSIA (≥ 18 tahun)

Disusun 15 Okt 2026 dari tiga sumber:

1. **Portal langsung** — daftar layanan seorang peserta **dewasa perempuan 49 tahun** yang sudah *Selesai
   Pemeriksaan* (36 baris), dibaca di browser tanpa mengisi apa pun.
2. **Macro V4.5** (UI.Vision) — nama form lansia/laki-laki yang tidak muncul pada peserta di atas.
3. **Kode CKG Robot** — `inti/layanan.py` (`FORM_TARGET`), `inti/form.py` (cara menjawab),
   `inti/peserta.py` (kolom template yang dibaca).

Belum dilihat langsung di portal: peserta **lansia laki-laki** dan **dewasa < 40 tahun**. Nama form untuk
mereka diambil dari macro V4.5 — perlu dicocokkan sekali lagi bila ada yang berbeda.

Nomor form = angka di id baris (`rowfrm000xxx`) dan di `data-name` pertanyaannya (`FRM000xxx`). Di jalur CKG
Umum **semua** baris memakai `rowfrm…`, termasuk Pelayanan oleh Nakes.

---

## 1. Pemeriksaan Mandiri (kuesioner)

Dewasa perempuan 49 th: **9 form**. Isinya bergantung umur dan jenis kelamin.

| FRM | Form | Untuk | Jawaban robot | Sumber data |
|-----|------|-------|---------------|-------------|
| 000006 | Demografi Dewasa Laki-laki | L 18–59 | pilihan normal/negatif | — |
| 000007 | Demografi Dewasa Perempuan | P 18–59 | pilihan normal/negatif | — |
| 000008 | Demografi Lansia | ≥ 60 | pilihan normal/negatif | — |
| 000169 | Tingkat Aktivitas Fisik | semua | pertanyaan 1 **Ya**, sisanya Tidak; **6 atau 7 hari**, **30 menit** (tetap per NIK) | — |
| 000064 | Hasil Perilaku Merokok | semua | **Tidak merokok** | kolom 35 `rinci` bila ada |
| 000138 | Penapisan Risiko Kanker Paru | semua | Tidak | — |
| 000180 | Faktor Risiko TB - Mandiri | semua | **Tidak batuk** / Tidak | kolom 35 `rinci` bila ada |
| 000027 | Faktor Risiko Kanker Usus | semua | Tidak | — |
| 000088 | Kanker Leher Rahim | P | Tidak | — |
| 000028 | Faktor Risiko Hati | semua | Tidak | — |
| 000067 | Kesehatan Jiwa Dewasa | semua | Tidak (tanpa gejala) | — |
| 000172 | Riwayat Imunisasi Tetanus | tertentu (macro V4.5) | pilihan normal | — |
| 000029 | SKILAS Kognitif | ≥ 60 | Normal → *Benar semua* / Ya | kolom 31 **Geriatri** |
| 000032 | SKILAS Mobilisasi | ≥ 60 | Normal → Ya | kolom 31 **Geriatri** |
| 000034 | SKILAS Malnutrisi | ≥ 60 | Normal → Tidak | kolom 31 **Geriatri** |
| 000038 | SKILAS Depresi | ≥ 60 | Normal → Tidak | kolom 31 **Geriatri** |
| 000040 | Barthel Index (ADL) | ≥ 60 | Normal → *Mandiri* / *Terkendali teratur* | kolom 31 **Geriatri** |

Kolom **Geriatri** berisi `Normal` atau `Tidak Normal`; `Tidak Normal` membalik semua jawaban geriatri ke arah
gangguan (tidak tahu / tidak / tergantung pertolongan).

---

## 2. Pelayanan oleh Nakes — DIISI robot

| FRM | Form | Untuk | Isian | Sumber data |
|-----|------|-------|-------|-------------|
| 000051 | Gizi (BB - TB - Lingkar Perut) Perempuan | P | **BB**, **TB**, **Lingkar Perut** | kolom 19 BB, 20 TB; LP dari kolom 21 *Skrining LP* (Normal 70–85, Kurus 60–72, Gemuk 90–105 cm) |
| 000093 | Gizi (BB - TB - Lingkar Perut) Laki-laki | L | sama | sama |
| 000265 | Tekanan Darah Dewasa Lansia | semua | **Sistol / Diastol** | kolom 18 (mis. `130/85`; kata `Normal/Tinggi/Rendah` → angka acak dalam rentang) |
| 000256 | Pemeriksaan Gula Darah Dewasa Lansia | semua | riwayat **Tidak** + **GDS**; GDS ke-2 & puasa dikosongkan | kolom 17 (angka; kata → rentang) |
| 000099 | Skrining Telinga dan Mata (≥ 40 tahun) | ≥ 40 | semua dropdown **Normal** | — |
| 000042 | Skrining Telinga dan Mata (versi lain, bergantian dengan 099) | < 40 (dugaan) | semua dropdown **Normal** | — |
| 000055 | Skrining Karies dan Gigi Hilang | semua | normal / 0 | — |
| 000056 | Skrining Penyakit Periodontal | semua | normal | — |
| 000182 | Faktor Risiko dan Skrining X-Ray TB (Dewasa & Lansia) | semua | **Tidak batuk**, radiografi **Tidak** | kolom 35 `rinci` (hasil rontgen bila ada) |
| 000184 | Pemeriksaan Tuberkulosis (Dewasa & Lansia) | semua | kontak **Tidak diketahui**, metode **Tidak dilakukan** | kolom 35 `rinci` |
| 000198 | Pemeriksaan Penyakit Kusta | semua | **Tidak Ada** | — |
| 000199 | Pemeriksaan Penyakit Frambusia | semua | **Tidak Ada** | — |
| 000201 | Pemeriksaan Penyakit Skabies | semua | **Tidak Ada** | — |
| 000101 | Pemeriksaan PPOK (Skrining PUMA) | ≥ 40 / perokok | jawaban negatif | — |
| 000059 | Skrining Kanker Payudara | P | **SADANIS normal** | — |
| 000060 | Pemeriksaan Inspekulo dan IVA | P | negatif | — |

Pada peserta contoh (diisi petugas, bukan robot) X-Ray TB, Pemeriksaan TB, PUMA, Kanker Payudara, dan IVA
masih *Belum Pemeriksaan*, tetapi pesertanya tetap *Selesai Pemeriksaan*. Artinya portal tidak mewajibkan
seluruh baris Nakes terisi untuk menutup layanan.

---

## 3. Pelayanan oleh Nakes — SENGAJA TIDAK diisi robot

Pemeriksaan lanjutan/laboratorium yang hanya dikerjakan bila memang dilakukan. Robot membiarkannya
*Belum Pemeriksaan* (tidak ada di `FORM_TARGET`).

| FRM | Form | Syarat menurut portal |
|-----|------|----------------------|
| 000186 | Pemeriksaan Kadar CO (Tatalaksana Merokok) | hanya bila merokok / terpapar asap |
| 000044 | Pemeriksaan Hepatitis | lab |
| 000045 | Pemeriksaan Fibrosis/Sirosis Hati | lab |
| 000245 | Skrining Fungsi Ginjal (P) | ≥ 40 dengan risiko HT/DM |
| 000248 | Skrining Kerusakan Ginjal | ≥ 40 dengan risiko HT/DM |
| 000047 | POCT Lipid Panel | ≥ 40 dan penyandang HT/DM |
| 000061 | Hasil Pemeriksaan HPV-DNA | P, lab |
| 000050 | Skrining Kanker Usus (TL APCS) | pemeriksaan lanjutan |
| 000041 | Skrining Kanker Paru | ≥ 45 tahun |
| 000205 | Pemeriksaan Calon Pengantin | catin |
| 000188 | Pemeriksaan HIV | lab |
| 000191 | Pemeriksaan Sifilis | lab |
| 000057 | Skrining Jantung (EKG) | penyandang HT & DM |

---

## 4. Kolom template "DEWASA-LANSIA (real data)" — mana yang benar-benar dipakai

Template: `template/Template DEWASA-LANSIA (real data).xlsx`.

| Kolom | Isi | Dipakai robot? |
|-------|-----|----------------|
| 2–5 | NIK, Nama, Tanggal Lahir, Jenis Kelamin | ya — pendaftaran & pencarian |
| 6 | No HP | ya (kosong → hotline puskesmas) |
| 7–13 | Provinsi … Pekerjaan | ya — pendaftaran |
| 14 | Merokok | **TIDAK** — form Merokok selalu *Tidak*, kecuali lewat kolom 35 |
| 15 | Riwayat Hipertensi | **TIDAK** |
| 16 | Riwayat Diabetes | **TIDAK** — riwayat di form Gula selalu *Tidak* |
| 17 | Gula Darah (mg/dL) | **ya** — angka apa adanya |
| 18 | Tekanan Darah (Sistol/Diastol) | **ya** — angka apa adanya |
| 19–20 | Berat Badan, Tinggi Badan | **ya** — angka apa adanya |
| 21 | Skrining LP | ya — rentang lingkar perut |
| 22–30 | Mata-Telinga, Karies, Periodontal, Frambusia, Kusta, Skabies, TB X-Ray, Pemeriksaan TB, Kesehatan Jiwa | **TIDAK** — form-form ini selalu dijawab normal |
| 31 | Geriatri | **ya** — form SKILAS & Barthel (lansia) |
| 32–34 | PUMA, Kanker Payudara, IVA | **TIDAK** — selalu normal |
| 35 | `rinci` (opsional) | ya — temuan per pertanyaan, saat ini untuk TB/merokok/mata/gigi/DM dari berkas skrining TBC |

**Akibatnya:** bila data kunjungan memuat temuan TIDAK normal (perokok, riwayat hipertensi/diabetes, gangguan
mata, karies, gejala jiwa, dst.), mengisinya di kolom 14–16 / 22–34 **belum** mengubah jawaban robot. Temuan
seperti itu harus lewat kolom 35 `rinci`, atau kolom-kolom tersebut perlu disambungkan dulu ke pengisi form.

---

## 5. Yang masih perlu dipastikan di portal

- Daftar form **lansia laki-laki** (≥ 60) — apakah sama dengan katalog di atas.
- **Dewasa < 40 tahun** — form Telinga-Mata mana yang muncul (000042 atau 000099), dan apakah PUMA muncul.
- **000172 Riwayat Imunisasi Tetanus** — untuk siapa munculnya.
- Teks pertanyaan & pilihan tiap form mandiri (katalog ini mencatat jawaban robot, bukan teks lengkap soalnya).
