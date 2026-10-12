"""
Pembacaan CSV peserta + penurunan nilai (usia, tekanan darah, no HP).

Peta kolom diambil dari macro V7 REAL DATA, bukan tebakan:
  1 No            8  Kota/Kabupaten   17 Gula Darah (GDS)   25-27 Param Tropis
  2 NIK           9  Kecamatan        18 Tekanan Darah      28-29 Param Tuberkulosis
  3 Nama          10 Kelurahan        19 Berat Badan        30 Param Kesehatan Jiwa
  4 Tgl Lahir     11 Alamat           20 Tinggi Badan       31 Param Geriatri
  5 Jenis Kelamin 12 Status Nikah     21 Param Gizi         32 Param PUMA
  6 No HP         13 Pekerjaan        22 Param Mata-Telinga 33 Param Kanker Payudara
  7 Provinsi      14-16 (tidak dipakai) 23-24 Param Gigi    34 Param IVA
"""
from __future__ import annotations

import csv
import hashlib
import io
import random
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import config


def _teks(baris: list[str], kolom: int) -> str:
    """Ambil kolom ke-N (mulai 1). Kembalikan string kosong bila tidak ada."""
    i = kolom - 1
    return baris[i].strip() if len(baris) > i else ""


# Nama bulan Indonesia (dan singkatannya) untuk bentuk "8 Juni 2020".
_BULAN = {b: i for i, b in enumerate(
    ["januari", "februari", "maret", "april", "mei", "juni", "juli", "agustus",
     "september", "oktober", "november", "desember"], 1)}
_BULAN.update({"jan": 1, "feb": 2, "peb": 2, "mar": 3, "apr": 4, "mei": 5,
               "jun": 6, "jul": 7, "agu": 8, "ags": 8, "agt": 8, "sep": 9,
               "sept": 9, "okt": 10, "nov": 11, "des": 12,
               # sebagian berkas memakai bulan bahasa Inggris
               "january": 1, "february": 2, "march": 3, "may": 5, "june": 6,
               "july": 7, "august": 8, "october": 10, "december": 12})

_POLA_PISAH = re.compile(r"^(\d{1,4})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{1,4})$")
_POLA_KATA = re.compile(r"^(\d{1,2})\s+([A-Za-z]+)\.?\s+(\d{2,4})$")
_POLA_ANGKA = re.compile(r"^\d{4,5}$")
_EPOCH_EXCEL = date(1899, 12, 30)
# Rentang nomor urut tanggal Excel yang masih masuk akal sebagai TANGGAL LAHIR:
# 10.000 = 1927, 60.000 = 2064. Di luar itu angkanya hampir pasti bukan tanggal.
#
# Dipakai bersama oleh pembaca ini dan konverter. Dulu keduanya punya rentang
# sendiri (konverter mulai dari 20.000 = 1954), jadi lansia kelahiran sebelum
# 1954 ditolak konverter padahal diterima pembacanya - dua jawaban berbeda
# untuk satu angka yang sama.
SERIAL_EXCEL = (10_000, 60_000)


def _tahun_penuh(y: int) -> int:
    """Tahun dua digit -> empat digit. 30 ke bawah = 20xx, sisanya 19xx."""
    if y >= 100:
        return y
    return 2000 + y if y <= 30 else 1900 + y


def _buat(tahun: int, bulan: int, hari: int) -> date | None:
    try:
        return date(_tahun_penuh(tahun), bulan, hari)
    except ValueError:
        return None


def identitas_dari_nik(nik: str) -> tuple[date | None, str]:
    """
    Tanggal lahir dan jenis kelamin yang TERTULIS DI DALAM NIK.

    Digit 7-12 NIK memuat tanggal lahir DDMMYY, dan pada perempuan angka
    HARInya ditambah 40 - itulah yang sekaligus menyatakan jenis kelamin.

    Berguna karena inilah yang dicocokkan portal ke Dukcapil: tanggal lahir di
    berkas yang bentrok dengan NIK-nya adalah sebab paling sering dari
    "Data peserta tidak valid".

    Kembalikan (None, "") bila NIK-nya bukan 16 digit.
    """
    nik = (nik or "").strip()
    if not re.fullmatch(r"\d{16}", nik):
        return None, ""
    hari, bulan, tahun = int(nik[6:8]), int(nik[8:10]), int(nik[10:12])
    kelamin = "Perempuan" if hari > 40 else "Laki-laki"
    if hari > 40:
        hari -= 40
    # ABAD DIPILIH DARI KEWAJARAN, BUKAN URUTAN.
    #
    # Dua digit tahun tidak menyebut abadnya. Memilih 20xx lebih dulu benar
    # untuk murid, tapi salah besar untuk dewasa: NIK ...950005 (kelahiran
    # 1995) terbaca 2095 - tanggal lahir di masa depan. Jadi 20xx hanya dipakai
    # bila hasilnya TIDAK melewati hari ini; kalau melewati, pasti 19xx.
    kini = date.today()
    for abad in (2000, 1900):
        try:
            hasil = date(abad + tahun, bulan, hari)
        except ValueError:
            continue
        if hasil <= kini:
            return hasil, kelamin
    return None, kelamin


