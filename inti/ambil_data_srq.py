"""
Ambil data peserta dari laporan SRQ (.xlsx) menjadi CSV siap pakai.

    python ambil_data_srq.py <berkas.xlsx> <baris_awal> <baris_akhir>
                             [umur_minimal] [jumlah_peserta]

    18 pada umur_minimal berarti dewasa/lansia saja.

Contoh:
    python ambil_data_srq.py "C:\\Users\\dava5\\Downloads\\ReportSrq.xlsx" 1000 1100

Menghasilkan dua berkas:
    data-srq-<awal>-<akhir>.csv        peserta yang datanya layak
    _srq-<awal>-<akhir>-ditolak.csv    baris bermasalah + sebabnya

Kenapa ada penyaringan: laporan SRQ diisi manusia, dan sudah terbukti ada baris
yang kolom Nama Pasien-nya justru berisi alamat. Kalau ikut terkirim, peserta
tercatat di portal dengan nama berupa alamat - dan itu tidak bisa dibatalkan.
"""
from __future__ import annotations

import csv
import re
import sys
from datetime import date
from pathlib import Path

import openpyxl

AKAR = Path(__file__).resolve().parent.parent
DATA = AKAR / "data"
PERIKSA = AKAR / "hasil" / "periksa"

# Kata yang menandakan sebuah "nama" sebenarnya alamat.
_POLA_ALAMAT = re.compile(
    r"^(jl|jln|jalan|gg|gang|kp|kampung|komp|komplek|perum|blok|rt|rw|no)\b|"
    r"\brt[\s.]*\d|\brw[\s.]*\d|\bno[\s.]*\d",
    re.I)


def masalah_nama(nama: str) -> str:
    """Sebab nama ditolak, atau '' bila wajar."""
    n = (nama or "").strip()
    if len(n) < 3:
        return "nama terlalu pendek"
    if _POLA_ALAMAT.search(n):
        return "nama berpola alamat"
    if re.search(r"\d", n):
        return "nama mengandung angka"
    # Dihitung JUMLAH hurufnya, bukan tiga huruf berurutan: data ini penuh nama
    # yang ditulis berspasi antar-huruf ("Y A Y A H", "A S R I", "E R U"), dan
    # aturan berurutan menolaknya sebagai bukan-nama.
    if len(re.sub(r"[^A-Za-z]", "", n)) < 3:
        return "nama tanpa huruf"
    return ""


def beda_nik(nik: str, hari: int, bulan: int, tahun: int, jk: str) -> str:
    """
    Bandingkan NIK dengan tanggal lahir dan jenis kelamin.

    Digit 7-12 NIK memuat tanggal lahir (tanggal ditambah 40 untuk perempuan),
    jadi ketidakcocokan menandakan salah satunya salah ketik. Terbukti nyata:
    Mega Lestari gagal daftar karena NIK-nya keliru, dan NIK itu menyandikan
    03/08/14 sedangkan tanggal lahirnya 17/10/1997.

    HANYA PERINGATAN, bukan alasan menolak. Dari 100 baris yang diperiksa,
    22 tidak cocok namun 16 di antaranya tetap berhasil didaftarkan - menolak
    semuanya berarti membuang pendaftaran yang sah.
    """
    h, b, t = int(nik[6:8]), int(nik[8:10]), int(nik[10:12])
    perempuan = h > 40
    if perempuan:
        h -= 40
    beda = []
    if (h, b) != (hari, bulan):
        beda.append(f"tanggal NIK {h:02d}/{b:02d} vs {hari:02d}/{bulan:02d}")
    if t != tahun % 100:
        beda.append(f"tahun NIK {t:02d} vs {tahun % 100:02d}")
    jk_nik = "Perempuan" if perempuan else "Laki-laki"
    if jk_nik != jk:
        beda.append(f"jenis kelamin NIK {jk_nik} vs {jk}")
    return "; ".join(beda)


def bersih(v) -> str:
    return re.sub(r"^'", "", str(v or "")).strip()


def judul(t) -> str:
    return " ".join(w.capitalize() for w in bersih(t).split())


