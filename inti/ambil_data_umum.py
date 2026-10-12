"""
Ubah berkas mentah (.xlsx / .csv) menjadi CSV siap jalan - DIPETAKAN DARI JUDUL
KOLOM, bukan dari posisinya.

    python inti\\ambil_data_umum.py "C:\\...\\SDN RBS 07 KELAS 1.xlsx"
    python inti\\ambil_data_umum.py "...xlsx" --sekolah "SDN Rawa Badak Selatan 07"
    python inti\\ambil_data_umum.py "...xlsx" --kelas "Kelas 1" --lembar "KELAS 1"

KENAPA PERLU ADA, PADAHAL SUDAH ADA EMPAT PENGEKSTRAK
    Keempat pengekstrak yang sudah ada mengenali SATU bentuk berkas masing-
    masing (register sekolah, skrining TBC, buku kunjungan, laporan SRQ), dan
    membaca kolomnya dari posisi yang sudah dipastikan. Itu tepat untuk berkas
    yang bentuknya memang tetap.

    Yang tidak tertangani adalah berkas yang "hampir template": tiap sekolah
    mengirim susunan yang sedikit berbeda - ada yang membuang kolom Alamat, ada
    yang tidak punya Gejala Cemas/Depresi, ada yang menambah kolom sendiri.

    Berkas "SDN RBS 07 KELAS 1 FIX" (1 Sep) adalah contohnya: 21 kolom, kurang
    tiga (Alamat, Gejala Cemas, Gejala Depresi). Karena kolom "Kelas 1" jadi
    bergeser dari kolom 12, macro tidak mengenalinya sebagai data sekolah sama
    sekali - ia terbaca sebagai PARAMETER dewasa/lansia, dan "Kelas 1" dipakai
    sebagai STATUS PERNIKAHAN. Tidak ada satu pun galat; yang terlihat hanya
    "gagal memilih status pernikahan".

    Pemetaan dari JUDUL membuat kelas kesalahan itu mustahil: kolom yang tidak
    ada dilaporkan sebagai peringatan lalu diisi nilai bawaan, dan kolom yang
    ada tidak pernah tertukar hanya karena tetangganya hilang.

YANG DIPERINGATKAN
    - kolom template yang tidak ada di berkas   -> dipakai nilai bawaan
    - kolom berkas yang tidak dikenali          -> diabaikan, disebutkan
    - kolom WAJIB hilang                        -> berhenti, tidak menulis apa pun
    - NIK yang tersimpan sebagai ANGKA          -> digit ke-16 bisa sudah hilang
    - nama sekolah yang tidak ada di daftar portal
"""
from __future__ import annotations

import csv
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config                                     # noqa: E402
import peserta                                   # noqa: E402
from peserta import bersihkan_nama                # noqa: E402


# --------------------------------------------------------------------- NIK
# NIK 16 digit TIDAK MUAT dalam ketelitian angka Excel (15 angka penting), jadi
# NIK yang tersimpan sebagai number kehilangan digit terakhirnya - "...0000" -
# dan yang sempat jadi float terbaca "...001.0". Keduanya sudah pernah merusak
# data di proyek ini, dan keduanya TIDAK terlihat sebagai galat: bentuknya tetap
# angka 16 digit yang meyakinkan. Karena itu asal-usul selnya ikut dilaporkan,
# bukan cuma isinya.
_SAINS = re.compile(r"^\d(?:\.\d+)?[eE]\+?\d+$")


def rapikan_nik(nilai) -> tuple[str, str]:
    """Kembalikan (nik, masalah). `masalah` kosong berarti aman."""
    if nilai is None:
        return "", "NIK kosong"
    if isinstance(nilai, bool):
        return "", f"NIK bertipe aneh ({type(nilai).__name__})"
    if isinstance(nilai, (int, float)):
        # Bahaya utamanya di sini: sel bertipe ANGKA.
        utuh = f"{int(nilai):d}"
        return utuh, ("NIK tersimpan sebagai ANGKA di Excel - digit terakhir "
                      "mungkin sudah hilang; format kolomnya sebagai Teks")
    teks = str(nilai).strip()
    if _SAINS.match(teks):
        return "", f"NIK terbaca sebagai notasi ilmiah ({teks}) - sudah rusak di berkasnya"
    if teks.endswith(".0") and teks[:-2].isdigit():
        return teks[:-2], "NIK sempat menjadi bilangan desimal - periksa digit terakhirnya"
    teks = re.sub(r"[^0-9]", "", teks)
    if not teks:
        return "", "NIK tidak berisi angka"
    if len(teks) != 16:
        return teks, f"NIK {len(teks)} digit (seharusnya 16)"
    if teks.endswith("0000"):
        # Ciri khas NIK yang PERNAH tersimpan sebagai angka lalu diubah jadi
        # teks: ketelitian 15 angka penting memotong digit terakhir, dan
        # Excel menambal sisanya dengan nol. Sudah pernah terjadi di proyek
        # ini. Empat nol beruntun di ujung NIK yang sah sangat jarang, jadi
        # lebih baik ditanyakan daripada lolos diam-diam.
        return teks, "NIK berakhir '0000' - ciri NIK yang digitnya sudah terpotong Excel"
    return teks, ""


