"""
Bangun "Template CKG BALITA.xlsx" di folder template/.

    python inti\\buat_template_balita.py

KENAPA FORMATNYA DIKUNCI SAMPAI RIBUAN BARIS
    Template lama hanya memformat baris contohnya saja. Begitu petugas menempel
    150 baris, baris ke-7 dan seterusnya kembali "General": NIK 16 digit
    berubah jadi 3,17203E+15 lalu terpotong, dan tanggal ditebak Excel menurut
    kebiasaan mesinnya (kadang bulan/hari tertukar). Karena itu format di sini
    dipasang ke SELURUH rentang isian, bukan cuma barisnya yang terlihat.

KOLOMNYA DIKENALI DARI POSISI, BUKAN JUDUL
    `peserta.py` membaca CSV berdasarkan nomor kolom. Menambah, menghapus, atau
    menukar kolom akan merusak pembacaan tanpa pesan galat apa pun.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config                                    # noqa: E402

BARIS_ISI = 1000          # sejauh mana format dan dropdown dipasang

# (judul, lebar, format, daftar pilihan) — urutannya WAJIB sama dengan PETA_BALITA.
KOLOM = [
    ("No",                      6,  "General", None),
    ("NIK",                     20, "@",       None),
    ("Nama Lengkap",            30, "General", None),
    ("Tanggal Lahir",           15, "DD/MM/YYYY", None),
    ("Jenis Kelamin",           14, "General", "JK"),
    ("Provinsi",                16, "General", None),
    ("Kota/Kabupaten",          24, "General", None),
    ("Kecamatan",               14, "General", None),
    ("Kelurahan",               14, "General", None),
    ("Alamat",                  32, "General", None),
    ("Status Pernikahan",       18, "General", "NIKAH"),
    ("Pekerjaan",               20, "General", "KERJA"),
    ("No HP",                   16, "@",       None),
    ("Penyandang Disabilitas",  20, "General", "YATIDAK"),
    ("Berat Lahir",             14, "General", "GIZI"),
    ("Berat Saat Ini",          15, "General", "GIZI"),
    ("Riwayat Imunisasi",       17, "General", "YATIDAK"),
    ("Status Gizi",             13, "General", "GIZI"),
]

PILIHAN = {
    "JK":      ["Laki-laki", "Perempuan"],
    "YATIDAK": ["Ya", "Tidak"],
    "GIZI":    ["Kurus", "Normal", "Gemuk"],
    "NIKAH":   ["Belum Menikah"],
    "KERJA":   ["Belum/Tidak Bekerja"],
}

CONTOH = ["", "3172034904230000", "CONTOH BALITA PUTRI", "09/04/2023", "Perempuan",
          "DKI Jakarta", "Kota Adm. Jakarta Utara", "Koja", "Lagoa",
          "Jl. Mangga Blok C No. 12", "Belum Menikah", "Belum/Tidak Bekerja",
          "81210076973", "Tidak", "Normal", "Normal", "Ya", "Normal"]

PANDUAN = [
    ("Umur peserta", "0 sampai 6 tahun. Di luar itu portal tidak memunculkan "
                     "bagian Data Wali, dan formnya pun berbeda."),
    ("NIK", "Wajib 16 angka. Bayi yang NIK-nya belum terbit TIDAK bisa lewat "
            "template ini - klinik biasanya memberi nomor sementara, dan portal "
            "menolaknya."),
    ("Tanggal Lahir", "Ketik apa saja bentuknya; kolomnya sudah dikunci "
                      "dd/mm/yyyy. Yang menentukan kategori adalah umur HARI INI, "
                      "bukan umur saat kunjungan."),
    ("Berat & tinggi badan", "TIDAK diisi di sini. Keduanya diturunkan dari umur "
                             "dan jenis kelamin memakai tabel WHO."),
    ("Berat Lahir / Berat Saat Ini", "Kurus 2000-2500 g · Normal 2600-3500 g · "
                                     "Gemuk 3600-4200 g. Satuannya GRAM - beda "
                                     "dengan form pertumbuhan yang memakai kilogram."),
    ("Status Gizi", "Menentukan berat badan sekarang: Kurus 0,80-0,90x ideal · "
                    "Normal 0,95-1,05x · Gemuk 1,15-1,30x."),
    ("Riwayat Imunisasi", "Ya / Tidak. Dipakai form Imunisasi Hepatitis B dan "
                          "Imunisasi Rutin Balita."),
    ("No HP", "Boleh diawali 0 atau 62; keduanya dirapikan sendiri. Kolomnya "
              "berformat teks supaya angka 0 di depan tidak hilang."),
    ("Jangan diubah", "Urutan dan jumlah kolom. Program membaca CSV dari POSISI "
                      "kolom, bukan judulnya - menukar kolom merusak tanpa pesan galat."),
    ("Menyimpan", "File > Save As > CSV (Comma delimited), taruh di folder data\\."),
]


def bangun() -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    ws = wb.active
    ws.title = "Data"

    ws["A1"] = "Template Pendaftaran BALITA (0-6 tahun) - CKG"
    ws["A1"].font = Font(size=14, bold=True)
    ws["A2"] = ("Isi mulai baris 5. Berat dan tinggi badan TIDAK diisi di sini - "
                "keduanya diturunkan dari umur dan jenis kelamin. Lihat lembar Panduan.")
    ws["A2"].font = Font(italic=True, color="666666")

    kepala = Font(bold=True, color="FFFFFF")
    latar = PatternFill("solid", fgColor="2F5597")
    tepi = Border(*[Side(style="thin", color="BFBFBF")] * 4)
    for i, (judul, lebar, _fmt, _daftar) in enumerate(KOLOM, start=1):
        sel = ws.cell(row=4, column=i, value=judul)
        sel.font, sel.fill, sel.border = kepala, latar, tepi
        sel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = lebar
    ws.row_dimensions[4].height = 30

    # Format dipasang ke SELURUH rentang isian, bukan hanya baris contoh.
    for i, (_judul, _lebar, fmt, _daftar) in enumerate(KOLOM, start=1):
        if fmt == "General":
            continue
        for r in range(5, 5 + BARIS_ISI):
            ws.cell(row=r, column=i).number_format = fmt

    for i, nilai in enumerate(CONTOH, start=1):
        if nilai != "":
            ws.cell(row=5, column=i, value=nilai)
    # Nomor urut mengisi dirinya sendiri begitu NIK diketik.
    for r in range(5, 5 + BARIS_ISI):
        ws.cell(row=r, column=1, value=f'=IF($B{r}="","",ROW()-4)')
    ws.cell(row=5, column=3).font = Font(color="808080", italic=True)

    ref = wb.create_sheet("Referensi")
    for k, (nama, isi) in enumerate(PILIHAN.items(), start=1):
        ref.cell(row=1, column=k, value=nama).font = Font(bold=True)
        for r, nilai in enumerate(isi, start=2):
            ref.cell(row=r, column=k, value=nilai)
        huruf = get_column_letter(k)
        aturan = DataValidation(
            type="list", formula1=f"=Referensi!${huruf}$2:${huruf}${len(isi) + 1}",
            allow_blank=True, showDropDown=False)
        aturan.error = f"Pilih salah satu: {', '.join(isi)}"
        aturan.errorTitle = "Nilai tidak dikenal"
        ws.add_data_validation(aturan)
        for i, (_j, _l, _f, daftar) in enumerate(KOLOM, start=1):
            if daftar == nama:
                huruf_kolom = get_column_letter(i)
                aturan.add(f"{huruf_kolom}5:{huruf_kolom}{4 + BARIS_ISI}")

    pan = wb.create_sheet("Panduan")
    pan["A1"] = "Panduan pengisian - Template BALITA"
    pan["A1"].font = Font(size=13, bold=True)
    pan.column_dimensions["A"].width = 30
    pan.column_dimensions["B"].width = 96
    for r, (judul, isi) in enumerate(PANDUAN, start=3):
        pan.cell(row=r, column=1, value=judul).font = Font(bold=True)
        sel = pan.cell(row=r, column=2, value=isi)
        sel.alignment = Alignment(wrap_text=True, vertical="top")
        pan.row_dimensions[r].height = 30

    ws.freeze_panes = "A5"
    tujuan = config.AKAR / "template" / "Template CKG BALITA.xlsx"
    tujuan.parent.mkdir(parents=True, exist_ok=True)
    wb.save(tujuan)
    return tujuan


if __name__ == "__main__":
    p = bangun()
    print(f"Template balita dibuat -> {p}")
    print(f"   {len(KOLOM)} kolom · format dikunci sampai baris {4 + BARIS_ISI}")
