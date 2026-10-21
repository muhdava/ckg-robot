"""
Alur "Sapu Belum Pemeriksaan": alur pelayanan normal TANPA berkas data.

Pesertanya diambil dari halaman Pelayanan CKG Umum, tab "Belum Pemeriksaan"
(rentang tanggal bawaan portal), dari atas. Jawaban form TIDAK dari berkas,
melainkan dipilih petugas di aplikasi - satu set untuk semua peserta jalan itu
(keputusan pemilik, 21 Okt 2026):

  * angka ukur (BB/TB/lingkar perut, tensi, gula) memakai PARAMETER seperti
    template DEWASA-LANSIA (parameter): Normal/Kurus/Gemuk, Normal/Tinggi/
    Rendah. Angkanya diturunkan peserta.py dalam rentang yang sama dengan
    template parameter, berbenih NIK (jalan ulang = angka sama);
  * temuan (merokok, gejala & kontak TBC, rontgen, mata, telinga, gigi)
    lewat kunci `rinci` yang sudah dipakai berkas skrining TBC
    (form.aturan_rinci); geriatri lewat parameter Geriatri.

Per peserta:
  1. baris di tab Belum Pemeriksaan (tabelnya TIDAK memuat NIK/JK - hanya
     nama, tanggal lahir, nomor tiket); umur < 18 dilewati;
  2. tombol "Mulai" di BARIS ITU - hanya membuka halaman detail, belum
     memulai apa pun. Dari kepala halaman dibaca NIK, jenis kelamin, dan
     nomor tiket (harus sama dengan baris);
  3. peserta dibentuk dari identitas itu + parameter pilihan petugas, lalu
     dikerjakan dengan alur "Pelayanan -> Selesai" yang SAMA dengan alur
     berkas (pekerjaan._coba_peserta): cari NIK, Mulai Pemeriksaan, sapu
     semua form, Selesaikan Layanan dengan bukti "Selesai Pemeriksaan",
     percobaan ulang, handler 429/portal sibuk.
"""
from __future__ import annotations

import re
from datetime import date, datetime

import config
import layanan
import pekerjaan
import portal
from browser import simpan_gambar
from peserta import Peserta, bersihkan_nama

# ---------------------------------------------------------------- pilihan
# Nilai kiri = yang dipakai robot (parameter peserta.py / kunci rinci);
# kanan = tulisan di aplikasi. Bawaan = paling atas (semua normal).
PILIHAN = {
    "gizi":     ("Gizi (BB, TB, lingkar perut)", [("Normal", "Normal"), ("Kurus", "Kurus"), ("Gemuk", "Gemuk")]),
    "tensi":    ("Tekanan darah", [("Normal", "Normal (110-139 / 65-89)"), ("Tinggi", "Tinggi (145-180 / 95-110)"),
                                   ("Rendah", "Rendah (85-99 / 50-60)")]),
    "gula":     ("Gula darah sewaktu", [("Normal", "Normal (110-139)"), ("Tinggi", "Tinggi (180-260)"),
                                        ("Rendah", "Rendah (55-69)")]),
    "rokok":    ("Merokok", [("tidak", "Tidak merokok"), ("ya", "Ya - rokok konvensional, terpapar asap")]),
    "batuk":    ("Batuk", [("tidak", "Tidak batuk"), ("kurang", "Ya, kurang dari 2 minggu"),
                           ("lebih", "Ya, lebih dari 2 minggu")]),
    "kontak":   ("Kontak TBC", [("tidak", "Tidak ada kontak"), ("serumah", "Kontak serumah"),
                                ("erat", "Kontak erat")]),
    "rontgen":  ("Radiografi toraks", [("tidak_dilakukan", "Tidak dilakukan"), ("normal", "Dilakukan - Normal")]),
    "mata":     ("Tajam penglihatan", [("normal", "Normal"), ("curiga", "Curiga gangguan penglihatan")]),
    "serumen":  ("Telinga (serumen impaksi)", [("tidak", "Tidak ada serumen"), ("ada", "Ada serumen")]),
    "karies":   ("Gigi karies", [("tidak", "Tidak"), ("ya", "Ya")]),
    "gigi_hilang": ("Gigi hilang/dicabut", [("tidak", "Tidak"), ("ya", "Ya")]),
    "geriatri": ("Geriatri (lansia >= 60)", [("Normal", "Normal"), ("Tidak Normal", "Tidak Normal")]),
}
BAGIAN = list(PILIHAN)
UMUR_MINIMAL = 18