# ------------------------------------------------------------------- kolom
# Satu baris = satu kolom template, berurutan.
#   judul   nama kolom di template (dipakai di pesan)
#   pola    pengenal judul di berkas sumber; None = tidak pernah dicari
#   wajib   True  -> berkas ditolak bila kolomnya tidak ada
#   bawaan  dipakai bila kolomnya tidak ada (dan tidak wajib)
#
# Urutan polanya penting. "nama orang tua" harus tertangkap SEBELUM "nama",
# kalau tidak kolom nama murid mengenai kolom orang tuanya - kesalahan yang
# sudah pernah terjadi di `ambil_data_sekolah`.
KOLOM_SEKOLAH = [
    ("No",                     None,                                   False, ""),
    ("NIK",                    r"^n\.?i\.?k\.?$|nomor\s*induk\s*kependudukan", True,  ""),
    ("Nama",                   r"^nama$|nama\s*(lengkap|peserta|siswa|murid|anak|pasien)", True, ""),
    ("Tanggal Lahir",          r"tgl\.?\s*lahir|tanggal\s*lahir",       True,  ""),
    ("Jenis Kelamin",          r"jenis\s*kelamin|jns\.?\s*klm|^l\s*/\s*p$|^l/p$", False, ""),
    ("Alamat",                 r"^alamat$|detail\s*alamat",             False, "Tanjung Priok"),
    ("Status Pernikahan",      r"status\s*(per)?nikah",                 False, "Belum Menikah"),
    ("Pekerjaan",              r"^pekerjaan$",                          False, "Pelajar"),
    ("No HP",                  r"no\.?\s*hp|whatsapp|telp|telepon",     False, ""),
    ("Penyandang Disabilitas", r"disabilitas",                          False, "Tidak"),
    ("Nama Sekolah",           r"nama\s*sekolah|^sekolah$",             False, ""),
    ("Kelas",                  r"^kelas$|jenjang",                      False, ""),
    ("Gejala Cemas",           r"cemas",                                False, "Normal"),
    ("Gejala Depresi",         r"depresi",                              False, "Normal"),
    ("Berat Badan",            r"berat",                                False, ""),
    ("Tinggi Badan",           r"tinggi",                               False, ""),
    ("Gula Darah",             r"gula\s*darah",                         False, "Normal"),
    ("Tekanan Darah",          r"tekanan\s*darah|tensi",                False, "Normal"),
    ("Hemoglobin",             r"hemoglobin|^hb$",                      False, "13"),
    ("Skrining Gigi",          r"gigi",                                 False, "Normal"),
    ("Serumen",                r"serumen",                              False, "Tidak Ada"),
    ("Visus Mata",             r"visus|tajam\s*penglihatan",            False, "Normal"),
    ("Berkacamata",            r"kacamata",                             False, "Tidak"),
    ("Kebugaran",              r"kebugaran",                            False, "Baik sekali"),
]

# Judul di berkas sumber yang memang BUKAN kolom template - disebut supaya
# peringatan "kolom tak dikenali" tidak berisik oleh hal yang sudah diketahui.
ABAIKAN = re.compile(
    r"nama\s*orang\s*tua|nama\s*ortu|^ortu$|^wali$|nama\s*wali|"
    r"^no\.?$|^nomor$|^urut|^nisn$|^nis$|^ttl$|^umur$|^usia$|^imt$|^bmi$|"
    r"^ket(erangan)?$|^catatan$|^lila$|lingkar|^cek(\s|$)", re.I)

# Sasaran BALITA TANPA NIK memakai daftar abai yang lebih longgar: di sana data
# wali justru WAJIB, sedangkan pada berkas sekolah dan balita biasa kolom
# "Nama Wali" memang harus dibuang supaya tidak tertukar dengan nama peserta.
# Satu daftar untuk semua sasaran membuat kolom wali tak pernah terbaca -
# terlihat langsung waktu diuji: "Nama Wali" hilang dari pemetaannya.
# Sasaran DEWASA/LANSIA juga perlu daftar abai sendiri, dengan sebab yang
# berbeda: kata "lingkar" ada di daftar abai umum karena berkas SEKOLAH memuat
# LILA (lingkar lengan) yang memang bukan target. Tapi di sini "Lingkar Perut"
# JUSTRU DATANYA - itulah Skrining LP. Satu daftar untuk semua sasaran membuat
# kolom itu tak pernah terbaca.
ABAIKAN_LANSIA = re.compile(
    r"nama\s*orang\s*tua|nama\s*ortu|^ortu$|^wali$|nama\s*wali|"
    r"^no\.?$|^nomor$|^urut|^nisn$|^nis$|^ttl$|^umur$|^usia$|^imt$|^bmi$|"
    r"^ket(erangan)?$|^catatan$|^lila$|lingkar\s*lengan", re.I)

ABAIKAN_TANPA_NIK = re.compile(
    r"^no\.?$|^nomor$|^urut|^nisn$|^nis$|^ttl$|^umur$|^usia$|^imt$|^bmi$|"
    r"^ket(erangan)?$|^catatan$|^lila$|lingkar|^cek(\s|$)", re.I)

# CKG BALITA: 18 kolom. Punya rantai wilayah bertingkat (peserta dicari lewat
# alamat, bukan sekolah) dan empat parameter khas balita di ujungnya. Nilai
# bawaannya menyalin `ambil_data_balita.TETAP`, supaya berkas yang lewat sini
# seragam dengan berkas balita yang sudah pernah dijalankan.
#
# "Berat Lahir" HARUS didahulukan dari "Berat Saat Ini": pola yang kedua juga
# mengenai tulisan "berat badan", dan tanpa urutan ini kolom berat lahir akan
# terambil olehnya.
KOLOM_BALITA = [
    ("No",                     None,                                   False, ""),
    ("NIK",                    r"^n\.?i\.?k\.?( anak)?$|nomor\s*induk\s*kependudukan", True, ""),
    ("Nama",                   r"^nama$|nama\s*(lengkap|peserta|anak|balita|pasien)", True, ""),
    ("Tanggal Lahir",          r"tgl\.?\s*lahir|tanggal\s*lahir",       True,  ""),
    ("Jenis Kelamin",          r"jenis\s*kelamin|jns\.?\s*klm|^l\s*/\s*p$|^l/p$", False, ""),
    ("Provinsi",               r"^provinsi$",                           False, "DKI Jakarta"),
    ("Kota/Kabupaten",         r"^kota|kabupaten",                      False, "Kota Adm. Jakarta Utara"),
    ("Kecamatan",              r"^kecamatan$",                          False, "Koja"),
    ("Kelurahan",              r"^kelurahan$|^desa$",                   False, "Lagoa"),
    ("Alamat",                 r"^alamat$|detail\s*alamat",             False, "Lagoa"),
    ("Status Pernikahan",      r"status\s*(per)?nikah",                 False, "Belum Menikah"),
    ("Pekerjaan",              r"^pekerjaan$",                          False, "Tidak Bekerja"),
    ("No HP",                  r"no\.?\s*hp|whatsapp|telp|telepon",     False, config.NOHP_CADANGAN),
    ("Penyandang Disabilitas", r"disabilitas",                          False, "Tidak"),
    ("Berat Lahir",            r"berat\s*lahir",                        False, "normal"),
    ("Berat Saat Ini",         r"berat\s*(saat\s*ini|kini|badan)",      False, "normal"),
    ("Riwayat Imunisasi",      r"imunisasi",                            False, "Ya"),
    ("Status Gizi",            r"gizi",                                 False, "normal"),
]