def ambil(sumber: Path, awal: int, akhir: int,
          umur_min: int = 0, jumlah: int = 0) -> tuple[Path, Path]:
    """
    `umur_min` menyaring menurut usia (18 = dewasa/lansia saja), `jumlah`
    berhenti setelah sekian peserta terkumpul.

    Yang tersaring umur BUKAN "ditolak": datanya tidak bermasalah, cuma bukan
    kategori yang diminta. Karena itu ia tidak masuk berkas ditolak, hanya
    dihitung.
    """
    wb = openpyxl.load_workbook(sumber, read_only=True, data_only=True)
    semua = [r for r in wb["Worksheet"].iter_rows(min_row=8, values_only=True) if r and r[0]]
    wb.close()
    potong = semua[awal - 1:akhir]

    hari_ini = date.today()
    baik: list[list] = []
    tolak: list[list] = []
    dicek: list[list] = []
    nik_terpakai: set[str] = set()
    lewat_umur = 0

    for urut, r in enumerate(potong, awal):
        nik = re.sub(r"\D", "", bersih(r[0]))
        nama = bersih(r[1])
        tgl = bersih(r[2])
        m = re.fullmatch(r"(\d{2})-(\d{2})-(\d{4})", tgl)

        sebab = ""
        if len(nik) != 16:
            sebab = "NIK bukan 16 digit"
        elif not m:
            sebab = f"tanggal lahir tidak terbaca ({tgl})"
        elif nik in nik_terpakai:
            sebab = "NIK kembar di rentang ini"
        else:
            sebab = masalah_nama(nama)

        if sebab:
            tolak.append([urut, nik, nama, tgl, bersih(r[4]), sebab])
            continue

        h, b, y = (int(x) for x in m.groups())
        usia_calon = hari_ini.year - y - ((hari_ini.month, hari_ini.day) < (b, h))
        if umur_min and usia_calon < umur_min:
            lewat_umur += 1
            continue

        nik_terpakai.add(nik)
        jk_csv = "Laki-laki" if bersih(r[4]).lower().startswith("laki") else "Perempuan"
        selisih = beda_nik(nik, h, b, y, jk_csv)
        if selisih:
            dicek.append([urut, nik, nama, f"{h:02d}/{b:02d}/{y}", jk_csv, selisih])
        usia = usia_calon
        bulan = (hari_ini.year - y) * 12 + (hari_ini.month - b) - (1 if hari_ini.day < h else 0)
        jk = "Laki-laki" if bersih(r[4]).lower().startswith("laki") else "Perempuan"
        N = "Normal"
        baik.append([
            len(baik) + 1, nik, nama, f"{h:02d}/{b:02d}/{y}", jk,
            "DKI Jakarta", "Kota Adm. Jakarta Utara", judul(r[10]), judul(r[11]), bersih(r[12]),
            "", "",                      # status nikah & pekerjaan -> dari usia
            "Tidak", "Tidak", "Tidak",   # merokok, riwayat hipertensi, riwayat diabetes
            N, N, N, N, N, N, N, N, N,   # gula, tekanan, gizi, mata-telinga, gigi, tropis
            "Lansia" if usia > 60 else "Dewasa", bulan,
            N, N, N, N, N, N, N,         # TB, jiwa, geriatri, puma, payudara, iva
        ])
        if jumlah and len(baik) >= jumlah:
            break

    # Baris awal ikut masuk nama begitu bukan dari awal berkas. Tanpa itu, dua
    # pengambilan dengan jumlah sama akan bernama sama dan yang kedua menimpa
    # yang pertama tanpa suara.
    dari = f"dari{awal}-" if awal > 1 else ""
    tanda = (f"dewasa-{dari}{len(baik)}" if umur_min >= 18 else
             f"umur{umur_min}plus-{dari}{len(baik)}" if umur_min else f"{awal}-{akhir}")
    tujuan = DATA / f"data-srq-{tanda}.csv"
    with tujuan.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(baik)

    berkas_cek = PERIKSA / f"_srq-{tanda}-perlu-dicek.csv"
    with berkas_cek.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["baris_sumber", "NIK", "Nama", "Tanggal Lahir", "Jenis Kelamin",
                    "Ketidakcocokan"])
        w.writerows(dicek)

    berkas_tolak = PERIKSA / f"_srq-{tanda}-ditolak.csv"
    with berkas_tolak.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["baris_sumber", "NIK", "Nama", "Tanggal Lahir", "Jenis Kelamin", "Sebab"])
        w.writerows(tolak)

    print(f"terbaca  : {len(potong)} baris dari {sumber.name}")
    if umur_min:
        print(f"lewat umur: {lewat_umur} baris di bawah {umur_min} tahun (bukan kesalahan)")
    print(f"dipakai  : {len(baik)} peserta -> {tujuan.name}")
    print(f"ditolak  : {len(tolak)} baris   -> {berkas_tolak.name}")
    print(f"perlu dicek: {len(dicek)} baris NIK tak cocok tanggal lahir "
          f"-> {berkas_cek.name}")
    print("             (TETAP dipakai - sebagian besar tetap berhasil didaftarkan)")
    for t in tolak:
        print(f"   baris {t[0]}: {t[5]} | nama={t[2][:40]!r}")
    return tujuan, berkas_tolak


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        raise SystemExit(1)
    # Dua argumen terakhir opsional supaya pemakaian lama tetap berjalan apa
    # adanya: <xlsx> <awal> <akhir> [umur_min] [jumlah]
    umur_min = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    jumlah = int(sys.argv[5]) if len(sys.argv) > 5 else 0
    ambil(Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), umur_min, jumlah)