def tanggal_dari_teks(teks) -> date | None:
    """
    Ubah tanggal lahir jadi `date` - BENTUK APA PUN yang beredar di berkas.

    Yang diterima, semuanya terbukti ada di berkas nyata pengguna:

        16/05/2019   16-05-2019   16.05.2019   16/5/19
        2018-06-12   2018-06-12 00:00:00   2020-06-08T00:00:00
        8 Juni 2020  08 Jun 2020
        42947        (nomor urut tanggal Excel)

    KENAPA DI SINI, BUKAN DI TEMPLATE. Template CKG Sekolah sudah lama memberi
    kolom ini format DD/MM/YYYY, dan itu tetap tidak menolong: sel yang isinya
    TEKS - hasil tempel dari sistem lain - ditampilkan apa adanya oleh Excel,
    tidak diubah oleh format apa pun. Berkas SD ISLAM MAFAZA membuktikannya:
    323 dari 390 barisnya berisi teks "2018-06-12 00:00:00" di kolom yang sudah
    berformat DD/MM/YYYY. Jadi yang harus lentur pembacanya, bukan kolomnya.

    Bentuk A/B/C yang mendua (12/06 - Juni atau Desember?) dibaca HARI DULU,
    kebiasaan Indonesia, kecuali angka keduanya jelas-jelas di atas 12.
    """
    if isinstance(teks, datetime):
        return teks.date()
    if isinstance(teks, date):
        return teks
    t = ("" if teks is None else str(teks)).strip()
    if not t:
        return None

    # "Jakarta, 15 Maret 2019" - satu kolom yang sebenarnya memuat TEMPAT dan
    # tanggal lahir sekaligus, kebiasaan formulir Indonesia. Bagian depan
    # dibuang hanya bila tidak mengandung angka sama sekali, supaya tanggal
    # yang memang berkoma tidak ikut terpotong.
    if "," in t:
        depan, _, belakang = t.partition(",")
        if belakang.strip() and not any(c.isdigit() for c in depan):
            t = belakang.strip()
    # Tanda baca nyasar di ujung - kutip, petik miring, titik - membuat pola di
    # bawah meleset padahal tanggalnya utuh ("20 Mei 2019`").
    t = t.strip("'\"`´ .,;:")
    if not t:
        return None

    m = _POLA_PISAH.match(t)
    if m:
        a, b, c = (int(g) for g in m.groups())
        if a > 31:                       # 2018-06-12 -> tahun di depan
            return _buat(a, b, c)
        if b > 12:                       # bulan mustahil -> bulan/hari/tahun
            return _buat(c, a, b)
        return _buat(c, b, a)            # kebiasaan Indonesia: hari dulu

    m = _POLA_KATA.match(t)
    if m:
        hari, kata, tahun = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        bulan = _BULAN.get(kata) or _BULAN.get(kata[:4]) or _BULAN.get(kata[:3])
        return _buat(tahun, bulan, hari) if bulan else None

    # Kolom tanggal yang selnya TIDAK diformat tanggal terbaca sebagai NOMOR
    # URUT Excel - "42947", bukan "31/07/2017". Rentangnya dibatasi supaya
    # angka lain (mis. tinggi badan yang tersasar) tidak ikut dibaca tanggal.
    if _POLA_ANGKA.match(t):
        n = int(t)
        if SERIAL_EXCEL[0] <= n <= SERIAL_EXCEL[1]:
            return _EPOCH_EXCEL + timedelta(days=n)

    # "2020-06-08T00:00:00" dan sejenisnya - ambil bagian tanggalnya saja.
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        return _buat(*(int(g) for g in m.groups()))
    return None