# Balita yang NIK-nya belum terbit ("Bayi Nyonya ..."). Bedanya dari balita
# biasa cuma di identitas: kolom NIK peserta hilang, diganti data WALI yang
# lengkap - dan No HP-nya jadi milik wali, sebab di portal nomor itu memang
# yang diketik ke kolom WhatsApp peserta lalu nomor wali tinggal dicentang.
KOLOM_BALITA_TANPA_NIK = [
    ("No",                     None,                                   False, ""),
    ("Nama",                   r"^nama$|nama\s*(lengkap|peserta|anak|balita|bayi|pasien)", True, ""),
    ("Tanggal Lahir",          r"^(tgl|tanggal)\.?\s*lahir$|tgl\.?\s*lahir\s*(anak|bayi|peserta)|tanggal\s*lahir\s*(anak|bayi|peserta)", True, ""),
    ("Jenis Kelamin",          r"^jenis\s*kelamin$|^jns\.?\s*klm$|^l\s*/\s*p$|jenis\s*kelamin\s*(anak|bayi|peserta)", False, ""),
    ("NIK Wali",               r"nik\s*(wali|ibu|orang\s*tua)|wali.*nik",  True,  ""),
    ("Nama Wali",              r"nama\s*(wali|ibu|orang\s*tua)",       True,  ""),
    ("Tanggal Lahir Wali",     r"(tgl|tanggal)\.?\s*lahir\s*(wali|ibu|orang\s*tua)", True, ""),
    ("Jenis Kelamin Wali",     r"jenis\s*kelamin\s*(wali|ibu|orang\s*tua)|kelamin\s*wali", False, "Perempuan"),
    ("Provinsi",               r"^provinsi$",                           False, "DKI Jakarta"),
    ("Kota/Kabupaten",         r"^kota|kabupaten",                      False, "Kota Adm. Jakarta Utara"),
    ("Kecamatan",              r"^kecamatan$",                          False, "Koja"),
    ("Kelurahan",              r"^kelurahan$|^desa$",                   False, "Lagoa"),
    ("Alamat",                 r"^alamat$|detail\s*alamat",             False, "Lagoa"),
    ("Status Pernikahan",      r"status\s*(per)?nikah",                 False, "Belum Menikah"),
    ("Pekerjaan",              r"^pekerjaan$",                          False, "Tidak Bekerja"),
    ("No HP Wali",             r"no\.?\s*hp|whatsapp|telp|telepon",     False, config.NOHP_CADANGAN),
    ("Penyandang Disabilitas", r"disabilitas",                          False, "Tidak"),
    ("Berat Lahir",            r"berat\s*lahir",                        False, "normal"),
    ("Berat Saat Ini",         r"berat\s*(saat\s*ini|kini|badan)",      False, "normal"),
    ("Riwayat Imunisasi",      r"imunisasi",                            False, "Ya"),
    ("Status Gizi",            r"gizi",                                 False, "normal"),
]

# CKG DEWASA/LANSIA: 33 kolom, menyalin "Template DEWASA-LANSIA (parameter)".
#
# Sengaja yang PARAMETER, bukan yang "real data" (34 kolom): berkas mentah
# lansia dari posyandu hampir tak pernah membawa angka hasil ukur, dan bentuk
# parameter membiarkan angkanya diturunkan sendiri dari kata "Normal". Kalau
# angkanya memang ada, isi saja kolom Gula Darah / Tekanan Darah dengan
# angkanya - macro menerima keduanya di kolom yang sama.
#
# Nilai bawaannya dipilih untuk LANSIA, bukan dewasa muda: "Menikah" dan
# "Belum/Tidak Bekerja" jauh lebih sering benar di kelompok ini. Semua itu
# tetap dilaporkan sebagai "dipakai nilai bawaan" waktu konversi, jadi tidak
# ada yang tertukar diam-diam.
KOLOM_LANSIA = [
    ("No",                     None,                                    False, ""),
    ("NIK",                    r"^n\.?i\.?k\.?$|nomor\s*induk\s*kependudukan|^nik\s*(peserta|lansia)", True, ""),
    ("Nama",                   r"^nama$|nama\s*(lengkap|peserta|lansia|pasien|warga)", True, ""),
    ("Tanggal Lahir",          r"tgl\.?\s*lahir|tanggal\s*lahir",       True,  ""),
    ("Jenis Kelamin",          r"jenis\s*kelamin|jns\.?\s*klm|^l\s*/\s*p$|^l/p$", False, ""),
    ("Provinsi",               r"^provinsi$",                            False, "DKI Jakarta"),
    ("Kota/Kabupaten",         r"^kota|kabupaten",                       False, "Kota Adm. Jakarta Utara"),
    ("Kecamatan",              r"^kecamatan$",                           False, "Koja"),
    ("Kelurahan",              r"^kelurahan$|^desa$",                    False, "Lagoa"),
    ("Alamat",                 r"^alamat$|detail\s*alamat",              False, "Lagoa"),
    ("Status Pernikahan",      r"status\s*(per)?nikah",                  False, "Menikah"),
    ("Pekerjaan",              r"^pekerjaan$",                           False, "Belum/Tidak Bekerja"),
    ("Merokok",                r"merokok|^rokok$",                       False, "Tidak"),
    ("Riwayat Hipertensi",     r"hipertensi|darah\s*tinggi",             False, "Tidak"),
    ("Riwayat Diabetes",       r"diabetes|kencing\s*manis|^dm$",         False, "Tidak"),
    ("Gula Darah",             r"gula\s*darah|^gds$|^gdp$",              False, "Normal"),
    ("Tekanan Darah",          r"tekanan\s*darah|^td$|tensi",            False, "Normal"),
    ("Skrining LP",            r"skrining\s*lp|lingkar\s*perut|^lp$|status\s*gizi|^gizi$", False, "Normal"),
    ("Skrining Mata dan Telinga", r"mata\s*dan\s*telinga|mata.*telinga|penglihatan|pendengaran", False, "Normal"),
    ("Skrining Karies",        r"karies",                                False, "Normal"),
    ("Skrining Periodontal",   r"periodontal",                           False, "Normal"),
    ("Frambusia",              r"frambusia",                             False, "Normal"),
    ("Kusta",                  r"kusta",                                 False, "Normal"),
    ("Skabies",                r"skabies|kudis",                         False, "Normal"),
    ("Kategori",               r"^kategori$",                            False, "Lansia"),
    ("Umur (bulan)",           r"umur\s*\(?\s*bulan",                    False, ""),
    ("TB X-Ray",               r"x-?ray|rontgen|^tb\s*x",                False, "Normal"),
    ("Pemeriksaan Tuberkulosis", r"tuberkulosis|^tbc?$|skrining\s*tb",   False, "Normal"),
    ("Kesehatan Jiwa",         r"kesehatan\s*jiwa|^jiwa$|^srq$",         False, "Normal"),
    ("Geriatri",               r"geriatri",                              False, "Normal"),
    ("PUMA",                   r"^puma$|ppok",                           False, "Normal"),
    ("Kanker Payudara",        r"kanker\s*payudara|^sadanis$",           False, "Normal"),
    ("IVA",                    r"^iva$|kanker\s*serviks",                False, "Normal"),
]

