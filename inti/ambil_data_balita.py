"""
Saring peserta BALITA (0-6 tahun) dari buku kunjungan rawat jalan puskesmas.

    python inti\\ambil_data_balita.py "C:\\...\\KUNJUNGAN PUSTU LAGOA JUNI 2026.xlsx"
    python inti\\ambil_data_balita.py "...xlsx" --kelurahan Lagoa --maks 200

BENTUK BERKAS SUMBER
    Buku kunjungan SEMUA UMUR, bukan daftar balita. Baris 1-3 judul, baris 4
    kepala kolom, data mulai baris 5. Kolomnya: No, Jam, #MRN, Nama Pasien,
    L/P, "Tgl. Lahir / Umur", NIK, No. BPJS, Alamat, L/B.

    Kolom tanggal lahirnya GABUNGAN: "06-APR-2014 (12 Thn)\\n0". Yang dipakai
    tanggalnya, bukan angka umur di dalam kurung - umur itu terhitung saat
    kunjungan, sedangkan yang menentukan kategori CKG adalah umur HARI INI.

    Satu pasien bisa berkunjung beberapa kali dalam sebulan, jadi barisnya
    kembar. Diambil kunjungan PERTAMA tiap NIK.
"""
from __future__ import annotations

import csv
import random
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config                                    # noqa: E402
from peserta import bersihkan_nama               # noqa: E402
from ambil_data_umum import rapikan_nik          # noqa: E402
from ambil_data_sekolah import dari_nik          # noqa: E402

# Batas kategori: 0 sampai 6 tahun penuh - sampai sehari sebelum ulang tahun
# ke-7. Inilah rentang yang membuat portal memunculkan bagian "Data Wali".
UMUR_MAKS = 7

BARIS_DATA = 5
K_NAMA, K_KELAMIN, K_LAHIR, K_NIK, K_ALAMAT = 4, 5, 6, 7, 9

# Kolom keluaran = tata letak BALITA (18 kolom) yang dikenali `peserta.py`.
# Nilainya tetap; yang berubah-ubah hanya identitas dan alamat.
TETAP = {
    6: "DKI Jakarta", 7: "Kota Adm. Jakarta Utara", 8: "Koja", 9: "Lagoa",
    11: "Belum Menikah", 12: "Tidak Bekerja",
    14: "Tidak",          # penyandang disabilitas
    15: "normal",         # berat lahir  -> 2600-3500 g
    16: "normal",         # berat saat ini -> sekitar berat ideal WHO
    17: "Ya",             # riwayat imunisasi - katalog menetapkan Ya/Tidak,
                          # bukan "Lengkap" yang tidak dikenal form mana pun
    18: "normal",         # status gizi
}

_BULAN = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6, "JUL": 7,
          "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
          "MEI": 5, "AGU": 8, "OKT": 10, "DES": 12}
_POLA_TANGGAL = re.compile(r"(\d{1,2})[-/\s]([A-Za-z]{3,4})[-/\s](\d{2,4})")


def tanggal_kunjungan(nilai) -> date | None:
    """
    Baca tanggal lahir dari kolom gabungan "06-APR-2014 (12 Thn)".

    Bulannya singkatan Inggris (kadang Indonesia), jadi `strptime` bergantung
    pada locale mesin - dan itu berbeda antar komputer petugas. Dipetakan
    sendiri supaya hasilnya sama di mana pun.
    """
    if isinstance(nilai, datetime):
        return nilai.date()
    if isinstance(nilai, date):
        return nilai
    m = _POLA_TANGGAL.search(str(nilai or ""))
    if not m:
        return None
    hari, bulan, tahun = int(m.group(1)), _BULAN.get(m.group(2).upper()), int(m.group(3))
    if not bulan:
        return None
    if tahun < 100:
        tahun += 2000 if tahun <= 30 else 1900
    try:
        return date(tahun, bulan, hari)
    except ValueError:
        return None


def umur_tahun(lahir: date, acuan: date) -> int:
    """Umur dalam tahun penuh - bukan pembagian 365, yang meleset di tanggal batas."""
    return acuan.year - lahir.year - ((acuan.month, acuan.day) < (lahir.month, lahir.day))


