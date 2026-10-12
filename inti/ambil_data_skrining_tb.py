"""
Ubah lembar "Skrining" pemantauan TBC menjadi CSV Dewasa/Lansia REAL DATA.

    python inti\\ambil_data_skrining_tb.py "C:\\...\\Jakarta Utara_Koja_Pustu Lagoa_14 Agustus 2026.xlsx"
    python inti\\ambil_data_skrining_tb.py "...xlsx" --maks 100

BENTUK BERKAS SUMBER
    Lembar "Skrining": baris 1-6 judul, baris 7 kepala bertingkat, baris 8
    kepala kolom, baris 9 CONTOH (dilewati), data mulai baris 10.

KENAPA REAL DATA, BUKAN PARAMETER
    Berkas ini memuat HASIL UKUR SUNGGUHAN - berat, tinggi, lingkar perut,
    tensi, gula darah, serta hasil periksa mata, telinga, dan gigi. Semuanya
    dipakai apa adanya; tidak ada yang diturunkan dari kata "Normal/Tinggi"
    seperti pada tata letak PARAMETER.
"""
from __future__ import annotations

import csv
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config                                    # noqa: E402
from peserta import bersihkan_nama               # noqa: E402
from ambil_data_umum import rapikan_nik          # noqa: E402
from ambil_data_sekolah import dari_nik          # noqa: E402

BARIS_DATA = 10          # baris 9 adalah baris CONTOH bawaan berkas
# Kolom sumber
S_NO, S_NAMA, S_JK, S_LAHIR, S_NIK, S_KERJA, S_ALAMAT, S_HP = 1, 2, 3, 4, 5, 6, 7, 8
S_BB, S_TB, S_IMT, S_LP, S_TENSI, S_GDS = 14, 15, 16, 17, 18, 19
S_MATA, S_TELINGA, S_GIGI = 20, 21, 22
S_MEROKOK, S_DM, S_KESIMPULAN = 24, 25, 33

# Kolom keluaran = template "DEWASA-LANSIA (real data)", 34 kolom.
TETAP = {
    7: "DKI Jakarta", 8: "Kota Adm. Jakarta Utara", 9: "Koja", 10: "Lagoa",
    15: "Tidak",        # riwayat hipertensi - tidak ada di berkas sumber
    25: "Normal", 26: "Normal", 27: "Normal",       # frambusia, kusta, skabies
    28: "Normal",       # TB X-Ray: kegiatannya "Tanpa Rontgen"
    30: "Normal",       # kesehatan jiwa
    31: "Normal", 32: "Normal", 33: "Normal", 34: "Normal",
}

# Pekerjaan di berkas ditulis bebas; portal hanya menerima pilihan tertentu.
# Yang dipakai di sini adalah nilai yang SUDAH TERBUKTI diterima portal pada
# jalan-jalan sebelumnya - bukan tebakan baru.
# Dicocokkan dengan POLA, bukan tulisan utuh: tiap berkas menulis dengan
# gayanya sendiri - "IRT" di berkas 14 Agustus, "IBU RUMAH TANGGA" di berkas
# 18 Agustus, "BURUH HARIAN LEPAS" di tempat lain lagi. Mencocokkan utuh
# berarti tiap berkas baru menjatuhkan puluhan orang ke nilai cadangan.
PEKERJAAN = (
    (r"ibu rumah tangga|^irt$",            "Belum/Tidak Bekerja"),
    (r"tidak bekerja|belum bekerja",       "Belum/Tidak Bekerja"),
    (r"pensiun",                           "Belum/Tidak Bekerja"),
    (r"buruh|kuli",                        "Pekerja Pabrik / Buruh"),
    # HARUS sesudah aturan wirausaha di bawah? Tidak - justru dijaga di sini:
    # "wiraswasta" memuat kata "swasta", jadi pencocokan longgar akan
    # menyeretnya jadi Pegawai Swasta. Batas kata membedakan keduanya.
    (r"karyawan|pegawai swasta|swasta", "Pegawai Swasta"),
    (r"asn|pns|pemerintah",             "ASN (Kantor Pemerintah)"),
    (r"mahasiswa",                         "Mahasiswa"),
    (r"pelajar|siswa|sekolah",             "Pelajar"),
    (r"guru|dosen|pengajar",               "Guru"),
    (r"wiraswasta|wirausaha|pedagang|dagang|usaha|seniman",
                                           "Wirausaha/Pekerja Mandiri"),
    (r"petani|kebun|pekebun",              "Petani / Pekebun"),
    (r"ternak|peternak",                   "Peternak"),
    # Nelayan tidak ada di daftar portal yang kita ketahui; yang
    # terdekat pekerja mandiri. Hanya 2 orang, dan dicatat.
    (r"nelayan",                           "Wirausaha/Pekerja Mandiri"),
)
KERJA_CADANGAN = "Belum/Tidak Bekerja"