# CKG DEWASA/LANSIA "real data": 34 kolom, menyalin
# "Template DEWASA-LANSIA (real data).xlsx". Bedanya dari yang parameter cuma
# tiga kolom, dan ketiganya yang menentukan:
#
#   No HP (kolom 6)        - dan ini pula yang MEMBEDAKAN kedua tata letak di
#                            mata macro: kolom 6 berisi angka/kosong -> real
#                            data, berisi teks ("DKI Jakarta") -> parameter.
#   Berat Badan (kolom 19)
#   Tinggi Badan (kolom 20)
#
# Berat dan tinggi sengaja BAWAANNYA KOSONG, bukan diisi angka: kosong berarti
# "turunkan dari parameter gizi", sedangkan angka karangan akan tercatat sebagai
# hasil ukur sungguhan di portal.
KOLOM_REAL = [
    ("No",                     None,                                    False, ""),
    ("NIK",                    r"^n\.?i\.?k\.?$|nomor\s*induk\s*kependudukan|^nik\s*(peserta|lansia)", True, ""),
    ("Nama",                   r"^nama$|nama\s*(lengkap|peserta|lansia|pasien|warga)", True, ""),
    ("Tanggal Lahir",          r"tgl\.?\s*lahir|tanggal\s*lahir",       True,  ""),
    ("Jenis Kelamin",          r"jenis\s*kelamin|jns\.?\s*klm|^l\s*/\s*p$|^l/p$", False, ""),
    ("No HP",                  r"no\.?\s*hp|whatsapp|telp|telepon|^hp$", False, config.NOHP_CADANGAN),
    ("Provinsi",               r"^provinsi$",                            False, "DKI Jakarta"),
    ("Kota/Kabupaten",         r"^kota|kabupaten",                       False, "Kota Adm. Jakarta Utara"),
    ("Kecamatan",              r"^kecamatan$",                           False, "Koja"),
    ("Kelurahan",              r"^kelurahan$|^desa$",                    False, "Lagoa"),
    ("Alamat",                 r"^alamat$|detail\s*alamat",              False, "Lagoa"),
    ("Status Pernikahan",      r"status\s*(per)?nikah",                  False, "Menikah"),
    ("Pekerjaan",              r"^pekerjaan$",                           False, "Belum/Tidak Bekerja"),
    ("Merokok",                r"merokok|^rokok$",                       False, "Tidak"),
    ("Riwayat Hipertensi",     r"hipertensi|darah\s*tinggi",             False, "Tidak"),
    ("Riwayat Diabetes",       r"diabetes|kencing\s*manis|^dm$",         False, "Tidak"),
    ("Gula Darah (mg/dL)",     r"gula\s*darah|^gds$|^gdp$",              False, "Normal"),
    ("Tekanan Darah (Sistol/Diastol)", r"tekanan\s*darah|^td$|tensi",    False, "Normal"),
    ("Berat Badan (kg)",       r"berat\s*(badan)?|^bb$",                 False, ""),
    ("Tinggi Badan (cm)",      r"tinggi\s*(badan)?|^tb$(?!\s*x)",        False, ""),
    ("Skrining LP",            r"skrining\s*lp|lingkar\s*perut|^lp$|status\s*gizi|^gizi$", False, "Normal"),
    ("Skrining Mata dan Telinga", r"mata\s*dan\s*telinga|mata.*telinga|penglihatan|pendengaran", False, "Normal"),
    ("Skrining Karies",        r"karies",                                False, "Normal"),
    ("Skrining Periodontal",   r"periodontal",                           False, "Normal"),
    ("Frambusia",              r"frambusia",                             False, "Normal"),
    ("Kusta",                  r"kusta",                                 False, "Normal"),
    ("Skabies",                r"skabies|kudis",                         False, "Normal"),
    ("TB X-Ray",               r"x-?ray|rontgen|^tb\s*x",                False, "Normal"),
    ("Pemeriksaan Tuberkulosis", r"tuberkulosis|^tbc?$|skrining\s*tb",   False, "Normal"),
    ("Kesehatan Jiwa",         r"kesehatan\s*jiwa|^jiwa$|^srq$",         False, "Normal"),
    ("Geriatri",               r"geriatri",                              False, "Normal"),
    ("PUMA",                   r"^puma$|ppok",                           False, "Normal"),
    ("Kanker Payudara",        r"kanker\s*payudara|^sadanis$",           False, "Normal"),
    ("IVA",                    r"^iva$|kanker\s*serviks",                False, "Normal"),
]

TATA_LETAK = {"sekolah": KOLOM_SEKOLAH, "balita": KOLOM_BALITA,
              "balita_tanpa_nik": KOLOM_BALITA_TANPA_NIK,
              "lansia": KOLOM_LANSIA, "lansia_real": KOLOM_REAL}

# Kolom yang menandai berkas ini memang bicara soal dewasa/lansia. Tanpa salah
# satunya, sasaran "lansia" TIDAK boleh menang sendiri: kolom identitasnya
# (NIK, Nama, Tanggal Lahir, Jenis Kelamin, Alamat) sama persis dengan sasaran
# balita, jadi berkas balita biasa pun akan mencetak angka tinggi di sana.
# Berkas lansia dari posyandu memang jarang membawa kolom penanda ini - jadi
# sasarannya dipilih SENDIRI di layar, bukan ditebak.
PENANDA_LANSIA = ("Merokok", "Riwayat Hipertensi", "Riwayat Diabetes",
                  "Geriatri", "PUMA", "Kanker Payudara", "IVA",
                  "Skrining Periodontal", "Kategori")

# Kolom yang HANYA ada pada sasaran balita tanpa NIK. Tanpa salah satu darinya
# terbaca, sasaran itu tidak boleh menang sendiri: seluruh kolom lainnya sama
# persis dengan balita biasa, jadi berkas balita ber-NIK pun akan mencetak
# angka tinggi di sana dan bisa memenangkannya karena selisih satu-dua kolom.
PENANDA_TANPA_NIK = ("NIK Wali", "Nama Wali", "Tanggal Lahir Wali")