def pilihan_untuk_aplikasi() -> dict:
    return {"bagian": [{"kunci": k, "judul": j, "pilihan": [{"nilai": v, "teks": t} for v, t in p]}
                       for k, (j, p) in PILIHAN.items()],
            "bawaan": {k: p[0][0] for k, (_, p) in PILIHAN.items()},
            "maks": config.SAPU_MAKS}


def urai_jawaban(masuk: dict | None) -> tuple[dict, str]:
    """Hanya nilai yang ada di PILIHAN yang diterima."""
    hasil = {}
    for k, (judul, p) in PILIHAN.items():
        nilai = str((masuk or {}).get(k) or p[0][0])
        if nilai not in {v for v, _ in p}:
            return {}, f"Jawaban {judul} tidak dikenal: {nilai!r}"
        hasil[k] = nilai
    return hasil, ""


def ringkas_jawaban(j: dict) -> str:
    return ", ".join(f"{PILIHAN[k][0]}: {dict(PILIHAN[k][1])[j[k]]}" for k in BAGIAN)


def rinci(j: dict) -> str:
    """Pilihan petugas -> "kunci=nilai;..." (form.aturan_rinci), dengan keputusan
    yang sama seperti berkas skrining TBC (ambil_data_skrining_tb)."""
    d = {"batuk": j["batuk"], "bb_turun": "tidak", "demam": "tidak", "keringat": "tidak",
         "kelenjar": "tidak", "rontgen": j["rontgen"], "kontak": j["kontak"]}
    if j["kontak"] != "tidak":
        d["indeks"] = "bakteriologis"
    d.update({"dahak": "tidak_dilakukan", "mata": j["mata"], "serumen": j["serumen"],
              "karies": j["karies"], "gigi_hilang": j["gigi_hilang"],
              "rokok": j["rokok"], "asap": j["rokok"], "dm": "tidak"})
    return ";".join(f"{k}={v}" for k, v in d.items())


# ---------------------------------------------------------------- halaman
BULAN = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "mei": 5, "jun": 6, "jul": 7, "agu": 8, "agt": 8,
         "ags": 8, "sep": 9, "okt": 10, "nov": 11, "des": 12}


def tanggal_id(teks: str) -> date | None:
    """'12 Mei 1966' -> date."""
    m = re.match(r"\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", teks or "")
    if not m:
        return None
    bln = BULAN.get(m.group(2)[:3].lower())
    try:
        return date(int(m.group(3)), bln, int(m.group(1))) if bln else None
    except ValueError:
        return None


def umur(lahir: date | None) -> int | None:
    if not lahir:
        return None
    k = date.today()
    return k.year - lahir.year - ((k.month, k.day) < (lahir.month, lahir.day))


# Baris tabel pelayanan: No, Nama, Tanggal Lahir, Nomor Tiket, Nama Wali, Unit,
# Pemeriksaan Mandiri, Pelayanan/Status, ..., tombol Mulai/Lihat. Dicari dari
# POLA isinya (tiket XXX-XXX, tanggal "12 Mei 1966"), bukan nomor kolom.
_JS_BARIS = r"""() => [...document.querySelectorAll('table tbody tr')].map((tr, i) => {
  const td = [...tr.children].map(x => (x.innerText || '').replace(/\s+/g, ' ').trim());
  const tiket = td.find(s => /^[A-Z0-9]{3}-[A-Z0-9]{3}$/.test(s)) || '';
  const lahir = td.find(s => /^\d{1,2} [A-Za-z]{3,9} \d{4}$/.test(s)) || '';
  const iTiket = td.indexOf(tiket), iLahir = td.indexOf(lahir);
  const nama = iLahir > 0 ? td[iLahir - 1] : (td[1] || '');
  const tombol = [...tr.querySelectorAll('button, a')].map(b => (b.innerText || '').trim()).filter(Boolean);
  return {i, nama, lahir, tiket, status: td.join(' '), tombol};
}).filter(b => b.tiket)"""