# Rentang lingkar perut yang dipakai `peserta._ukuran_gizi()` untuk tiap
# kategori. Kategorinya dipilih yang rentangnya PALING DEKAT dengan lingkar
# perut sungguhan, supaya angka nyata di berkas tidak terbuang percuma.
LP_KATEGORI = {"Kurus": (60, 72), "Normal": (70, 85), "Gemuk": (90, 105)}


def _teks(ws, r: int, k: int) -> str:
    """
    Isi sel sebagai teks.

    Sel berisi ANGKA dibulatkan tanpa koma. Tanpa ini, NIK yang tersimpan
    sebagai angka terbaca "140705541282001.0" - lalu dilaporkan "17 digit,
    ada yang bukan angka", padahal sebenarnya 15 digit. Laporan yang salah
    membuat orang mencari masalah yang tidak ada.
    """
    v = ws.cell(row=r, column=k).value
    if isinstance(v, float) and v.is_integer():
        return f"{v:.0f}"
    if isinstance(v, int):
        return str(v)
    return str(v or "").strip()


def _angka(nilai, bulat: bool = True):
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(nilai or "").replace(",", "."))
    if not m:
        return None
    x = float(m.group())
    return round(x) if bulat else x


def _tanggal(nilai) -> date | None:
    if isinstance(nilai, datetime):
        return nilai.date()
    if isinstance(nilai, date):
        return nilai
    teks = str(nilai or "").strip()
    for bentuk in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(teks[:10], bentuk).date()
        except ValueError:
            pass
    return None


def _kategori_lp(lp: int | None, kelamin: str) -> str:
    """Kategori gizi dari lingkar perut sungguhan; rentang terdekat yang dipakai."""
    if lp is None:
        return "Normal"
    def jarak(rentang):
        a, b = rentang
        return 0 if a <= lp <= b else min(abs(lp - a), abs(lp - b))
    return min(LP_KATEGORI, key=lambda k: jarak(LP_KATEGORI[k]))