def pilih_tata_letak(baris: list[list]) -> tuple[str, dict]:
    """
    Tebak sasaran mana yang paling cocok dengan judul kolom berkas ini.

    Dihitung dari BANYAKNYA kolom yang berhasil dipetakan, bukan dari satu
    kolom penanda. Berkas balita mengenai 17 kolom pada sasaran balita tapi
    cuma 9 pada sasaran sekolah; berkas sekolah sebaliknya. Selisihnya lebar,
    jadi tebakannya tidak rapuh.

    Seri dimenangkan "sekolah" - itu sasaran yang sudah dipakai selama ini.
    """
    nilai = {}
    for nama, kolom in TATA_LETAK.items():
        _, peta, _ = cari_kepala(baris, kolom)
        nilai[nama] = len(peta)
        if nama == "balita_tanpa_nik" and not any(k in peta for k in PENANDA_TANPA_NIK):
            nilai[nama] = 0
        if nama in ("lansia", "lansia_real") and not any(k in peta for k in PENANDA_LANSIA):
            nilai[nama] = 0
    urut = sorted(nilai.items(), key=lambda x: (-x[1], x[0] != "sekolah"))
    return urut[0][0], nilai


def kelamin_baku(teks: str, bawaan: str = "") -> str:
    """
    Samakan tulisan jenis kelamin jadi "Laki-laki" / "Perempuan".

    Berkas puskesmas menulisnya "L", "P", "LK", "Pr", "laki2", "wanita" -
    semuanya sah bagi manusia dan semuanya SALAH bagi portal, yang dropdown-nya
    hanya menerima dua tulisan itu persis.

    Bukan sekadar soal dropdown: `Peserta._ideal()` memilih baris tabel WHO
    dengan `jenis_kelamin.startswith("laki")`, sehingga "L" diam-diam dihitung
    sebagai PEREMPUAN dan seluruh berat/tinggi balita laki-laki meleset tanpa
    satu pun pesan galat.
    """
    v = _rapi(teks).lower()
    if not v:
        return bawaan
    if v.startswith(("l", "m")) or v in ("1", "laki2", "pria"):
        return "Laki-laki"
    if v.startswith(("p", "w", "f")):
        return "Perempuan"
    return _rapi(teks) or bawaan


def _rapi(x) -> str:
    return re.sub(r"\s+", " ", str(x if x is not None else "")).strip()


def tanggal_sel(nilai) -> tuple[str, str]:
    """
    Tanggal lahir sebagai teks dd/mm/yyyy, plus keterangan bila perlu dicek.

    Kolom tanggal yang selnya TIDAK diformat sebagai tanggal terbaca sebagai
    ANGKA URUT Excel - "42947", bukan "31/07/2017". Terlihat pada berkas
    "8355 terbaru tahun pelajaran" milik pengguna. Dibiarkan apa adanya, angka
    itu masuk CSV dan umur peserta jadi tidak bisa dihitung sama sekali.
    """
    if isinstance(nilai, (datetime, date)):
        return nilai.strftime("%d/%m/%Y"), ""
    if isinstance(nilai, (int, float)) and not isinstance(nilai, bool):
        # Rentangnya diambil dari `peserta.SERIAL_EXCEL` - satu angka untuk
        # konverter dan pembaca, supaya tidak ada tanggal yang diterima di satu
        # tempat lalu ditolak di tempat lain.
        if peserta.SERIAL_EXCEL[0] <= float(nilai) <= peserta.SERIAL_EXCEL[1]:
            from openpyxl.utils.datetime import from_excel
            return (from_excel(float(nilai)).strftime("%d/%m/%Y"),
                    "tanggal lahir tersimpan sebagai angka urut Excel - sudah diterjemahkan")
        return str(nilai), "tanggal lahir berupa angka yang tidak masuk akal"

    # Nilai TEKS diserahkan ke pembaca yang sama dengan yang dipakai saat
    # menjalankan macro. Satu sumber aturan: apa pun yang bisa dijalankan pasti
    # bisa dikonversi, dan sebaliknya - tidak ada lagi berkas yang lolos
    # konversi lalu mentok di kalender portal.
    teks = _teks_sel(nilai)
    if not teks:
        return "", ""
    tgl = peserta.tanggal_dari_teks(teks)
    if tgl is None:
        return teks, f"tanggal lahir tidak terbaca ({teks!r}) - perbaiki manual"
    baku = tgl.strftime("%d/%m/%Y")
    return baku, ("" if baku == teks
                  else f"tanggal lahir dirapikan: {teks!r} -> {baku}")


def _teks_sel(nilai) -> str:
    """Isi sel sebagai teks, dengan tanggal dan angka bulat yang tidak berekor."""
    if nilai is None:
        return ""
    if isinstance(nilai, datetime):
        return nilai.strftime("%d/%m/%Y")
    if isinstance(nilai, date):
        return nilai.strftime("%d/%m/%Y")
    if isinstance(nilai, float) and nilai.is_integer():
        return str(int(nilai))
    return _rapi(nilai)


def baca_berkas(path: Path, lembar: str | None = None) -> tuple[list[list], str]:
    """Baris mentah berkas .xlsx atau .csv, apa adanya."""
    if path.suffix.lower() in (".csv", ".txt"):
        isi = path.read_text(encoding="utf-8-sig", errors="replace")
        return [list(b) for b in csv.reader(isi.splitlines())], path.stem
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=True, read_only=True)
    ws = wb[lembar] if lembar else wb[wb.sheetnames[0]]
    baris = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    return baris, ws.title