_JS_TOTAL_BELUM = r"""() => {
  const t = [...document.querySelectorAll('div,span,button,li,a')]
     .map(e => (e.innerText || '').replace(/\s+/g, ' ').trim())
     .find(s => /^Belum Pemeriksaan\s*\d+$/.test(s));
  return t ? parseInt(t.replace(/\D/g, ''), 10) : -1;
}"""

_JS_IDENTITAS = r"""() => {
  const t = (document.body.innerText || '').replace(/\s+/g, ' ');
  const ambil = re => { const m = t.match(re); return m ? m[1].trim() : ''; };
  return {nik: ambil(/NIK\s+(\d{16})\b/),
          lahir: ambil(/Tanggal Lahir\s+(\d{1,2} [A-Za-z]+ \d{4})/),
          jk: ambil(/Jenis Kelamin\s+(Laki-laki|Perempuan)/i),
          tiket: ambil(/Nomor Tiket\s+([A-Z0-9]{3}-[A-Z0-9]{3})/),
          detail: /detail-pemeriksaan/.test(location.pathname)};
}"""

# Tombol halaman berikutnya di bawah tabel: ikon panah/"›"/"Berikutnya".
_JS_TANDAI_BERIKUT = r"""() => {
  const kandidat = [...document.querySelectorAll('button, a, li, [role=button]')].filter(e => {
    if (e.offsetParent === null) return false;
    const t = (e.innerText || '').trim(), a = (e.getAttribute('aria-label') || '').toLowerCase();
    return /^(›|>|»|Berikutnya|Selanjutnya|Next)$/i.test(t) || /next|berikut|selanjutnya/.test(a);
  });
  const hidup = kandidat.find(e => !e.disabled && e.getAttribute('aria-disabled') !== 'true'
                                   && !/disabled|cursor-not-allowed/.test(e.className || ''));
  if (!hidup) return false;
  hidup.setAttribute('data-ckg-berikut', '1');
  return true;
}"""


def buka_daftar(halaman, catat) -> None:
    halaman.goto(config.HAL_PELAYANAN, wait_until="domcontentloaded")
    if not portal.tunggu_siap(halaman, portal.js_dan(portal.JS_TIDAK_MEMUAT,
                                                     portal.js_ada_teks("Belum Pemeriksaan")),
                              config.TUNGGU_MUNCUL_MS, "halaman pelayanan"):
        pesan = portal.tutup_popup_galat(halaman)
        raise RuntimeError("halaman pelayanan tidak termuat" + (f" ({pesan})" if pesan else ""))
    # Tab Belum Pemeriksaan biasanya sudah terbuka; label berangka -> klik_tab.
    portal.klik_tab(halaman, "Belum Pemeriksaan")
    portal.tunggu_siap(halaman, portal.JS_TIDAK_MEMUAT, 8_000, "tab belum pemeriksaan")


def _halaman_berikut(halaman) -> bool:
    try:
        if not halaman.evaluate(_JS_TANDAI_BERIKUT):
            return False
        sebelum = portal.tanda_tabel(halaman)
        halaman.locator("[data-ckg-berikut='1']").first.click(timeout=4_000)
        portal.tunggu_beda(halaman, sebelum, 8_000, "halaman daftar berikutnya")
        portal.tunggu_siap(halaman, portal.JS_TIDAK_MEMUAT, 8_000, "daftar berikutnya termuat")
        return True
    except Exception:
        return False
    finally:
        try:
            halaman.evaluate("() => document.querySelectorAll('[data-ckg-berikut]')"
                             ".forEach(e => e.removeAttribute('data-ckg-berikut'))")
        except Exception:
            pass