def olah(sumber: Path, maks: int = 0) -> tuple[list[list], list[str]]:
    from openpyxl import load_workbook

    wb = load_workbook(sumber, data_only=True)
    ws = wb["Skrining"] if "Skrining" in wb.sheetnames else wb.worksheets[0]

    keluaran: list[list] = []
    catatan: list[str] = []
    terlihat: set[str] = set()
    kerja_asing: set[str] = set()

    for r in range(BARIS_DATA, ws.max_row + 1):
        nik = _teks(ws, r, S_NIK)
        nama_asli = _teks(ws, r, S_NAMA)
        if not nik or not nama_asli or nama_asli.upper() == "CONTOH":
            continue

        nik, _soal_nik = rapikan_nik(nik)
        if len(nik) != 16 or not nik.isdigit():
            catatan.append(f"baris {r} · {nik} · {nama_asli} · DIBUANG, NIK CACAT: "
                           f"{_soal_nik or str(len(nik)) + ' digit'}")
            continue
        if nik.endswith("0000"):
            catatan.append(f"baris {r} · {nik} · {nama_asli} · DIBUANG, NIK RUSAK: "
                           "berakhir 0000, digit ke-16 hilang di Excel")
            continue
        if nik in terlihat:
            catatan.append(f"baris {r} · {nik} · {nama_asli} · DILEWATI, NIK kembar")
            continue
        terlihat.add(nik)

        nama = bersihkan_nama(nama_asli)
        if nama != nama_asli:
            catatan.append(f"baris {r} · {nik} · nama dirapikan: {nama_asli!r} -> {nama!r}")

        lahir_berkas = _tanggal(ws.cell(row=r, column=S_LAHIR).value)
        lahir_nik, kelamin_nik = dari_nik(nik)
        # NIK yang digit tanggalnya MUSTAHIL bukan NIK - aturan tetapnya jelas:
        # NIK yang salah jangan dimasukkan. Dulu ia lolos, sebab tanggal lahir
        # dari berkas dipakai sebagai cadangan; hasilnya seorang peserta (18 Sep,
        # NIK berbunyi bulan 17) dikirim ke portal dan ditolak. Pemeriksaan
        # yang sama sudah lama berlaku di pilah_kunjungan dan penyiap data jiwa.
        if lahir_nik is None:
            catatan.append(f"baris {r} · {nik} · {nama} · DIBUANG, NIK CACAT: "
                           f"digit tanggalnya mustahil ({nik[6:8]}/{nik[8:10]}/{nik[10:12]})")
            continue
        lahir = lahir_berkas or lahir_nik
        if not lahir:
            catatan.append(f"baris {r} · {nik} · {nama} · DIBUANG: tanggal lahir tak terbaca")
            continue
        if lahir_nik and lahir_berkas and lahir_nik != lahir_berkas:
            catatan.append(f"baris {r} · {nik} · {nama} · tanggal lahir DISESUAIKAN ke NIK: "
                           f"{lahir_berkas:%d/%m/%Y} -> {lahir_nik:%d/%m/%Y}")
            lahir = lahir_nik

        jk_berkas = _teks(ws, r, S_JK).replace(" ", "").lower()   # "Laki - Laki"
        kelamin_berkas = ("Laki-laki" if jk_berkas.startswith("laki")
                          else "Perempuan" if jk_berkas.startswith("perempuan") else "")
        if kelamin_nik and kelamin_berkas and kelamin_nik != kelamin_berkas:
            catatan.append(f"baris {r} · {nik} · {nama} · jenis kelamin DISESUAIKAN ke NIK: "
                           f"{kelamin_berkas} -> {kelamin_nik}")
        kelamin = kelamin_nik or kelamin_berkas or "Laki-laki"

        kerja_asli = _teks(ws, r, S_KERJA)
        rendah = kerja_asli.lower().strip()
        kerja = next((nilai for pola, nilai in PEKERJAAN if re.search(pola, rendah)), "")
        if not kerja:
            kerja = KERJA_CADANGAN
            if kerja_asli:
                kerja_asing.add(kerja_asli)

        umur = lahir and (date.today().year - lahir.year
                          - ((date.today().month, date.today().day) < (lahir.month, lahir.day)))
        # Status pernikahan TIDAK ADA di berkas sumber. Portal mewajibkannya,
        # jadi harus diisi sesuatu - dipilih menurut umur, dan setiap barisnya
        # dicatat supaya jelas ini turunan, bukan data.
        nikah = "Menikah" if (umur or 0) >= 21 else "Belum Menikah"

        bb, tb = _angka(ws.cell(row=r, column=S_BB).value), _angka(ws.cell(row=r, column=S_TB).value)
        lp = _angka(ws.cell(row=r, column=S_LP).value)
        gds = _angka(ws.cell(row=r, column=S_GDS).value)
        tensi = _teks(ws, r, S_TENSI)
        if not re.match(r"^\d{2,3}\s*/\s*\d{2,3}$", tensi):
            catatan.append(f"baris {r} · {nik} · {nama} · tensi tak terbaca ({tensi!r}), dikosongkan")
            tensi = ""
        else:
            # ANGKA YANG MUSTAHIL IKUT DIKOSONGKAN, bukan cuma yang tak terbaca.
            #
            # "14/69" lolos pemeriksaan bentuk di atas - dua angka dipisah
            # garis miring - padahal sistol 14 tidak ada pada manusia hidup;
            # yang dimaksud hampir pasti 140/69. Portal MENOLAK angka seperti
            # itu di form Tekanan Darah, dan penolakannya tidak berhenti di
            # formnya saja: daftar layanan peserta itu ikut kosong dan tidak
            # pulih. Terjadi pada seorang peserta (18 Sep), satu-satunya dari 100
            # peserta yang tensinya di luar rentang - dan satu-satunya yang
            # tersangkut.
            #
            # Dikosongkan berarti "turunkan sendiri dari parameter", bukan
            # ditebak: menulis 140 atas nama petugas sama saja mengarang hasil
            # ukur.
            sis, dia = (int(x) for x in re.split(r"\s*/\s*", tensi))
            if not (70 <= sis <= 250 and 40 <= dia <= 150):
                catatan.append(f"baris {r} · {nik} · {nama} · tensi MUSTAHIL "
                               f"({tensi}) - sistol {sis}, diastol {dia}; dikosongkan "
                               "supaya form Tekanan Darah tidak ditolak portal")
                tensi = ""
        if not bb or not tb:
            catatan.append(f"baris {r} · {nik} · {nama} · berat/tinggi kosong "
                           f"(bb={bb}, tb={tb}) - form gizi akan memakai turunan")

        mata = _teks(ws, r, S_MATA).lower()
        telinga = _teks(ws, r, S_TELINGA).lower()
        gigi = _teks(ws, r, S_GIGI).lower()
        # Sumber menyatukan mata dan telinga jadi dua kolom, portal memakai satu.
        # "Tidak Normal" bila SALAH SATU tidak normal - menurunkan temuan jadi
        # "Normal" berarti menghilangkan rujukan yang seharusnya terbit.
        mt = "Tidak Normal" if ("curiga" in mata or "impaksi" in telinga) else "Normal"
        karies = "Tidak Normal" if "karies" in gigi else "Normal"
        # "Gigi dicabut" = gigi hilang, yang ditanyakan form Periodontal.
        periodontal = "Tidak Normal" if "dicabut" in gigi else "Normal"
        tbc = ("Tidak Normal" if "ada gejala" in _teks(ws, r, S_KESIMPULAN).lower()
               and not _teks(ws, r, S_KESIMPULAN).lower().startswith("tidak") else "Normal")

        baris = [""] * 34
        baris[0] = str(len(keluaran) + 1)
        baris[1] = nik
        baris[2] = nama
        baris[3] = lahir.strftime("%d/%m/%Y")
        baris[4] = kelamin
        baris[5] = re.sub(r"\D", "", _teks(ws, r, S_HP)) or config.NOHP_CADANGAN
        baris[10] = " ".join(_teks(ws, r, S_ALAMAT).split()) or "Lagoa"
        baris[11] = nikah
        baris[12] = kerja
        baris[13] = "Ya" if _teks(ws, r, S_MEROKOK).lower().startswith("ya") else "Tidak"
        baris[15] = "Ya" if _teks(ws, r, S_DM).lower().startswith("ya") else "Tidak"
        baris[16] = str(gds) if gds else ""
        baris[17] = tensi
        baris[18] = str(bb) if bb else ""
        baris[19] = str(tb) if tb else ""
        baris[20] = _kategori_lp(lp, kelamin)
        baris[21] = mt
        baris[22] = karies
        baris[23] = periodontal
        baris[28] = tbc
        for kolom, nilai in TETAP.items():
            baris[kolom - 1] = nilai
        keluaran.append(baris)
        if maks and len(keluaran) >= maks:
            break

    if kerja_asing:
        catatan.insert(0, f"pekerjaan tak dikenal -> {KERJA_CADANGAN}: {sorted(kerja_asing)}")
    catatan.insert(0, f"{len(keluaran)} peserta diambil · status pernikahan DITURUNKAN "
                      "dari umur (tidak ada di berkas sumber)")
    return keluaran, catatan


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    sumber = Path(sys.argv[1])
    maks = int(sys.argv[sys.argv.index("--maks") + 1]) if "--maks" in sys.argv else 0

    baris, catatan = olah(sumber, maks)
    if not baris:
        print("Tidak ada peserta terbaca.")
        raise SystemExit(1)

    nama_berkas = re.sub(r"[^a-z0-9]+", "-", sumber.stem.lower()).strip("-")[:48]
    tujuan = config.DATA / f"datackg-{nama_berkas}.csv"
    with tujuan.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(baris)
    print(f"{len(baris)} peserta -> {tujuan}")

    periksa = config.HASIL / "periksa" / f"_tb-{nama_berkas}.txt"
    periksa.parent.mkdir(parents=True, exist_ok=True)
    periksa.write_text("\n".join(catatan), encoding="utf-8")
    print(f"\n{len(catatan)} hal perlu dicek manusia -> {periksa}")
    for c in catatan[:10]:
        print(f"   {c}")
    if len(catatan) > 10:
        print(f"   ... dan {len(catatan) - 10} lagi")


if __name__ == "__main__":
    main()