def cari_kepala(baris: list[list], kolom: list) -> tuple[int, dict, list[str]]:
    """
    Temukan baris kepala kolom dan petakan judulnya.

    Kepala dicari, bukan dipatok di baris tertentu: berkas sekolah beredar
    dengan 4, 8, bahkan 9 baris judul di atasnya. Yang dipilih adalah baris
    dengan judul TERKENALI TERBANYAK - bukan baris pertama yang ada isinya,
    sebab baris judul laporan pun berisi teks.

    Kembalikan (nomor_baris_kepala, {nama_kolom: indeks}, judul_tak_dikenali).
    """
    # Daftar abai mengikuti SASARANNYA, bukan dipatok satu untuk semua - lihat
    # keterangan di ABAIKAN_TANPA_NIK. Diturunkan dari katalog kolomnya sendiri
    # supaya tiap pemanggil `cari_kepala` otomatis memakai yang benar tanpa
    # harus ingat menyetelnya.
    if kolom is KOLOM_BALITA_TANPA_NIK:
        abaikan = ABAIKAN_TANPA_NIK
    elif kolom is KOLOM_LANSIA or kolom is KOLOM_REAL:
        abaikan = ABAIKAN_LANSIA
    else:
        abaikan = ABAIKAN

    terbaik, nilai_terbaik = -1, 0
    for i, b in enumerate(baris[:40]):
        judul = [_rapi(x).lower() for x in b]
        kena = sum(1 for _, pola, _, _ in kolom
                   if pola and any(re.search(pola, j, re.I) for j in judul if j))
        if kena > nilai_terbaik:
            terbaik, nilai_terbaik = i, kena
    if terbaik < 0 or nilai_terbaik < 3:
        return -1, {}, []

    judul = [_rapi(x) for x in baris[terbaik]]
    peta: dict[str, int] = {}
    dipakai: set[int] = set()
    # Kolom diproses menurut urutan katalog, jadi pola yang lebih khusus
    # ("nama sekolah") mengambil kolomnya sebelum pola yang lebih longgar
    # ("nama") sempat menyentuhnya.
    for nama, pola, _, _ in kolom:
        if not pola:
            continue
        for k, j in enumerate(judul):
            if k in dipakai or not j:
                continue
            if abaikan.search(j):
                continue
            if re.search(pola, j, re.I):
                peta[nama] = k
                dipakai.add(k)
                break
    tak_dikenali = [j for k, j in enumerate(judul)
                    if j and k not in dipakai and not abaikan.search(j)]
    return terbaik, peta, tak_dikenali


# Kolom HASIL PEMERIKSAAN murid. Kosong di berkas -> diisi nilai bawaannya
# (Hb 13, "Normal", "Baik sekali"), dan nilai itu tercatat di portal seolah
# hasil sungguhan. Lihat `tahan_kosong` di konversi().
PERIKSA_SEKOLAH = ("Berat Badan", "Tinggi Badan", "Hemoglobin", "Skrining Gigi", "Serumen",
                   "Visus Mata", "Kebugaran")