@dataclass
class Peserta:
    baris_csv: int
    nik: str
    nama: str
    tgl_lahir_teks: str          # format asli dd/mm/yyyy
    jenis_kelamin: str
    no_hp: str
    provinsi: str
    kota: str
    kecamatan: str
    kelurahan: str
    alamat: str
    status_nikah: str
    pekerjaan: str
    gula_darah: str
    tekanan_darah: str           # mentah, mis. "110/80"
    berat_badan: str
    tinggi_badan: str
    parameter: dict[str, str] = field(default_factory=dict)

    # ---------------------------------------------------------- nilai turunan
    @property
    def tanggal_lahir(self) -> date | None:
        return tanggal_dari_teks(self.tgl_lahir_teks)

    @property
    def usia(self) -> int | None:
        lahir = self.tanggal_lahir
        if lahir is None:
            return None
        kini = date.today()
        return kini.year - lahir.year - ((kini.month, kini.day) < (lahir.month, lahir.day))

    @property
    def sistole(self) -> int:
        """Angka depan tekanan darah. Cadangan 120 bila tak terbaca."""
        return self._pecah_tekanan()[0]

    @property
    def diastole(self) -> int:
        """Angka belakang tekanan darah. Cadangan 80 bila tak terbaca."""
        return self._pecah_tekanan()[1]

    # -------------------------------------------------- angka dari parameter
    # CSV bertata letak PARAMETER tidak memuat angka, hanya kata
    # ("Normal"/"Rendah"/"Tinggi", "Kurus"/"Gemuk"). Rentang angkanya disalin
    # dari blok Data Hipertensi / Data Diabetes / BB & TB macro V4.5.
    # Diacak per peserta memakai NIK sebagai benih, supaya menjalankan ulang
    # peserta yang sama tidak menghasilkan berat badan atau tekanan yang
    # berbeda-beda.
    def _acak(self) -> random.Random:
        return random.Random(self.nik or self.nama)

    def _kata(self, teks: str) -> str:
        return (teks or "").strip().lower()

    def _pecah_tekanan(self) -> tuple[int, int]:
        angka = re.findall(r"\d+", self.tekanan_darah or "")
        if len(angka) >= 2:
            return int(angka[0]), int(angka[1])
        if len(angka) == 1:
            return int(angka[0]), 80
        r = self._acak()
        v = self._kata(self.tekanan_darah)
        if "tinggi" in v:
            return r.randint(145, 180), r.randint(95, 110)
        if "rendah" in v:
            return r.randint(85, 99), r.randint(50, 60)
        return r.randint(110, 139), r.randint(65, 89)

    def _ukuran_gizi(self) -> tuple[int, int, int]:
        """Berat badan, tinggi badan, lingkar perut menurut parameter gizi."""
        r = self._acak()
        tb = r.randint(150, 165)
        v = self._kata(self.parameter.get("gizi", ""))
        if "kurus" in v:
            return r.randint(38, 48), tb, r.randint(60, 72)
        if "gemuk" in v or "obes" in v:
            return r.randint(70, 85), tb, r.randint(90, 105)
        return r.randint(50, 65), tb, r.randint(70, 85)

    @property
    def no_hp_bersih(self) -> str:
        """Hanya angka, tanpa awalan 62 atau 0. Pakai nomor cadangan bila kosong."""
        digit = re.sub(r"\D", "", self.no_hp or "")
        if digit.startswith("62"):
            digit = digit[2:]
        elif digit.startswith("0"):
            digit = digit[1:]
        return digit if len(digit) >= 7 else config.NOHP_CADANGAN

    def _angka(self, teks: str, cadangan: float) -> float:
        bersih = re.sub(r"[^0-9.,]", "", teks or "").replace(",", ".")
        try:
            return float(bersih)
        except ValueError:
            return cadangan

    @property
    def bb(self) -> float:
        return self._angka(self.berat_badan, self._ukuran_gizi()[0])

    @property
    def tb(self) -> float:
        return self._angka(self.tinggi_badan, self._ukuran_gizi()[1])

    @property
    def lingkar_perut(self) -> float:
        return self._ukuran_gizi()[2]

    @property
    def gds(self) -> float:
        angka = re.sub(r"[^0-9.,]", "", self.gula_darah or "")
        if angka:
            return self._angka(self.gula_darah, 110)
        r = self._acak()
        v = self._kata(self.gula_darah)
        if self.dari_balita:
            # BALITA PUNYA RENTANG SENDIRI. Angka dewasa 110-139 terbaca
            # TINGGI untuk anak seusia itu; "normal" pada balita harus di
            # bawah 90 - keputusan pengguna 2 Sep 2026.
            if "tinggi" in v:
                return r.randint(180, 260)
            if "rendah" in v:
                return r.randint(50, 65)
            return r.randint(72, 89)
        if "tinggi" in v:
            return r.randint(180, 260)
        if "rendah" in v:
            return r.randint(55, 69)
        return r.randint(110, 139)

    @property
    def dari_balita(self) -> bool:
        """Benar bila barisnya memakai tata letak balita (18 kolom)."""
        p = self.parameter
        return "berat_lahir" in p and "gizi" in p and "kelas" not in p

    @property
    def kunci(self) -> str:
        """
        Identitas peserta - NIK bila ada, penggantinya bila tidak.

        Bayi tanpa NIK tetap butuh identitas: `_pecahan` memakainya sebagai
        benih (tanpa itu SELURUH bayi mendapat angka yang sama persis), dan
        daftar "sudah selesai" memakainya untuk melewati peserta pada jalan
        ulang (tanpa itu semuanya bertabrakan di satu kunci kosong).

        Diawali "TANPA-NIK/" supaya tidak pernah tertukar dengan NIK sungguhan,
        baik oleh manusia yang membaca berkas hasil maupun oleh kode.
        """
        return self.nik or f"TANPA-NIK/{self.nama}"

    @property
    def tanpa_nik(self) -> bool:
        """
        Benar bila peserta ini didaftarkan lewat centang "Tidak punya NIK".

        Ditanyakan pada PARAMETERNYA, bukan pada NIK yang kosong: baris balita
        biasa yang kolom NIK-nya kebetulan kosong itu berkas cacat yang harus
        diperbaiki, bukan bayi tanpa NIK - dan mendaftarkannya lewat jalan
        tanpa-NIK justru menyembunyikan cacat itu.
        """
        return "nik_wali" in self.parameter

    @property
    def wali(self) -> dict:
        """
        Identitas yang dipakai mengisi bagian "Data Wali" di portal.

        Dua sumber, sengaja dibedakan:

        - Balita TANPA NIK: walinya nyata dan wajib, datanya ada di berkas.
        - Balita biasa: berkasnya memang tidak memuat data wali sama sekali,
          dan yang selama ini diterima portal adalah identitas pesertanya
          sendiri. Kebiasaan itu dipertahankan apa adanya di sini supaya
          penambahan jalur tanpa-NIK tidak diam-diam mengubah perilaku ratusan
          baris balita yang sudah berjalan.
        """
        if not self.tanpa_nik:
            return {"nik": self.nik, "nama": self.nama,
                    "tanggal": self.tanggal_lahir, "kelamin": self.jenis_kelamin}
        p = self.parameter
        # Nama wali dibersihkan sama seperti nama peserta. Aturan portal
        # berlaku untuk KEDUA kolom - "Nama hanya dapat menggunakan huruf dan
        # karakter berikut ' . -" - dan pelanggarnya mematikan tombol
        # "Selanjutnya" untuk seterusnya, bukan sesaat. Di berkas balita tanpa
        # NIK 9 Sep ada "SITI CONTOH (PENELITIAN KIA RSCM)": catatan
        # penelitian yang menempel di belakang nama KTP.
        return {"nik": (p.get("nik_wali") or "").strip(),
                "nama": bersihkan_nama((p.get("nama_wali") or "").strip()),
                "tanggal": tanggal_dari_teks(p.get("lahir_wali", "")),
                "kelamin": (p.get("kelamin_wali") or "").strip()}

    def _pecahan(self, geser: int = 0) -> float:
        """
        Angka 0..1 yang TETAP untuk orang ini.

        NAMANYA JANGAN `_acak`. Kelas ini sudah punya `_acak()` yang
        mengembalikan generator `random.Random` dan dipakai tekanan darah,
        gizi, serta gula darah. Menamai keduanya sama membuat yang belakangan
        menimpa yang pertama, dan seluruh peserta dewasa/lansia gagal dengan
        "'float' object has no attribute 'randint'".

        Dipakai untuk memilih nilai di dalam rentang. Benihnya NIK, jadi anak
        yang sama selalu mendapat angka yang sama - dijalankan ulang berapa kali
        pun, hasilnya tidak berubah, dan itu penting bila peserta harus diulang.
        """
        # Diambil dari SELURUH NIK lewat pengacakan, bukan dari beberapa digit
        # terakhirnya: digit terakhir NIK adalah nomor urut, sehingga anak-anak
        # dalam satu berkas akan menumpuk di ujung rentang yang sama.
        benih = f"{self.kunci}-{geser}".encode("utf-8")
        return int(hashlib.md5(benih).hexdigest()[:8], 16) / 0xFFFFFFFF

    @property
    def berat_lahir_gram(self) -> int:
        """Berat lahir dalam GRAM (form `rowfrm000010` memakai gram)."""
        kunci = (self.parameter.get("berat_lahir") or "normal").strip().lower()
        a, b = BERAT_LAHIR.get(next((k for k in BERAT_LAHIR if k in kunci), "normal"))
        return int(a + self._pecahan(0) * (b - a))

    @property
    def berat_kini_gram(self) -> int:
        """Berat saat ini dalam GRAM - kolom kedua form Berat Lahir."""
        kunci = (self.parameter.get("berat_kini") or "normal").strip().lower()
        a, b = BERAT_LAHIR.get(next((k for k in BERAT_LAHIR if k in kunci), "normal"))
        return int(a + self._pecahan(1) * (b - a))

    @property
    def usia_bulan(self) -> int | None:
        """Umur dalam bulan penuh. Yang menentukan ukuran bayi, bukan tahunnya."""
        lahir = self.tanggal_lahir
        if lahir is None:
            return None
        kini = date.today()
        bulan = (kini.year - lahir.year) * 12 + kini.month - lahir.month
        return max(0, bulan - (1 if kini.day < lahir.day else 0))

    def _ideal(self) -> tuple[float, int]:
        # Bayi di bawah setahun dibaca dari tabel PER BULAN. Sebelumnya umur 0
        # dipaksa jadi 1 (`max(1, ...)`), sehingga bayi baru lahir tercatat
        # 10 kg / 76 cm - ukuran anak setahun.
        # `self.usia or 1` TIDAK BOLEH dipakai di sini: umur 0 itu falsy, jadi
        # bayi nol tahun akan diperlakukan sebagai anak setahun - persis cacat
        # yang hendak diperbaiki. Ketiadaan umur diperiksa terpisah.
        umur_tahun = 1 if self.usia is None else self.usia
        if umur_tahun < 1:
            bulan = min(11, self.usia_bulan or 0)
            jk = "L" if (self.jenis_kelamin or "").lower().startswith("laki") else "P"
            berat, panjang = IDEAL_BAYI[bulan][jk]
            return berat, round(panjang)
        umur = min(6, umur_tahun)
        jk = "L" if (self.jenis_kelamin or "").lower().startswith("laki") else "P"
        return IDEAL_WHO[umur][jk]

    @property
    def bb_balita(self) -> float:
        """Berat badan (kg) - ideal WHO dikali faktor menurut parameter gizi."""
        kunci = (self.parameter.get("gizi") or "normal").strip().lower()
        lo, hi = PENGALI_GIZI.get(next((k for k in PENGALI_GIZI if k in kunci), "normal"))
        berat, _ = self._ideal()
        return round(berat * (lo + self._pecahan(2) * (hi - lo)), 1)

    @property
    def tb_balita(self) -> int:
        """Tinggi badan (cm) - langsung dari tabel WHO, tanpa dikali."""
        return self._ideal()[1]

    @property
    def dari_sekolah(self) -> bool:
        """
        Benar bila peserta berasal dari CSV CKG Sekolah.

        Kategori ditentukan oleh DATANYA, bukan oleh pengaturan terpisah:
        pengaturan yang bertentangan dengan berkasnya pernah membuat berkas
        sekolah dijalankan lewat alur individu, dan tidak ada yang memberi tahu.
        """
        return "sekolah" in self.parameter or "kelas" in self.parameter

    def __str__(self) -> str:
        return f"[baris {self.baris_csv}] {self.nama} ({self.nik}) — {self.usia} th, {self.jenis_kelamin}"