def cari_calon(halaman, dicoba: set, catat, maks_halaman: int = 60) -> dict | None:
    """
    Baris pertama di tab Belum Pemeriksaan yang berumur >= 18 dan belum dicoba.
    Anak/balita (umur < 18) dilewati - alur ini untuk dewasa/lansia.
    """
    for nomor_hal in range(1, maks_halaman + 1):
        for b in halaman.evaluate(_JS_BARIS) or []:
            if b["tiket"] in dicoba:
                continue
            u = umur(tanggal_id(b["lahir"]))
            if u is None or u < UMUR_MINIMAL:
                dicoba.add(b["tiket"])          # anak / tanggal tak terbaca: tidak dikerjakan
                continue
            if "Belum Pemeriksaan" not in b["status"] or "Mulai" not in b["tombol"]:
                continue
            b["umur"] = u
            b["halaman"] = nomor_hal
            return b
        if not _halaman_berikut(halaman):
            return None
    return None


def buka_detail(halaman, calon: dict) -> dict:
    """Tekan "Mulai" di baris calon (membuka detail, BELUM memulai) dan baca identitas."""
    baris = halaman.locator("table tbody tr").filter(has_text=calon["tiket"])
    if not baris.count():
        return {}
    baris.first.get_by_role("button", name="Mulai", exact=True).first.click(timeout=6_000)
    portal.tunggu_siap(halaman, "() => /detail-pemeriksaan/.test(location.pathname) "
                                "&& /NIK\\s+\\d{16}/.test(document.body.innerText || '')",
                       20_000, "detail peserta")
    return halaman.evaluate(_JS_IDENTITAS) or {}


def bentuk_peserta(urutan: int, idt: dict, calon: dict, jawaban: dict) -> Peserta:
    lahir = tanggal_id(idt.get("lahir") or calon["lahir"])
    return Peserta(
        baris_csv=urutan, nik=idt["nik"], nama=bersihkan_nama(calon["nama"]),
        tgl_lahir_teks=lahir.strftime("%d/%m/%Y") if lahir else "",
        jenis_kelamin=idt.get("jk") or "", no_hp="", provinsi="", kota="", kecamatan="",
        kelurahan="", alamat="", status_nikah="", pekerjaan="",
        gula_darah=jawaban["gula"], tekanan_darah=jawaban["tensi"], berat_badan="", tinggi_badan="",
        parameter={"gizi": jawaban["gizi"], "geriatri": jawaban["geriatri"], "rinci": rinci(jawaban)})