def olah(sumber: Path, maks: int = 0) -> tuple[list[list], list[str]]:
    from openpyxl import load_workbook

    wb = load_workbook(sumber, data_only=True)
    ws = wb.worksheets[0]
    hari_ini = date.today()

    keluaran: list[list] = []
    catatan: list[str] = []
    terlihat: set[str] = set()
    jumlah_baris = bukan_balita = 0

    for r in range(BARIS_DATA, ws.max_row + 1):
        nama_asli = str(ws.cell(row=r, column=K_NAMA).value or "").strip()
        nik = str(ws.cell(row=r, column=K_NIK).value or "").strip()
        if not nama_asli or not nik:
            continue
        jumlah_baris += 1

        lahir_berkas = tanggal_kunjungan(ws.cell(row=r, column=K_LAHIR).value)
        lahir_nik, kelamin_nik = dari_nik(nik)
        lahir = lahir_berkas or lahir_nik
        if not lahir:
            catatan.append(f"baris {r} · {nik} · {nama_asli} · DILEWATI: "
                           "tanggal lahir tidak terbaca")
            continue

        umur = umur_tahun(lahir, hari_ini)
        if not 0 <= umur < UMUR_MAKS:
            bukan_balita += 1
            continue

        # Satu pasien bisa berkunjung berkali-kali dalam sebulan.
        if nik in terlihat:
            continue
        terlihat.add(nik)

        nik, _soal_nik = rapikan_nik(nik)
        if len(nik) != 16 or not nik.isdigit():
            catatan.append(f"baris {r} · {nik} · {nama_asli} · DIBUANG, NIK CACAT: "
                           f"{_soal_nik or str(len(nik)) + ' digit'}")
            terlihat.discard(nik)
            continue
        # Enam belas angka yang BUKAN NIK: bayi yang NIK-nya belum terbit diberi
        # nomor sementara oleh klinik. Portal pasti menolaknya, dan jalan
        # resminya bukan lewat sini melainkan lewat centang "Tidak punya NIK" -
        # alur tersendiri yang belum kita bangun. Dikeluarkan supaya tidak
        # menghabiskan waktu jalan hanya untuk ditolak satu per satu.
        if not lahir_nik:
            catatan.append(f"baris {r} · {nik} · {nama_asli} · DIBUANG, nomor ini "
                           "bukan NIK (kemungkinan nomor sementara bayi) - "
                           "perlu jalur 'Tidak punya NIK'")
            terlihat.discard(nik)
            continue

        nama = bersihkan_nama(nama_asli)
        if nama != nama_asli:
            catatan.append(f"baris {r} · {nik} · nama dirapikan: {nama_asli!r} -> {nama!r}")

        kelamin_berkas = {"L": "Laki-laki", "P": "Perempuan"}.get(
            str(ws.cell(row=r, column=K_KELAMIN).value or "").strip().upper(), "")
        # NIK terbit dari Dukcapil; kolom di buku kunjungan ditulis tangan.
        # Bila berselisih, NIK yang menang - dan penyesuaiannya dicatat.
        if lahir_nik and lahir_berkas and lahir_nik != lahir_berkas:
            catatan.append(f"baris {r} · {nik} · {nama} · tanggal lahir DISESUAIKAN "
                           f"ke NIK: {lahir_berkas:%d/%m/%Y} -> {lahir_nik:%d/%m/%Y}")
            lahir = lahir_nik
            umur = umur_tahun(lahir, hari_ini)
            if not 0 <= umur < UMUR_MAKS:
                catatan.append(f"baris {r} · {nik} · {nama} · DIBUANG: menurut NIK "
                               f"umurnya {umur} th, di luar 0-{UMUR_MAKS - 1}")
                continue
        if kelamin_nik and kelamin_berkas and kelamin_nik != kelamin_berkas:
            catatan.append(f"baris {r} · {nik} · {nama} · jenis kelamin DISESUAIKAN "
                           f"ke NIK: {kelamin_berkas} -> {kelamin_nik}")
        kelamin = kelamin_nik or kelamin_berkas or "Laki-laki"

        alamat = " ".join(str(ws.cell(row=r, column=K_ALAMAT).value or "").split()).strip()

        baris = [""] * 18
        baris[0] = str(len(keluaran) + 1)
        baris[1] = nik
        baris[2] = nama
        baris[3] = lahir.strftime("%d/%m/%Y")
        baris[4] = kelamin
        baris[9] = alamat or "Lagoa"
        baris[12] = config.NOHP_CADANGAN
        for kolom, nilai in TETAP.items():
            baris[kolom - 1] = nilai
        keluaran.append(baris)
        if maks and len(keluaran) >= maks:
            break

    catatan.insert(0, f"dibaca {jumlah_baris} baris kunjungan · "
                      f"{bukan_balita} di luar umur 0-{UMUR_MAKS - 1} · "
                      f"{len(keluaran)} balita diambil (kunjungan pertama tiap NIK)")
    return keluaran, catatan


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    sumber = Path(sys.argv[1])
    maks = 0
    if "--maks" in sys.argv:
        maks = int(sys.argv[sys.argv.index("--maks") + 1])

    baris, catatan = olah(sumber, maks)
    if not baris:
        print("Tidak ada peserta berumur 0-6 tahun di berkas ini.")
        raise SystemExit(1)

    nama_berkas = re.sub(r"[^a-z0-9]+", "-", sumber.stem.lower()).strip("-")
    tujuan = config.DATA / f"datackg-balita-{nama_berkas}.csv"
    with tujuan.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(baris)
    print(f"{len(baris)} balita -> {tujuan}")

    umur = {}
    hari_ini = date.today()
    for b in baris:
        d, m, y = (int(x) for x in b[3].split("/"))
        umur[umur_tahun(date(y, m, d), hari_ini)] = umur.get(
            umur_tahun(date(y, m, d), hari_ini), 0) + 1
    print("   sebaran umur: " + ", ".join(f"{u} th: {n}" for u, n in sorted(umur.items())))

    periksa = config.HASIL / "periksa" / f"_balita-{nama_berkas}.txt"
    periksa.parent.mkdir(parents=True, exist_ok=True)
    periksa.write_text("\n".join(catatan), encoding="utf-8")
    print(f"\n{len(catatan) - 1} hal perlu dicek manusia -> {periksa}")
    for c in catatan[:10]:
        print(f"   {c}")
    if len(catatan) > 10:
        print(f"   ... dan {len(catatan) - 10} lagi")


if __name__ == "__main__":
    main()