# Dua tata letak CSV yang dipakai macro � keduanya harus bisa dibaca.
#
# REAL DATA : punya kolom No HP (6) serta Berat/Tinggi Badan (19, 20).
# PARAMETER : tanpa No HP dan tanpa Berat/Tinggi Badan, tapi ada dua kolom
#             tambahan di 25-26 (kategori usia dan kode). Semua kolom sesudah
#             Kelurahan otomatis bergeser, jadi tata letaknya tidak bisa
#             dipakai bergantian � harus dikenali lebih dulu.
PETA_REAL = {
    "nik": 2, "nama": 3, "tgl_lahir_teks": 4, "jenis_kelamin": 5, "no_hp": 6,
    "provinsi": 7, "kota": 8, "kecamatan": 9, "kelurahan": 10, "alamat": 11,
    "status_nikah": 12, "pekerjaan": 13,
    "gula_darah": 17, "tekanan_darah": 18, "berat_badan": 19, "tinggi_badan": 20,
}
PARAM_REAL = {
    21: "gizi", 22: "mata_telinga", 23: "gigi_a", 24: "gigi_b",
    25: "tropis_a", 26: "tropis_b", 27: "tropis_c",
    28: "tb_a", 29: "tb_b", 30: "kesehatan_jiwa", 31: "geriatri",
    32: "puma", 33: "kanker_payudara", 34: "iva",
}