# ---------------------------------------------------------------- batch
def kerjakan(halaman, kerja, catatan_hasil, jumlah: int, jawaban: dict) -> None:
    jumlah = max(1, min(int(jumlah), config.SAPU_MAKS))
    # Semua peserta dewasa/lansia lewat alur pelayanan biasa.
    config.TAHAP = "pelayanan"
    config.KATEGORI = "dewasa"
    kerja.total = jumlah
    kerja.lapor(f"Jawaban: {ringkas_jawaban(jawaban)}")
    catat = lambda s: kerja.lapor(f"    {s}")          # noqa: E731
    dicoba: set[str] = set()
    jejak: list = []
    jejak_layanan: list = []
    urutan, beruntun = 0, 0
    while urutan < jumlah and not kerja.minta_berhenti:
        if not kerja.akun:
            kerja.akun = portal.nama_akun(halaman)
        try:
            buka_daftar(halaman, catat)
            if urutan == 0:
                total = halaman.evaluate(_JS_TOTAL_BELUM)
                kerja.lapor(f"Belum Pemeriksaan: {total if total >= 0 else '?'} peserta "
                            "(semua umur, rentang tanggal bawaan portal)")
            calon = cari_calon(halaman, dicoba, catat)
        except Exception as e:
            r = {"keterangan": f"{type(e).__name__}: {e}"}
            if pekerjaan._galat_jaringan(r) and beruntun < 3:
                beruntun += 1
                pekerjaan._tunggu_jaringan(halaman, kerja)
                continue
            kerja.pesan = f"Daftar pelayanan tidak bisa dibuka: {' '.join(str(e).split())[:200]}"
            kerja.lapor(kerja.pesan)
            simpan_gambar(halaman, "error_daftar_pelayanan")
            break
        if calon is None:
            kerja.pesan = "Tidak ada lagi peserta dewasa/lansia di tab Belum Pemeriksaan."
            kerja.lapor(kerja.pesan)
            kerja.total = urutan
            break
        dicoba.add(calon["tiket"])
        urutan += 1
        kerja.lapor(f"[{urutan}/{kerja.total}] {calon['nama']} · {calon['umur']} th · tiket {calon['tiket']}")
        idt = {}
        try:
            idt = buka_detail(halaman, calon)
        except Exception as e:
            catat(f"detail gagal dibuka: {type(e).__name__}")
        if not idt.get("nik") or (idt.get("tiket") and idt["tiket"] != calon["tiket"]):
            r = {"baris": urutan, "nik": idt.get("nik", ""), "nama": calon["nama"], "status": "gagal_detail",
                 "keterangan": f"tiket {calon['tiket']} | identitas di halaman detail tak terbaca/tak cocok "
                               f"(tiket detail {idt.get('tiket') or '-'})", "tiket": calon["tiket"]}
            simpan_gambar(halaman, f"sapu_detail_{urutan}")
        elif config.MODE_UJI:
            # MODE UJI di alur normal hanya menahan PENDAFTARAN; di alur ini
            # tidak ada pendaftaran, jadi robot berhenti SEBELUM "Mulai
            # Pemeriksaan" dan hanya melaporkan apa yang akan diisi.
            orang = bentuk_peserta(urutan, idt, calon, jawaban)
            r = {"baris": urutan, "nik": orang.nik, "nama": orang.nama, "status": "uji", "tiket": calon["tiket"],
                 "tgl_lahir": orang.tgl_lahir_teks,
                 "keterangan": (f"MODE UJI - tidak dimulai | {orang.usia} th · {orang.jenis_kelamin} · "
                                f"BB {orang.bb:g} TB {orang.tb:g} LP {orang.lingkar_perut:g} · "
                                f"TD {orang.sistole}/{orang.diastole} · GDS {orang.gds:g} · "
                                f"geriatri {orang.parameter['geriatri']} · {orang.parameter['rinci']}")}
        else:
            orang = bentuk_peserta(urutan, idt, calon, jawaban)
            r = pekerjaan._coba_peserta(halaman, orang, kerja, jejak, jejak_layanan)
            r["tiket"] = r.get("tiket") or calon["tiket"]
            r["keterangan"] = (f"tiket {calon['tiket']} · {calon['umur']} th · {idt.get('jk') or '?'} | "
                               + r.get("keterangan", ""))
            r["tgl_lahir"] = orang.tgl_lahir_teks
        r["waktu"] = datetime.now().strftime("%H:%M:%S")
        kerja.hasil.append(dict(r))
        kerja.selesai = urutan
        catatan_hasil.tambah(r)
        kerja.lapor(f"    {r['status']} · {r['keterangan'][:200]}")
        beruntun = beruntun + 1 if r["status"] in pekerjaan.GAGAL_SEMENTARA else 0
        if config.BERHENTI_SETELAH_GAGAL and beruntun >= config.BERHENTI_SETELAH_GAGAL:
            kerja.pesan = (f"Dihentikan: {beruntun} peserta gagal berturut-turut. "
                           "Periksa catatannya, lalu jalankan lagi.")
            kerja.lapor(kerja.pesan)
            break
    layanan.simpan_jejak(jejak_layanan, "-sapu")
    if kerja.minta_berhenti:
        kerja.lapor("Dihentikan oleh pengguna.")