def konversi(path: Path, bentuk: str = "auto", lembar: str | None = None,
             sekolah: str = "", kelas: str = "", ikut_nik: bool = True,
             keluar: Path | None = None, tahan_kosong: bool = True) -> dict:
    """
    Ubah satu berkas mentah jadi CSV siap jalan.

    Kembalikan laporan: jumlah baris, peringatan, dan catatan per baris. Tidak
    pernah melempar galat untuk data yang cacat - yang cacat DILAPORKAN, supaya
    satu baris buruk tidak membatalkan seluruh berkas.
    """
    laporan: dict = {"berkas": path.name, "bentuk": bentuk, "lembar": "",
                     "peringatan": [], "catatan": [], "jumlah": 0, "tujuan": ""}

    baris, nama_lembar = baca_berkas(path, lembar)
    laporan["lembar"] = nama_lembar
    if bentuk in ("", "auto"):
        bentuk, nilai = pilih_tata_letak(baris)
        laporan["peringatan"].append(
            f"tata letak yang dipakai: {bentuk.upper()} "
            + "(kolom cocok: " + ", ".join(f"{k} {v}" for k, v in nilai.items()) + ")")
    laporan["bentuk"] = bentuk
    kolom = TATA_LETAK[bentuk]
    kepala, peta, asing = cari_kepala(baris, kolom)
    if kepala < 0:
        laporan["peringatan"].append(
            "BERHENTI: tidak ada baris kepala kolom yang dikenali. Berkas ini "
            "tidak cocok dengan template yang kita punya - pastikan ada baris "
            "berisi judul kolom seperti NIK, Nama, Tanggal Lahir.")
        return laporan
    laporan["kepala_baris"] = kepala + 1

    kurang_wajib = [n for n, _, wajib, _ in kolom if wajib and n not in peta]
    if kurang_wajib:
        laporan["peringatan"].append(
            "BERHENTI: kolom WAJIB tidak ditemukan: " + ", ".join(kurang_wajib)
            + f". Judul yang terbaca di baris {kepala + 1}: "
            + ", ".join(_rapi(x) for x in baris[kepala] if _rapi(x))[:200])
        return laporan

    kurang = [(n, bw) for n, pola, wajib, bw in kolom
              if pola and not wajib and n not in peta]
    # DIRINGKAS BILA BANYAK. Sasaran lansia punya 33 kolom dan berkas mentah
    # posyandu hampir tak pernah membawa lebih dari lima di antaranya - satu
    # baris peringatan per kolom berarti 27 baris yang isinya sama-sama
    # "wajar", dan peringatan yang SUNGGUHAN (umur meleset, NIK rusak)
    # tenggelam di antaranya.
    bawaan = []
    for n, bw in kurang:
        if n == "Nama Sekolah" and sekolah:
            continue
        if n == "Kelas" and kelas:
            continue
        bawaan.append(f"{n}={bw!r}" if bw else f"{n}=(kosong)")
    if len(bawaan) > 5:
        laporan["peringatan"].append(
            f"{len(bawaan)} kolom tidak ada di berkas, dipakai nilai bawaannya: "
            + ", ".join(bawaan))
    else:
        for satu in bawaan:
            nama_kolom, _, nilai = satu.partition("=")
            laporan["peringatan"].append(
                f"kolom '{nama_kolom}' tidak ada di berkas - dipakai nilai bawaan {nilai}")
    if asing:
        laporan["peringatan"].append(
            "kolom di berkas yang tidak dikenali (diabaikan): " + ", ".join(asing[:12]))

    # Kolom NIK-nya BUKAN selalu bernama "NIK": sasaran balita tanpa NIK sengaja
    # tidak punya NIK peserta, dan yang memegang identitasnya adalah NIK WALI.
    # Dulu di sini tertulis peta["NIK"] mati, dan berkas tanpa-NIK berhenti
    # dengan KeyError yang sama sekali tidak menyebut sebabnya.
    kol_nik = "NIK Wali" if "NIK Wali" in peta else "NIK"
    k_nik = peta.get(kol_nik, -1)

    # MURID TANPA HASIL PEMERIKSAAN DITAHAN.
    #
    # Al Irsyad (12 Okt 2026): 21 murid tanpa satu pun hasil pemeriksaan -
    # kemungkinan tidak hadir - akan masuk portal dengan Hb 13 dan semua
    # "Normal" bila dikonversi apa adanya. Itu data kesehatan resmi yang
    # dikarang. Yang dihitung hanya kolom pemeriksaan yang MEMANG ADA di berkas:
    # berkas yang sama sekali tidak membawa kolom pemeriksaan tidak ditahan
    # (tidak ada yang bisa dibedakan), cukup diberi peringatan.
    periksa_ada = [c for c in PERIKSA_SEKOLAH if c in peta] if bentuk == "sekolah" else []
    if bentuk == "sekolah" and not periksa_ada:
        laporan["peringatan"].append(
            "berkas ini tidak membawa kolom hasil pemeriksaan (BB, TB, Hb, gigi, serumen, visus, "
            "kebugaran) - SEMUA hasil diisi nilai bawaan. Pastikan memang itu yang dimaksud.")
    ditahan: list[str] = []
    diisi_bawaan: dict[str, int] = {}

    keluar_baris: list[list[str]] = []
    lihat: dict[str, int] = {}
    for n, b in enumerate(baris[kepala + 1:], start=kepala + 2):
        nik, masalah = rapikan_nik(b[k_nik] if 0 <= k_nik < len(b) else None)
        nama = bersihkan_nama(_teks_sel(b[peta["Nama"]] if peta["Nama"] < len(b) else ""))
        k_tgl = peta["Tanggal Lahir"]
        lahir, soal_tgl = tanggal_sel(b[k_tgl] if k_tgl < len(b) else None)
        if not nik and not nama:
            continue                       # baris kosong / ekor template
        tanda = f"baris {n} {nama[:28] or '(tanpa nama)':<28}"
        if periksa_ada:
            kosong = [c for c in periksa_ada
                      if not _teks_sel(b[peta[c]] if peta[c] < len(b) else "")]
            if len(kosong) == len(periksa_ada) and tahan_kosong:
                ditahan.append(f"{tanda} tidak ada hasil pemeriksaan - DITAHAN, tidak masuk CSV")
                continue
            for c in kosong:
                diisi_bawaan[c] = diisi_bawaan.get(c, 0) + 1
        if masalah:
            laporan["catatan"].append(f"{tanda} {masalah}")
        if soal_tgl:
            laporan["catatan"].append(f"{tanda} {soal_tgl}")

        # NIK JADI HAKIM TANGGAL LAHIR.
        #
        # Digit 7-12 NIK memuat tanggal lahirnya sendiri, dan ITULAH yang
        # dicocokkan portal ke Dukcapil. Tanggal di berkas yang bentrok
        # dengannya adalah sebab paling sering dari "Data peserta tidak valid",
        # dan sekaligus satu-satunya cara menangkap tanggal yang salah baca
        # gara-gara bentuk 05/06 yang mendua.
        #
        # Hanya berlaku bila kolom NIK-nya memang milik PESERTA. Pada sasaran
        # balita tanpa NIK, kolom itu berisi NIK WALI - tanggal lahir bayinya
        # jelas berbeda dari tanggal lahir ibunya, dan menyamakan keduanya
        # justru merusak.
        k_jk = peta.get("Jenis Kelamin", -1)
        kelamin = kelamin_baku(_teks_sel(b[k_jk])) if 0 <= k_jk < len(b) else ""

        if ikut_nik and kol_nik == "NIK" and nik:
            tgl_nik, jk_nik = peserta.identitas_dari_nik(nik)
            if tgl_nik:
                baku_nik = tgl_nik.strftime("%d/%m/%Y")
                if not lahir:
                    laporan["catatan"].append(
                        f"{tanda} tanggal lahir kosong - diambil dari NIK: {baku_nik}")
                    lahir = baku_nik
                elif lahir != baku_nik:
                    # Dibedakan: isian yang TIDAK TERBACA sebagai tanggal
                    # ("10 Juli", tanpa tahun) bukan tanggal yang berbeda -
                    # menyebutnya "BEDA dari NIK" membuat pembacanya mengira
                    # ada dua tanggal yang bertentangan.
                    sebab = ("tidak terbaca" if peserta.tanggal_dari_teks(lahir) is None
                             else "BEDA dari NIK")
                    laporan["catatan"].append(
                        f"{tanda} tanggal lahir {sebab} ({lahir!r}) - "
                        f"diikutkan ke NIK: {baku_nik}")
                    lahir = baku_nik
            # Jenis kelamin ikut diikutkan ke NIK, dengan alasan yang sama
            # persis: angka HARI pada NIK ditambah 40 untuk perempuan, jadi
            # NIK menyatakan jenis kelaminnya sendiri - dan itulah yang
            # dicocokkan portal. Tiap perubahan tetap dicatat satu per satu.
            if jk_nik:
                if not kelamin:
                    laporan["catatan"].append(
                        f"{tanda} jenis kelamin kosong - diambil dari NIK: {jk_nik}")
                    kelamin = jk_nik
                elif kelamin != jk_nik:
                    laporan["catatan"].append(
                        f"{tanda} jenis kelamin BEDA dari NIK ({kelamin}) - "
                        f"diikutkan ke NIK: {jk_nik}")
                    kelamin = jk_nik
        # NIK kembar hanya janggal bila itu NIK PESERTA. Satu ibu boleh punya
        # dua bayi di daftar yang sama, jadi NIK wali yang berulang normal dan
        # tidak perlu diributkan.
        if kol_nik == "NIK" and nik and nik in lihat:
            laporan["catatan"].append(f"{tanda} NIK kembar dengan baris {lihat[nik]}")
        elif nik:
            lihat[nik] = n

        satu: list[str] = []
        for nama_kolom, _, _, bawaan in kolom:
            if nama_kolom == "No":
                satu.append(str(len(keluar_baris) + 1))
            elif nama_kolom == kol_nik:
                satu.append(nik)
            elif nama_kolom == "Nama":
                satu.append(nama)
            elif nama_kolom == "Tanggal Lahir":
                satu.append(lahir)
            elif nama_kolom == "Nama Sekolah" and sekolah:
                satu.append(sekolah)
            elif nama_kolom == "Kelas" and kelas:
                satu.append(kelas)
            elif nama_kolom == "Jenis Kelamin":
                # Sudah diputuskan di atas (termasuk penyesuaian ke NIK), jadi
                # jangan dibaca ulang dari selnya - nanti koreksinya hilang.
                satu.append(kelamin or bawaan)
            elif nama_kolom in peta:
                k = peta[nama_kolom]
                isi = _teks_sel(b[k]) if k < len(b) else ""
                if nama_kolom.startswith("Jenis Kelamin"):
                    isi = kelamin_baku(isi, bawaan)
                satu.append(isi or bawaan)
            else:
                satu.append(bawaan)
        keluar_baris.append(satu)

    laporan["jumlah"] = len(keluar_baris)
    if ditahan:
        laporan["peringatan"].append(
            f"{len(ditahan)} murid TIDAK ADA HASIL PEMERIKSAANNYA - ditahan, tidak masuk CSV. "
            "Centang 'Ikutkan murid tanpa hasil pemeriksaan' bila memang ingin dijalankan "
            "dengan nilai bawaan.")
        laporan["catatan"] = ditahan + laporan["catatan"]
        laporan["ditahan"] = len(ditahan)
    if diisi_bawaan:
        bawaan_kolom = {nk: bw for nk, _, _, bw in kolom}
        laporan["peringatan"].append(
            "kolom pemeriksaan yang KOSONG diisi nilai bawaan: "
            + ", ".join(f"{c} {j} murid (={bawaan_kolom.get(c) or 'kosong'!s})"
                        for c, j in diisi_bawaan.items()))
    if not keluar_baris:
        laporan["peringatan"].append("BERHENTI: tidak ada baris data yang bisa dibaca.")
        return laporan

    if bentuk == "sekolah":
        _periksa_sekolah(keluar_baris, kolom, laporan)
    if bentuk == "balita_tanpa_nik":
        _periksa_tanpa_nik(keluar_baris, laporan)
    if bentuk in ("lansia", "lansia_real"):
        _periksa_lansia(keluar_baris, laporan)

    awalan = {"balita": "datackg-balita-",
              "balita_tanpa_nik": "datackg-balita-tanpa-nik-",
              "lansia": "datackg-lansia-",
              "lansia_real": "datackg-lansia-real-"}.get(bentuk, "datackg-")
    tujuan = keluar or (config.DATA / f"{awalan}{_tanda(path, nama_lembar)}.csv")
    with tujuan.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(keluar_baris)
    laporan["tujuan"] = str(tujuan)
    return laporan