PETA_PARAM = {
    "nik": 2, "nama": 3, "tgl_lahir_teks": 4, "jenis_kelamin": 5, "no_hp": 0,
    "provinsi": 6, "kota": 7, "kecamatan": 8, "kelurahan": 9, "alamat": 10,
    "status_nikah": 11, "pekerjaan": 12,
    "gula_darah": 16, "tekanan_darah": 17, "berat_badan": 0, "tinggi_badan": 0,
}
PARAM_PARAM = {
    18: "gizi", 19: "mata_telinga", 20: "gigi_a", 21: "gigi_b",
    22: "tropis_a", 23: "tropis_b", 24: "tropis_c",
    27: "tb_a", 28: "tb_b", 29: "kesehatan_jiwa", 30: "geriatri",
    31: "puma", 32: "kanker_payudara", 33: "iva",
}

# CKG SEKOLAH: 24 kolom. Tidak punya kolom wilayah bertingkat (murid dicari
# lewat Sekolah + Kelas, bukan lewat alamat), tapi punya Nama Sekolah & Kelas
# serta angka nyata untuk berat, tinggi, dan hemoglobin.
PETA_SEKOLAH = {
    "nik": 2, "nama": 3, "tgl_lahir_teks": 4, "jenis_kelamin": 5,
    "provinsi": 0, "kota": 0, "kecamatan": 0, "kelurahan": 0, "alamat": 6,
    "status_nikah": 7, "pekerjaan": 8, "no_hp": 9,
    "gula_darah": 17, "tekanan_darah": 18, "berat_badan": 15, "tinggi_badan": 16,
}
PARAM_SEKOLAH = {
    10: "disabilitas", 11: "sekolah", 12: "kelas",
    13: "gejala_cemas", 14: "gejala_depresi",
    19: "hemoglobin", 20: "gigi", 21: "serumen",
    22: "visus", 23: "berkacamata", 24: "kebugaran",
}
# Tata letak sekolah LAMA: 25 kolom, visus dipecah kanan dan kiri. Berkas yang
# sudah terlanjur dibuat dengan tata letak itu masih beredar di folder data,
# dan menggesernya begitu saja membuat kolom Berkacamata terbaca sebagai
# Kebugaran - salah tanpa suara. Jadi keduanya tetap bisa dibaca, dipilih dari
# JUMLAH KOLOM, dan form.py menyatukan kanan+kiri jadi satu nilai.
PARAM_SEKOLAH_LAMA = {
    10: "disabilitas", 11: "sekolah", 12: "kelas",
    13: "gejala_cemas", 14: "gejala_depresi",
    19: "hemoglobin", 20: "gigi", 21: "serumen",
    22: "visus_kanan", 23: "visus_kiri", 24: "berkacamata", 25: "kebugaran",
}

