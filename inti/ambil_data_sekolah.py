"""
Ubah "Register Kegiatan Kesehatan" sekolah menjadi CSV siap jalan.

    python inti\\ambil_data_sekolah.py "C:\\...\\Data SDN LAGOA 09.xlsx" 1 5

Argumen sesudah nama berkas adalah nomor kelas yang diambil. Tanpa itu, semua
kelas diambil.

BENTUK BERKAS SUMBER
    Satu lembar per kelas ("KELAS 1", "KELAS 2", ...), judulnya kadang berspasi
    ekor. Baris 1-8 judul dan kepala bertingkat, baris 9 penomoran kolom, data
    mulai baris 10. Kolomnya: No, Nama, NIK, Tgl Lahir, L/P, Disabilitas,
    Tinggi, Berat.

YANG PERLU DIKETAHUI
    Tinggi badan di berkas register ini SELALU KOSONG, sedangkan berat badan
    terisi. Karena itu tinggi dibangkitkan dari berat, bukan diarang bebas:
    dipilih supaya IMT-nya jatuh di rentang normal anak seusianya. Dengan
    begitu status gizi yang dihitung portal pasti "normal" - dan itu memang
    yang diminta, sebab register sekolah tidak memuat hasil ukur.

    Angka yang dibangkitkan BERSIFAT TETAP untuk tiap murid (diundi dari
    NIK-nya), jadi menjalankan ulang skrip ini tidak mengubah hasilnya.
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
from peserta import bersihkan_nama, tanggal_dari_teks   # noqa: E402
from ambil_data_umum import rapikan_nik          # noqa: E402

# Pembersihan NIK dipakai bersama SEMUA pengekstrak - lihat
# `ambil_data_umum.rapikan_nik`. Dulu tiap pengekstrak memeriksa NIK-nya
# sendiri dengan `len(nik) != 16 or not nik.isdigit()`, dan itu MEMBUANG
# NIK yang sebetulnya sah: register "MI AL IKHWAN" menyimpan NIK-nya dengan
# tanda kutip di depan ("'3172045901190000") - penanda "paksa jadi teks"
# milik Excel yang ikut terbawa ke nilainya. Ke-85 muridnya dibuang dengan
# alasan "17 digit, ada yang bukan angka", padahal NIK-nya utuh.


# Kolom keluaran = template "CKG SEKOLAH", 24 kolom, dikenali dari POSISINYA.
# Kolom 22 adalah Visus Mata - SATU kolom yang menyebut sisi yang terganggu
# ("Normal", "Visus Kanan", "Visus Kiri", "Visus Kanan dan Kiri"), bukan dua
# kolom kanan/kiri seperti sebelumnya.
TETAP = {
    6: "Tanjung Priok", 7: "Belum Menikah", 8: "Pelajar", 9: "", 10: "Tidak",
    13: "Normal", 14: "Normal", 20: "Normal", 21: "Tidak Ada",
    22: "Normal", 23: "Tidak", 24: "Baik",
}
# Kolom TIDAK dipatok. Register sekolah beredar dalam dua tata letak, dan
# keduanya sama-sama sah:
#
#   SDN LAGOA 09/11 : ... Disabilitas(6) Tinggi(7) Berat(8)
#   SDN LAGOA 02    : ... Disabilitas(6) Nama Ortu(7) No.HP Ortu(8) Tinggi(9) Berat(10)
#
# Mematok kolom 8 sebagai berat membuat berkas jenis kedua membaca NOMOR HP
# ORANG TUA sebagai berat badan anak - dan itu lolos semua pemeriksaan lain
# karena bentuknya tetap angka. Karena itu kolomnya dicari dari JUDULNYA.
KUNCI_KOLOM = (
    # Urutannya penting: "nama orang tua" harus diperiksa sebelum "nama",
    # kalau tidak kolom nama murid akan mengenai kolom orang tuanya.
    ("nama_ortu", r"nama\s*orang\s*tua"),
    ("nama",      r"^nama$"),
    ("nik",       r"^nik$"),
    ("lahir",     r"tanggal\s*lahir"),
    ("kelamin",   r"jns\s*klm|l\s*/\s*p|jenis\s*kelamin"),
    ("disabilitas", r"disabilitas"),
    ("tinggi",    r"tinggi"),
    ("berat",     r"berat"),
)


BERKAS_DAFTAR_SEKOLAH = "nama_sekolah_portal.txt"


def daftar_sekolah_portal() -> list[str]:
    """Nama sekolah persis seperti di portal, direkam dari dropdown "Pilih sekolah"."""
    f = config.AKAR / BERKAS_DAFTAR_SEKOLAH
    if not f.exists():
        return []
    return [x.strip() for x in f.read_text(encoding="utf-8").splitlines()
            if x.strip() and not x.lstrip().startswith("#")]


def _sederhana(nama: str) -> str:
    """
    Bentuk baku sebuah nama sekolah, untuk dibandingkan.

    Yang dibuang hanya hiasan yang TIDAK membedakan sekolah: tanda baca,
    "pagi"/"pg", "jakarta". Angkanya justru dipertahankan mati-matian - "Lagoa
    01" dan "Lagoa 09" cuma beda satu angka, dan menyamakan keduanya berarti
    mengirim ratusan murid ke sekolah yang salah.
    """
    s = re.sub(r"[^a-z0-9]+", " ", nama.lower())
    s = re.sub(r"\bsd\s+negeri\b", "sdn", s)
    s = re.sub(r"\bsmp\s+negeri\b", "smpn", s)
    s = re.sub(r"\b(pg|pagi|jakarta|standar nasional)\b", " ", s)
    return " ".join(s.split())


def cocokkan_sekolah(nama: str) -> tuple[str, str]:
    """
    Betulkan nama sekolah ke tulisan portal.

    Kembalikan (nama_terpakai, keterangan). Nama yang salah satu huruf pun
    membuat SELURUH murid sekolah itu gagal `tidak_ditemukan` - dan baru
    ketahuan sesudah satu putaran penuh terbuang. Sudah terjadi pada 219 murid
    SDN LAGOA 11, jadi pencocokannya dilakukan di sini, sebelum berkas dibuat.
    """
    daftar = daftar_sekolah_portal()
    if not daftar or not nama.strip():
        return nama, ""
    if nama in daftar:
        return nama, ""

    mau = _sederhana(nama)
    persis = [x for x in daftar if _sederhana(x) == mau]
    if persis:
        return persis[0], f"nama sekolah dibetulkan ke tulisan portal: {nama!r} -> {persis[0]!r}"

    # Angka di dalam nama WAJIB sama. Tanpa syarat ini "Lagoa 02" bisa
    # tersambung ke "Lagoa 05" hanya karena sisa katanya mirip.
    angka = set(re.findall(r"\d+", mau))
    calon = [x for x in daftar
             if set(re.findall(r"\d+", _sederhana(x))) == angka
             and (mau in _sederhana(x) or _sederhana(x) in mau)]
    if len(calon) == 1:
        return calon[0], f"nama sekolah dibetulkan ke tulisan portal: {nama!r} -> {calon[0]!r}"
    if calon:
        return nama, (f"nama sekolah {nama!r} cocok ke BEBERAPA nama portal "
                      f"{calon} - pilih sendiri, dipakai apa adanya dulu")
    return nama, (f"nama sekolah {nama!r} TIDAK ADA di daftar portal "
                  f"({len(daftar)} sekolah terekam) - murid sekolah ini akan "
                  "gagal 'tidak_ditemukan'")


def _sekolah_dari_berkas(wb) -> str:
    """Nama sekolah dari sel "NAMA SEKOLAH/MADRASAH :" bila memang diisi."""
    for ws in wb.worksheets:
        for r in range(1, 6):
            for k in range(1, 6):
                teks = str(ws.cell(row=r, column=k).value or "")
                m = re.search(r"NAMA\s+SEKOLAH[^:]*:\s*(.+)$", teks, re.I)
                if m and m.group(1).strip(" .:_-"):
                    return re.sub(r"\s+", " ", m.group(1)).strip(" .:_-")
    return ""


def _petakan_kolom(ws) -> tuple[int, dict]:
    """
    Cari baris data pertama dan peta kolomnya, dari kepala berjenjang.

    Kepalanya bertingkat ("Hasil Penjaringan" > "Tinggi" > "Bdn" > "(cm)"),
    jadi judul tiap kolom disusun dari BEBERAPA baris sekaligus. Baris
    penomoran (1,2,3,...) dipakai sebagai penanda batas: data mulai tepat di
    bawahnya, dan judulnya ada di baris-baris di atasnya.
    """
    baris_nomor = 0
    for r in range(1, min(20, ws.max_row) + 1):
        nilai = [ws.cell(row=r, column=k).value for k in range(1, 9)]
        angka = [str(v).strip() for v in nilai if v is not None]
        if len(angka) >= 6 and angka[:6] == ["1", "2", "3", "4", "5", "6"]:
            baris_nomor = r
            break
    if not baris_nomor:
        raise SystemExit("Baris penomoran kolom (1,2,3,...) tidak ditemukan.")

    judul = {}
    for k in range(1, ws.max_column + 1):
        potong = [str(ws.cell(row=r, column=k).value or "").strip()
                  for r in range(max(1, baris_nomor - 5), baris_nomor)]
        judul[k] = re.sub(r"\s+", " ", " ".join(x for x in potong if x)).strip().lower()

    peta = {}
    for nama_kunci, pola in KUNCI_KOLOM:
        for k, teks in judul.items():
            if k in peta.values() or not teks:
                continue
            if re.search(pola, teks):
                peta[nama_kunci] = k
                break
    kurang = [n for n in ("nama", "nik", "lahir") if n not in peta]
    if kurang:
        raise SystemExit(f"Kolom wajib tak ditemukan: {kurang}. Judul terbaca: {judul}")
    return baris_nomor + 1, peta


def _tanggal(nilai) -> date | None:
    """
    Tanggal lahir dari register - bentuk apa pun.

    Dulu di sini ada daftar empat bentuk sendiri ("%d-%m-%Y" dan kawan-kawan),
    dan itu membuat pengekstrak sekolah lebih picik daripada pembaca peserta
    yang sudah lentur: register MIS AL KHAIRIYAH PAGI menulis "13 Oktober 2019"
    dan SD Muhammadiyah 22 menulis "Jakarta, 15 Maret 2019" - keduanya ditolak
    di sini lalu diam-diam diganti tanggal turunan NIK, sehingga selisih yang
    seharusnya ketahuan justru tidak pernah muncul. Satu pembaca untuk semua.
    """
    return tanggal_dari_teks(nilai)


def dari_nik(nik: str) -> tuple[date | None, str]:
    """
    Baca tanggal lahir dan jenis kelamin yang TERTANAM di NIK.

    Digit 7-12 adalah hari-bulan-tahun lahir, dengan hari DITAMBAH 40 bila
    perempuan. Dipakai untuk mencocokkan, bukan menggantikan - NIK yang salah
    ketik justru itu yang ingin kita temukan.
    """
    if len(nik) != 16 or not nik.isdigit():
        return None, ""
    # Enam belas angka belum tentu NIK. Buku kunjungan puskesmas memuat nomor
    # sementara untuk bayi yang NIK-nya belum terbit - "1020252026011001",
    # "7778889994125477" - dan tanggal serta jenis kelamin yang "terbaca" dari
    # nomor begitu adalah kebetulan belaka. Menyesuaikan data peserta dengan
    # kebetulan jauh lebih berbahaya daripada tidak menyesuaikan sama sekali.
    #
    # Dua digit pertama adalah kode provinsi, dan hanya 11-94 yang dipakai.
    if not 11 <= int(nik[:2]) <= 94:
        return None, ""
    hh, bb, tt = int(nik[6:8]), int(nik[8:10]), int(nik[10:12])
    kelamin = "Perempuan" if hh > 40 else "Laki-laki"
    hh -= 40 if hh > 40 else 0
    # Tahun dua digit: murid SD-SMA tidak mungkin lahir sebelum 2000-an, tapi
    # ambang 30 memberi ruang bila berkas ini dipakai untuk data lain.
    tahun = 2000 + tt if tt <= 30 else 1900 + tt
    try:
        lahir = date(tahun, bb, hh)
    except ValueError:
        return None, kelamin
    # Tanggal lahir di masa depan berarti nomornya bukan NIK, apa pun bentuknya.
    return (lahir, kelamin) if lahir <= date.today() else (None, "")


# Tinggi badan lazim menurut umur (cm), median kasar rujukan pertumbuhan.
# Dipakai sebagai JANGKAR, bukan hiasan - lihat `_tinggi()`.
_TB_LAZIM = {
    "Laki-laki": {5: 110, 6: 116, 7: 122, 8: 128, 9: 133, 10: 138, 11: 144,
                  12: 150, 13: 157, 14: 163, 15: 168, 16: 170, 17: 171, 18: 172},
    "Perempuan": {5: 109, 6: 115, 7: 121, 8: 127, 9: 133, 10: 139, 11: 145,
                  12: 151, 13: 156, 14: 159, 15: 161, 16: 162, 17: 163, 18: 163},
}
GESER_MAKS = 8          # cm; sejauh mana tinggi boleh menyimpang dari lazimnya


def _imt_sasaran(usia: float, undi: random.Random) -> float:
    """
    IMT normal menurut umur: kelas awal lebih kurus, makin besar makin naik.

    Angkanya mengikuti berkas SD yang sudah berhasil dijalankan sebelumnya
    (13,7-18,6), bukan karangan baru - supaya hasil portal tetap seragam.
    """
    dasar = 13.9 + (max(usia, 5.0) - 6.0) * 0.30
    return min(18.0, max(13.7, dasar + undi.uniform(-0.35, 0.45)))


def _tinggi(berat: float, usia: float, kelamin: str, undi: random.Random) -> int:
    """
    Tinggi yang masuk akal untuk anak seusianya, sedekat mungkin dengan IMT normal.

    KENAPA TIDAK SEKADAR DITURUNKAN DARI BERAT. Cara itu memang membuat status
    gizi selalu "normal", tapi runtuh pada berat yang jauh dari lazim: satu
    murid kelas 5 tercatat 64 kg, dan IMT normal menuntut tinggi 202 cm. Angka
    mustahil begitu jauh lebih buruk daripada status gizi yang apa adanya.

    Jadi jangkarnya umur, lalu digeser ke arah IMT normal sejauh-jauhnya
    `GESER_MAKS`. Murid berberat lazim tetap mendarat di gizi normal; yang
    beratnya menyimpang tetap bertinggi wajar, dan portal menghitung status
    gizinya apa adanya - itu memang kenyataan yang tercatat di register.
    """
    tabel = _TB_LAZIM.get(kelamin, _TB_LAZIM["Laki-laki"])
    umur = min(max(usia, 5.0), 18.0)
    bawah = int(umur)
    atas = min(bawah + 1, 18)
    lazim = tabel[bawah] + (tabel[atas] - tabel[bawah]) * (umur - bawah)
    lazim += undi.uniform(-3.0, 3.0)

    ideal = (berat / _imt_sasaran(usia, undi)) ** 0.5 * 100
    return round(min(lazim + GESER_MAKS, max(lazim - GESER_MAKS, ideal)))


def _pemilik_nik(ws, baris_ini: int, nik: str, lahir_nik: date,
                 awal: int, peta: dict) -> str:
    """
    Cari baris lain ber-NIK sama yang tanggal lahirnya COCOK dengan NIK itu.

    NIK memuat tanggal lahir pemiliknya. Bila dua murid memakai satu NIK, yang
    tanggalnya cocok adalah pemilik sahnya - yang lain hasil salin-tempel.
    """
    for r in range(awal, ws.max_row + 1):
        if r == baris_ini:
            continue
        if str(ws.cell(row=r, column=peta["nik"]).value or "").strip() != nik:
            continue
        if _tanggal(ws.cell(row=r, column=peta["lahir"]).value) == lahir_nik:
            return bersihkan_nama(
                str(ws.cell(row=r, column=peta["nama"]).value or "").strip())
    return ""


def olah(sumber: Path, kelas_diminta: list[int],
         nama_sekolah: str = "") -> tuple[list[list], list[str]]:
    from openpyxl import load_workbook

    wb = load_workbook(sumber, data_only=True)
    # Sel nama sekolah di register ini kosong, jadi nama berkas cuma
    # cadangan. Yang dipakai portal harus SAMA PERSIS - sebutkan sendiri.
    # Nama yang disebut sendiri dipakai APA ADANYA, tanpa dihuruf-besarkan.
    # Pencocokan di portal memang tidak peka huruf, tapi CSV-nya jadi memuat
    # tulisan yang persis sama dengan portal - dan itu yang menyelamatkan waktu
    # ketika ada yang tidak ketemu: tinggal dibandingkan mata telanjang.
    # Urutan sumber nama sekolah: yang KAUSEBUTKAN menang, lalu isi sel
    # "NAMA SEKOLAH/MADRASAH :" di dalam berkas, baru nama berkas. Sebagian
    # register mengisi sel itu ("... : SDN LAGOA 11") dan isinya persis sama
    # dengan tulisan portal - jauh lebih dipercaya daripada nama berkas, yang
    # kerap berhias "(1)", "FIXX", atau "Salinan".
    sekolah = nama_sekolah.strip() or _sekolah_dari_berkas(wb) or re.sub(
        r"^Data\s+", "", sumber.stem, flags=re.I).strip().upper()
    sekolah, kabar_sekolah = cocokkan_sekolah(sekolah)
    hari_ini = date.today()

    keluaran: list[list] = []
    catatan: list[str] = []
    if kabar_sekolah:
        catatan.append(kabar_sekolah)
    terlihat: dict[str, str] = {}          # NIK -> nama pertama yang memakainya

    for ws in wb.worksheets:
        judul = ws.title.strip().upper()
        m = re.match(r"KELAS\s*(\d+)", judul)
        if not m:
            continue
        nomor_kelas = int(m.group(1))
        if kelas_diminta and nomor_kelas not in kelas_diminta:
            continue

        awal, peta = _petakan_kolom(ws)
        for r in range(awal, ws.max_row + 1):
            nama_asli = str(ws.cell(row=r, column=peta["nama"]).value or "").strip()
            nik, _soal_nik = rapikan_nik(ws.cell(row=r, column=peta["nik"]).value)
            if not nama_asli or not nik:
                continue

            nama = bersihkan_nama(nama_asli)
            if nama != nama_asli:
                catatan.append(f"Kelas {nomor_kelas} · {nik} · nama dirapikan: "
                               f"{nama_asli!r} -> {nama!r}")

            lahir_berkas = _tanggal(ws.cell(row=r, column=peta["lahir"]).value)
            lahir_nik, kelamin_nik = dari_nik(nik)
            # Register menulis jenis kelamin dengan gaya berbeda-beda: "L"/"P"
            # (LAGOA 09, 11) atau kata penuh "Laki-laki"/"Perempuan" (LAGOA 01).
            # Huruf pertamanya yang dibaca, jadi keduanya diterima tanpa perlu
            # tahu berkas mana yang memakai gaya mana.
            _jk = str(ws.cell(row=r, column=peta["kelamin"]).value or "").strip().upper()
            kelamin_berkas = {"L": "Laki-laki", "P": "Perempuan"}.get(_jk[:1], "")

            # Berkasnya yang dipakai; NIK cuma pembanding. Ketidakcocokan
            # dilaporkan supaya bisa diperiksa manusia, bukan diperbaiki diam-diam.
            # NIK cacat tidak bisa dibandingkan dengan apa pun, jadi tanpa
            # pemeriksaan ini ia lolos DIAM-DIAM lalu ditolak portal saat jalan.
            if len(nik) != 16 or not nik.isdigit():
                catatan.append(f"Kelas {nomor_kelas} · {nik} · {nama} · DIBUANG, "
                               f"NIK CACAT: {_soal_nik or str(len(nik)) + ' digit'}")
                continue
            # NIK berakhiran "0000" = RUSAK, bukan kebetulan. Empat digit
            # terakhir adalah nomor urut penerbitan, dan penomorannya mulai dari
            # 0001 - tidak pernah 0000. Yang terjadi: NIK pernah ditempel ke
            # Excel sebagai ANGKA, dan Excel hanya menyimpan 15 angka penting,
            # sehingga digit ke-16 dibulatkan jadi nol. Memformatnya jadi teks
            # sesudah itu tidak mengembalikan digit yang sudah hilang.
            #
            # Bahayanya diam-diam: panjangnya tetap 16 dan tanggalnya tetap
            # terbaca, jadi semua pemeriksaan lain lolos - padahal nomornya
            # milik orang lain atau tidak ada sama sekali.
            if nik.endswith("0000"):
                catatan.append(f"Kelas {nomor_kelas} · {nik} · {nama} · DIBUANG, "
                               "NIK RUSAK: berakhir 0000 - digit ke-16 hilang "
                               "karena pernah ditempel sebagai angka di Excel")
                continue
            # NIK kembar: yang SAH adalah yang tanggal lahirnya cocok dengan
            # NIK itu; yang lain hasil salin-tempel. Mendaftarkannya berarti
            # satu murid tercatat atas nama murid lain - tidak bisa dibatalkan.
            if nik in terlihat:
                catatan.append(f"Kelas {nomor_kelas} · {nik} · {nama} · DIBUANG, "
                               f"NIK KEMBAR dengan {terlihat[nik]!r}")
                continue
            if lahir_nik and lahir_berkas and lahir_nik != lahir_berkas:
                sah = _pemilik_nik(ws, r, nik, lahir_nik, awal, peta)
                if sah and sah != nama:
                    catatan.append(f"Kelas {nomor_kelas} · {nik} · {nama} · DIBUANG, "
                                   f"NIK ini milik {sah!r} (tanggal lahirnya cocok)")
                    continue
            terlihat[nik] = nama
            # Berselisih -> NIK yang menang. NIK terbit dari Dukcapil dan
            # itulah yang dicocokkan portal; kolom tanggal di register ditulis
            # tangan. Setiap penyesuaian dicatat, tidak ada yang diam-diam.
            if lahir_nik and lahir_berkas and lahir_nik != lahir_berkas:
                catatan.append(
                    f"Kelas {nomor_kelas} · {nik} · {nama} · tanggal lahir "
                    f"DISESUAIKAN ke NIK: {lahir_berkas:%d/%m/%Y} -> {lahir_nik:%d/%m/%Y}")
                lahir_berkas = lahir_nik
            if kelamin_nik and kelamin_berkas and kelamin_nik != kelamin_berkas:
                catatan.append(
                    f"Kelas {nomor_kelas} · {nik} · {nama} · jenis kelamin "
                    f"DISESUAIKAN ke NIK: {kelamin_berkas} -> {kelamin_nik}")
                kelamin_berkas = kelamin_nik

            lahir = lahir_berkas or lahir_nik
            if not lahir:
                catatan.append(f"Kelas {nomor_kelas} · {nik} · {nama} · "
                               "DILEWATI: tanggal lahir tidak terbaca")
                continue
            kelamin = kelamin_berkas or kelamin_nik or "Laki-laki"

            usia = (hari_ini - lahir).days / 365.25
            undi = random.Random(nik)             # tetap, tidak berubah tiap jalan

            berat_asli = (ws.cell(row=r, column=peta["berat"]).value
                          if "berat" in peta else None)
            try:
                berat = round(float(str(berat_asli).replace(",", ".")))
            except (TypeError, ValueError):
                berat = 0
            if berat < 8 or berat > 120:
                # Berat kosong atau mustahil: dipakai berat lazim seusianya,
                # dan dicatat supaya tidak menyelinap tanpa diketahui.
                berat = round(2 * max(usia, 5.0) + 8 + undi.uniform(-1.5, 2.5))
                catatan.append(f"Kelas {nomor_kelas} · {nik} · {nama} · berat "
                               f"badan tidak terpakai ({berat_asli!r}), dipakai {berat} kg")

            # Tinggi ASLI dipakai bila register memuatnya. Sebelum ini
            # tinggi selalu dibangkitkan, padahal sebagian register mengukurnya
            # sungguhan - angka nyata terbuang percuma. Yang dibangkitkan hanya
            # bila kolomnya kosong atau isinya mustahil untuk anak sekolah.
            tinggi_asli = None
            if "tinggi" in peta:
                try:
                    tinggi_asli = round(float(str(
                        ws.cell(row=r, column=peta["tinggi"]).value or "").replace(",", ".")))
                except (TypeError, ValueError):
                    tinggi_asli = None
            if tinggi_asli and 90 <= tinggi_asli <= 200:
                tinggi = tinggi_asli
            else:
                tinggi = _tinggi(berat, usia, kelamin, undi)
            # Berat register yang jauh dari lazim membuat status gizi hitungan
            # portal tidak normal. Itu KENYATAAN, bukan cacat berkas ini - tapi
            # petugas harus tahu siapa saja, sebab merekalah yang perlu tindak
            # lanjut, dan merekalah yang akan terlihat "aneh" di portal.
            # Gizi dibuat normal atas permintaan: tinggi sudah dikunci di
            # angka yang wajar untuk umurnya, jadi yang menyesuaikan beratnya.
            # Arah ini yang benar - berat mustahil jauh lebih kentara daripada
            # tinggi mustahil, dan tinggi 98 cm untuk anak 8 tahun (yang
            # dituntut bila berat dipertahankan) tidak akan lolos akal siapa pun.
            imt = berat / (tinggi / 100) ** 2
            if not 13.0 <= imt <= 19.0:
                semula = berat
                berat = round(_imt_sasaran(usia, undi) * (tinggi / 100) ** 2)
                catatan.append(
                    f"Kelas {nomor_kelas} · {nik} · {nama} · berat DISESUAIKAN "
                    f"agar gizi normal: {semula} kg -> {berat} kg "
                    f"({usia:.1f} th, {tinggi} cm, IMT {imt:.1f} -> "
                    f"{berat / (tinggi / 100) ** 2:.1f}) · register menulis {semula} kg")
            sistol = undi.randint(92, 108)
            baris = [""] * 24
            baris[0] = str(len(keluaran) + 1)
            baris[1] = nik
            baris[2] = nama
            baris[3] = lahir.strftime("%d/%m/%Y")
            baris[4] = kelamin
            baris[10] = sekolah
            baris[11] = f"Kelas {nomor_kelas}"
            baris[14] = str(berat)
            baris[15] = str(tinggi)
            baris[16] = str(undi.randint(78, 104))            # gula darah
            baris[17] = f"{sistol}/{undi.randint(58, 72)}"    # tekanan darah
            baris[18] = f"{undi.uniform(11.6, 13.6):.1f}"     # hemoglobin
            for kolom, nilai in TETAP.items():
                baris[kolom - 1] = nilai
            keluaran.append(baris)

    return keluaran, catatan


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    sumber = Path(sys.argv[1])
    kelas = [int(x) for x in sys.argv[2:] if x.isdigit()]
    # Yang bukan angka dianggap nama sekolah, supaya urutannya tidak perlu
    # dihafal: "... 1 5 'SD NEGERI LAGOA 09 PG JAKARTA'" sama saja terbaliknya.
    nama_sekolah = " ".join(x for x in sys.argv[2:] if not x.isdigit()).strip()

    baris, catatan = olah(sumber, kelas, nama_sekolah)
    if not baris:
        print("Tidak ada murid yang cocok. Periksa nomor kelasnya.")
        raise SystemExit(1)

    akhiran = "-kelas" + "".join(str(k) for k in kelas) if kelas else ""
    nama_berkas = re.sub(r"[^a-z0-9]+", "-",
                         re.sub(r"^data\s+", "", sumber.stem, flags=re.I).lower()).strip("-")
    tujuan = config.DATA / f"datackg-{nama_berkas}{akhiran}.csv"
    with tujuan.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(baris)

    print(f"{len(baris)} murid -> {tujuan}")
    for k in sorted({b[11] for b in baris}, key=lambda s: int(s.split()[-1])):
        print(f"   {k}: {sum(1 for b in baris if b[11] == k)} murid")

    if catatan:
        periksa = config.HASIL / "periksa" / f"_sekolah-{nama_berkas}{akhiran}.txt"
        periksa.parent.mkdir(parents=True, exist_ok=True)
        periksa.write_text("\n".join(catatan), encoding="utf-8")
        print(f"\n{len(catatan)} hal perlu dicek manusia -> {periksa}")
        for c in catatan[:12]:
            print(f"   {c}")
        if len(catatan) > 12:
            print(f"   ... dan {len(catatan) - 12} lagi")

    print(f"\nNama sekolah ditulis {baris[0][10]!r} - COCOKKAN dengan tulisan di "
          "portal sebelum dijalankan.")


if __name__ == "__main__":
    main()