def _tanda(path: Path, lembar: str) -> str:
    dasar = re.sub(r"[^a-z0-9]+", "-", f"{path.stem}-{lembar}".lower()).strip("-")
    return dasar[:60]


def _periksa_lansia(baris: list[list[str]], laporan: dict) -> None:
    """
    Peringatkan bila isinya ternyata bukan lansia.

    Sasaran ini tidak menolak siapa pun - portal sendiri yang menentukan
    kategori peserta dari umurnya, dan orang berusia 30 tahun tetap bisa
    didaftarkan. Yang perlu diketahui pengguna cuma satu: kalau berkas yang
    dipilih ternyata berisi anak-anak, hampir pasti sasarannya yang salah
    pilih, bukan datanya.
    """
    muda, tanpa_umur = [], 0
    kini = date.today()
    for i, b in enumerate(baris, 1):
        t = (b[3] if len(b) > 3 else "").strip()
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)
        if not m:
            tanpa_umur += 1
            continue
        d, bl, th = (int(x) for x in m.groups())
        umur = kini.year - th - ((kini.month, kini.day) < (bl, d))
        if umur < 60:
            muda.append((i, umur))
    if tanpa_umur:
        laporan["peringatan"].append(
            f"{tanpa_umur} baris tanggal lahirnya tidak terbaca - umurnya tidak "
            "bisa diperiksa, dan portal tidak akan bisa mengisi kalendernya.")
    if muda:
        laporan["peringatan"].append(
            f"{len(muda)} dari {len(baris)} baris umurnya DI BAWAH 60 tahun "
            f"(mis. baris {', '.join(str(i) for i, _ in muda[:6])}"
            + (", ..." if len(muda) > 6 else "")
            + "). Tetap bisa dijalankan - portal menentukan kategorinya sendiri "
              "dari umur - tapi periksa dulu apakah sasaran 'Lansia' memang yang "
              "kamu maksud.")


def _periksa_tanpa_nik(baris: list[list[str]], laporan: dict) -> None:
    """
    NIK wali harus 16 digit - kalau tidak, barisnya bukan sekadar kurang rapi,
    melainkan TIDAK AKAN DIKENALI sebagai balita tanpa NIK saat dijalankan.
    Pengenalan tata letak bersandar pada NIK 16 digit di kolom ke-6, jadi baris
    yang NIK walinya kosong akan terbaca sebagai bentuk lain dan diisi ke kolom
    yang salah semua. Lebih baik diteriakkan sekarang.
    """
    rusak = [i for i, b in enumerate(baris, 1)
             if not re.fullmatch(r"\d{16}", (b[4] if len(b) > 4 else "").strip())]
    if rusak:
        laporan["peringatan"].append(
            f"{len(rusak)} baris NIK WALI-nya bukan 16 digit (baris "
            + ", ".join(str(x) for x in rusak[:10])
            + (", ..." if len(rusak) > 10 else "")
            + "). Baris ini TIDAK akan dikenali sebagai balita tanpa NIK - "
              "isi NIK walinya dulu sebelum dijalankan.")


def _periksa_sekolah(baris: list[list[str]], kolom: list, laporan: dict) -> None:
    """Nama sekolah harus SAMA PERSIS dengan pilihan di portal."""
    try:
        from ambil_data_sekolah import cocokkan_sekolah
    except Exception:
        return
    i = [n for n, *_ in kolom].index("Nama Sekolah")
    for nama in sorted({b[i] for b in baris if b[i]}):
        cocok, pesan = cocokkan_sekolah(nama)
        if pesan:
            laporan["peringatan"].append(pesan)
        elif cocok != nama:
            laporan["peringatan"].append(f"nama sekolah disesuaikan: '{nama}' -> '{cocok}'")
        for b in baris:
            if b[i] == nama:
                b[i] = cocok


def _cetak(laporan: dict) -> None:
    print(f"\nBerkas   : {laporan['berkas']}  (lembar '{laporan['lembar']}')")
    if laporan.get("kepala_baris"):
        print(f"Kepala   : baris {laporan['kepala_baris']}")
    print(f"Terbaca  : {laporan['jumlah']} baris")
    if laporan["tujuan"]:
        print(f"Ditulis  : {laporan['tujuan']}")
    for p in laporan["peringatan"]:
        print(f"  [PERINGATAN] {p}")
    for c in laporan["catatan"]:
        print(f"  [CEK] {c}")


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    path = Path(argv[0])
    ambil = lambda t: (argv[argv.index(t) + 1] if t in argv else "")   # noqa: E731
    laporan = konversi(path, lembar=ambil("--lembar") or None,
                       sekolah=ambil("--sekolah"), kelas=ambil("--kelas"))
    _cetak(laporan)
    return 0 if laporan["jumlah"] else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