# BALITA (0-6 th): 18 kolom. Tanpa Berat/Tinggi Badan - keduanya diturunkan
# dari tabel WHO menurut umur dan jenis kelamin, jadi mengisinya di CSV hanya
# akan diabaikan. Tanpa tekanan darah, hemoglobin, kacamata, kebugaran: form
# balita memang tidak punya pertanyaan itu.
PETA_BALITA = {
    "nik": 2, "nama": 3, "tgl_lahir_teks": 4, "jenis_kelamin": 5,
    "provinsi": 6, "kota": 7, "kecamatan": 8, "kelurahan": 9, "alamat": 10,
    "status_nikah": 11, "pekerjaan": 12, "no_hp": 13,
    "gula_darah": 0, "tekanan_darah": 0, "berat_badan": 0, "tinggi_badan": 0,
}
PARAM_BALITA = {
    14: "disabilitas", 15: "berat_lahir", 16: "berat_kini",
    17: "imunisasi", 18: "gizi",
}

# BALITA TANPA NIK ("bayi Nyonya"): 21 kolom. Bayi yang NIK-nya belum terbit
# didaftarkan lewat centang "Tidak punya NIK", dan portal MEWAJIBKAN data wali
# yang lengkap - NIK, nama, tanggal lahir, jenis kelamin - sebab identitas
# pesertanya sendiri tidak ada. Karena itu kolom NIK peserta DIBUANG dan
# diganti empat kolom wali.
#
# Nomor HP yang ada hanyalah NOMOR WALI, dan itu diketikkan ke kolom "No.
# Whatsapp Aktif" peserta di halaman 1; nomor wali cukup dicentang "Nomor sama
# dengan peserta". Jadi satu kolom untuk keduanya.
PETA_BALITA_TANPA_NIK = {
    "nik": 0, "nama": 2, "tgl_lahir_teks": 3, "jenis_kelamin": 4,
    "provinsi": 9, "kota": 10, "kecamatan": 11, "kelurahan": 12, "alamat": 13,
    "status_nikah": 14, "pekerjaan": 15, "no_hp": 16,
    "gula_darah": 0, "tekanan_darah": 0, "berat_badan": 0, "tinggi_badan": 0,
}
PARAM_BALITA_TANPA_NIK = {
    5: "nik_wali", 6: "nama_wali", 7: "lahir_wali", 8: "kelamin_wali",
    17: "disabilitas", 18: "berat_lahir", 19: "berat_kini",
    20: "imunisasi", 21: "gizi",
}

# Tabel berat & tinggi ideal WHO (kg, cm) menurut umur penuh tahun dan jenis
# kelamin. Umur 6 memakai angka umur 5 - keputusan pengguna 2026-08-03, sebab
# form untuk 5 dan 6 tahun sama.
# Median WHO untuk TAHUN PERTAMA, per bulan: (berat kg, panjang cm).
# Wajib ada tabel tersendiri karena tabel per tahun tidak berguna di sini -
# bayi 0 bulan 3,3 kg dan bayi 12 bulan 9,6 kg sama-sama "0 tahun". Memakai
# angka setahun untuk bayi baru lahir menghasilkan data yang mustahil.
IDEAL_BAYI = {
    0:  {"L": (3.3, 49.9), "P": (3.2, 49.1)},
    1:  {"L": (4.5, 54.7), "P": (4.2, 53.7)},
    2:  {"L": (5.6, 58.4), "P": (5.1, 57.1)},
    3:  {"L": (6.4, 61.4), "P": (5.8, 59.8)},
    4:  {"L": (7.0, 63.9), "P": (6.4, 62.1)},
    5:  {"L": (7.5, 65.9), "P": (6.9, 64.0)},
    6:  {"L": (7.9, 67.6), "P": (7.3, 65.7)},
    7:  {"L": (8.3, 69.2), "P": (7.6, 67.3)},
    8:  {"L": (8.6, 70.6), "P": (7.9, 68.7)},
    9:  {"L": (8.9, 72.0), "P": (8.2, 70.1)},
    10: {"L": (9.2, 73.3), "P": (8.5, 71.5)},
    11: {"L": (9.4, 74.5), "P": (8.7, 72.8)},
}

IDEAL_WHO = {
    1: {"L": (9.6, 76),  "P": (9.6, 76)},
    2: {"L": (12.2, 88), "P": (11.5, 87)},
    3: {"L": (14.3, 96), "P": (13.9, 95)},
    4: {"L": (16.3, 103), "P": (16.0, 103)},
    5: {"L": (18.3, 110), "P": (18.2, 109)},
    # Umur 6 SENGAJA memakai angka umur 5 - keputusan pengguna 2026-08-03,
    # tercatat di "KATALOG FORM BALITA.md": anak 6 tahun ternyata masih memakai
    # form pertumbuhan rowfrm000119, yang tabelnya sama dengan umur 5.
    # JANGAN "diperbaiki" jadi angka umur 6; itu membatalkan keputusan tadi.
    6: {"L": (18.3, 110), "P": (18.2, 109)},
}
# Berat lahir (gram) menurut parameter Kurus/Normal/Gemuk.
BERAT_LAHIR = {"kurus": (2000, 2500), "normal": (2600, 3500), "gemuk": (3600, 4200)}
# Pengali berat badan saat ini terhadap berat ideal WHO.
PENGALI_GIZI = {"kurus": (0.80, 0.90), "normal": (0.95, 1.05), "gemuk": (1.15, 1.30)}

# Nama-nama provinsi tidak pernah berupa angka, sedangkan nomor HP selalu.
# Itulah pembeda paling jelas antara REAL DATA dan PARAMETER.
_ANGKA_SAJA = re.compile(r"^[\d\s+()-]+$")
# Kolom 12 CKG Sekolah selalu berisi tingkat kelas ("Kelas 1", "Kelas 11").
# Tanpa penanda ini, tata letak sekolah tertukar dengan PARAMETER: keduanya
# sama-sama punya kolom 6 berisi teks (alamat vs provinsi).
_KELAS = re.compile(r"^kelas\b", re.I)


def _geser_sekolah(baris: list[str]) -> int | None:
    """
    Berapa kolom tata letak sekolah ini bergeser, atau None kalau bukan sekolah.

    Kolom "Kelas N" DICARI, bukan dipatok di 12. Sebagian data sekolah masih
    membawa rantai wilayah Provinsi/Kota/Kecamatan/Kelurahan warisan template
    dewasa - empat kolom yang menggeser SELURUH kolom sesudah Jenis Kelamin.
    Dipatok di 12, berkas seperti itu tidak dikenali sebagai sekolah sama
    sekali; ia jatuh ke tata letak PARAMETER dan terbaca tanpa nama sekolah,
    tanpa kelas, tanpa berat dan tinggi - salah TANPA satu pun pesan galat.
    """
    for kolom in (12, 16):
        if _KELAS.match(_teks(baris, kolom)):
            return kolom - 12
    return None


def _peta_sekolah(baris: list[str], geser: int) -> tuple[dict, dict]:
    """Peta kolom sekolah, digeser bila berkasnya membawa kolom wilayah."""
    # Visus: satu kolom (24) atau masih terpecah kanan/kiri (25). Dihitung
    # setelah pergeseran dibuang, supaya lebarnya bisa dibandingkan langsung.
    param = (PARAM_SEKOLAH_LAMA if len(baris) - geser >= 25 else PARAM_SEKOLAH)
    if not geser:
        return PETA_SEKOLAH, param
    peta = {k: (v + geser if v else 0) for k, v in PETA_SEKOLAH.items()}
    # Kolom wilayah yang tadinya kosong kini benar-benar ada isinya.
    peta.update({"provinsi": 6, "kota": 7, "kecamatan": 8, "kelurahan": 9,
                 "alamat": 10})
    return peta, {k + geser: v for k, v in param.items()}


# Tanda tangan BALITA TANPA NIK: NIK 16 digit ada di kolom 6 (milik WALI),
# sedangkan kolom 2 berisi NAMA - bukan angka. Tidak ada tata letak lain yang
# begitu; semuanya menaruh NIK peserta di kolom 2. Dua syarat sekaligus dipakai
# supaya berkas lain yang NIK-nya kebetulan rusak tidak ikut tertangkap.
_ADA_HURUF = re.compile(r"[A-Za-z]")


def _tanpa_nik(baris: list[str]) -> bool:
    # NIK WALI ada di kolom 5 - keempat kolom wali berurutan di 5..8 (NIK,
    # Nama, Tanggal Lahir, Jenis Kelamin), mengikuti susunan template 4 Sep.
    return bool(re.fullmatch(r"\d{16}", _teks(baris, 5))
                and _ADA_HURUF.search(_teks(baris, 2))
                and _teks(baris, 3))


def _kenali_tata_letak(baris: list[str]) -> tuple[dict, dict]:
    # Balita dikenali dari JUMLAH KOLOM: 18, paling sedikit di antara semua
    # tata letak (sekolah 24, parameter 33, real data 34). Kolom 12 balita
    # berisi pekerjaan, jadi pemeriksaan "Kelas ..." di bawah tidak terganggu.
    if _tanpa_nik(baris):
        return PETA_BALITA_TANPA_NIK, PARAM_BALITA_TANPA_NIK
    if len(baris) <= 20 and _teks(baris, 2) and _teks(baris, 3):
        return PETA_BALITA, PARAM_BALITA
    geser = _geser_sekolah(baris)
    if geser is not None:
        return _peta_sekolah(baris, geser)
    isi6 = _teks(baris, 6)
    if isi6 and not _ANGKA_SAJA.match(isi6):
        return PETA_PARAM, PARAM_PARAM
    return PETA_REAL, PARAM_REAL


# Portal hanya menerima huruf, spasi, dan tiga tanda: apostrof, titik, hubung.
# Pesannya: "Nama hanya dapat menggunakan huruf dan karakter berikut ' . -".
# Nama yang melanggar membuat tombol "Selanjutnya" MATI SELAMANYA - bukan galat
# sesaat, jadi tidak ada gunanya diulang.
_NAMA_HARAM = re.compile(r"[^A-Za-z '.\-]")
# Yang melanggar di data nyata selalu berupa catatan yang MENEMPEL DI BELAKANG
# nama KTP: "(EM)", "(PROLANIS DM HT)", "*", ", SE", ",S.PD", "/ (BY 01-...)".
# Nama KTP-nya utuh di depan, jadi dipotong mulai tanda pertama - bukan sekadar
# membuang karakternya, yang akan menyisakan "SITI CONTOH SE".
_NAMA_EKOR = re.compile(r"\s*[(/*,].*$")


NAMA_DIBERSIHKAN: list[tuple[int, str, str]] = []


def bersihkan_nama(nama: str) -> str:
    """
    Buang catatan administrasi dari nama supaya portal mau menerimanya.

    Dikembalikan apa adanya bila pembersihan menyisakan kosong - lebih baik
    ditolak portal dengan jelas daripada mendaftarkan orang tanpa nama.
    """
    # Spasi tak-biasa (NBSP dari salinan web, tab) dijadikan spasi dulu - kalau
    # tidak, _NAMA_HARAM membuangnya dan "BUDI SANTOSO" menyatu jadi "BUDISANTOSO".
    nama = re.sub(r"\s", " ", nama)
    bersih = _NAMA_HARAM.sub("", _NAMA_EKOR.sub("", nama)).strip()
    bersih = " ".join(bersih.split())
    return bersih or nama


def baca_csv(path: Path | None = None) -> list[Peserta]:
    """Baca seluruh CSV peserta. Baris yang tidak punya NIK+Nama dilewati."""
    path = path or config.CSV_PESERTA
    isi = path.read_text(encoding="utf-8-sig", errors="replace")
    hasil: list[Peserta] = []
    peta = param = None
    for nomor, baris in enumerate(csv.reader(io.StringIO(isi)), start=1):
        if not _teks(baris, 2) or not _teks(baris, 3):
            continue          # baris ekor template / kosong
        if peta is None:
            peta, param = _kenali_tata_letak(baris)
        medan = {m: _teks(baris, k) if k else "" for m, k in peta.items()}
        asli = medan.get("nama", "")
        medan["nama"] = bersihkan_nama(asli)
        if medan["nama"] != asli:
            NAMA_DIBERSIHKAN.append((nomor, asli, medan["nama"]))
        hasil.append(
            Peserta(
                baris_csv=nomor,
                parameter={nama: _teks(baris, k) for k, nama in param.items()},
                **medan,
            )
        )
    return hasil


def ambil_batch(semua: list[Peserta], mulai: int, jumlah: int) -> list[Peserta]:
    """Potong daftar peserta sesuai nomor baris CSV (bukan indeks list)."""
    return [p for p in semua if mulai <= p.baris_csv < mulai + jumlah]


if __name__ == "__main__":
    orang = baca_csv()
    print(f"Terbaca {len(orang)} peserta dari {config.CSV_PESERTA.name}\n")
    for p in ambil_batch(orang, config.BARIS_AWAL, min(config.JUMLAH_DATA, 5)):
        print(" ", p)
        print(f"     TD {p.sistole}/{p.diastole} · GDS {p.gds} · BB {p.bb} · TB {p.tb} · HP {p.no_hp_bersih}")
