"""
Alur "Tatalaksana Gigi": mencatat tatalaksana gigi berlubang TANPA berkas data.

Pesertanya diambil langsung dari portal: menu Tatalaksana -> Daftar
Tatalaksana, filter Tahun program + Kelompok skrining "Gigi" + Hasil
pemeriksaan "Gigi berlubang", tab "Belum Pencatatan Tatalaksana".

Per peserta (dibuktikan di portal sungguhan, 20 Okt 2026):
  daftar -> "Lihat Detail" -> halaman detail (identitas + tabel Tatalaksana)
  -> baris "Gigi berlubang" status "Belum tatalaksana" -> "Mulai Tatalaksana"
  -> form SurveyJS di form.kemkes.go.id -> Kirim -> portal kembali sendiri ke
  halaman detail, status baris menjadi "Selesai tatalaksana", dan peserta
  keluar dari tab Belum Pencatatan (lencana berkurang satu).

Yang perlu diingat:
  * Tombol "Mulai Tatalaksana" TETAP ADA sesudah selesai. Status baris yang
    jadi hakim - tanpa membacanya, peserta yang sudah selesai dicatat dua kali.
  * Filter daftar TIDAK tersimpan; tiap kembali ke daftar dipilih ulang.
  * Karena yang selesai keluar dari daftar, robot selalu mengambil baris
    teratas yang belum dicoba - tidak perlu menelusuri ratusan halaman.
  * Jawaban form bukan tebakan: dipilih petugas (bawaan dari pemilik) dan
    dicocokkan dengan model SurveyJS sebelum Kirim. Bila ada yang tidak
    sama, form TIDAK dikirim.
"""
from __future__ import annotations

import re
from datetime import datetime

import config
import form
import pekerjaan
import portal
from browser import simpan_gambar

# Pilihan form tatalaksana gigi berlubang, dibaca dari model SurveyJS portal
# (20 Okt 2026). Nilai di kiri = nilai yang disimpan form; teks di kanan =
# tulisan pilihannya. Aplikasi menampilkan daftar ini; saat mengisi, robot
# mencocokkannya lagi dengan form yang sedang terbuka.
PILIHAN = {
    "diagnosis": {
        "judul": "Diagnosis",
        "ya": [
            ("K02", "K02 - Dental caries (Karies gigi)"),
            ("K02.0", "K02.0 - Caries limited to enamel (Karie terbatas pada enamel)"),
            ("K02.1", "K02.1 - Caries of dentine (Karies dentin)"),
            ("K02.2", "K02.2 - Caries of cementum (Karies semen)"),
            ("K02.3", "K02.3 - Arrested dental caries (Karies gigi yang berhenti berkembang)"),
            ("K02.4", "K02.4 - Odontoclasia (Odontoklasia)"),
            ("K02.5", "K02.5 - Caries with pulp exposure (Karies mencapai akar)"),
            ("K02.8", "K02.8 - Other dental caries (Karies gigi lainnya)"),
            ("K02.9", "K02.9 - Dental caries, unspecified (Karies gigi, tidak terspesifikasi)"),
        ],
        "tidak": [
            ("DX-PENDING", "Perlu pemeriksaan penunjang lainnya"),
            ("DX-UNSPEC", "Gejala masih belum spesifik"),
            ("DX-LIMFAC", "Keterbatasan fasilitas pemeriksaan"),
            ("DX-LIMTME", "Waktu pemeriksaan terbatas"),
            ("DX-REFREQ", "Perlu rujukan ke fasilitas yang lebih lengkap"),
            ("DX-OTHERS", "Lainnya"),
        ],
    },
    "tindakan": {
        "judul": "Tindakan medis",
        "ya": [
            ("23", "23 - Removal and restoration of teeth (Pencabutan dan restorasi gigi)"),
            ("23.2", "23.2 - Restoration of tooth by filling (Restorasi gigi dengan penambalan)"),
            ("23.4", "23.4 - Other dental restoration (Restorasi gigi lainnya)"),
            ("23.11", "23.11 - Removal of residual root (Pengangkatan sisa akar)"),
            ("23.71", "23.71 - Root canal therapy with irrigation (Perawatan saluran akar dengan irigasi)"),
        ],
        "tidak": [
            ("DEF-REFUSE", "Pasien menolak tindakan medis / tidak datang lagi"),
            ("DEF-FAC", "Keterbatasan fasilitas (alat & bahan)"),
            ("DEF-COND", "Pasien tidak memenuhi syarat untuk tindakan tertentu"),
            ("DEF-PEND", "Menunggu hasil pemeriksaan penunjang"),
            ("DEF-HR", "Tidak ada SDM terlatih"),
            ("DEF-RISK", "Risiko tindakan lebih besar daripada manfaat"),
            ("DEF-OTHERS", "Lainnya"),
        ],
    },
    # Terapi obat "Ya" butuh resep + dosis per obat - sengaja tidak disediakan.
    "obat": {
        "judul": "Terapi farmakologi (obat)",
        "ya": [],
        "tidak": [
            ("RX-NOIND", "Tidak ada indikasi medis"),
            ("RX-EMPTY", "Obat tidak tersedia"),
            ("RX-ALRC", "Riwayat alergi atau kontraindikasi obat"),
            ("RX-TOXIC", "Risiko efek samping lebih besar daripada manfaat"),
            ("RX-REFUSE", "Pasien menolak diberikan obat"),
            ("RX-NONCOV", "Tidak masuk dalam skema pembiayaan Puskesmas"),
            ("RX-OTHERS", "Lainnya"),
        ],
    },
    "edukasi": {
        "judul": "Edukasi",
        "ya": [("", "Sudah diberikan edukasi")],
        "tidak": [
            ("EDU-UNFIT", "Kondisi pasien tidak memungkinkan"),
            ("EDU-BARRIER", "Hambatan komunikasi"),
            ("EDU-TIME", "Keterbatasan waktu pelayanan"),
            ("EDU-NONCOOP", "Pasien tidak kooperatif atau tidak fokus"),
            ("EDU-OTHERS", "Lainnya"),
        ],
    },
    # "Kontrol rutin" butuh tanggal kunjungan ulang - hanya "Rujuk FKTL"
    # yang disediakan untuk jawaban Ya.
    "tindak_lanjut": {
        "judul": "Kontrol rutin / rujuk FKTL",
        "ya": [("rujuk_fktl", "Rujuk FKTL")],
        "tidak": [
            ("TL - LAIN", "Lainnya"),
            ("TL - TUNTAS", "Pengobatan tuntas"),
            ("TL - BIAYA", "Tidak masuk dalam skema pembiayaan Puskesmas"),
            ("TL - TOLAK", "Pasien menolak"),
        ],
    },
}
BAGIAN = list(PILIHAN)


def pilihan_untuk_aplikasi() -> dict:
    """Daftar pilihan + bawaan, untuk dropdown jawaban di aplikasi."""
    return {
        "bagian": [{
            "kunci": k,
            "judul": PILIHAN[k]["judul"],
            "pilihan": ([{"nilai": f"Y|{v}", "teks": f"Ya · {t}"} for v, t in PILIHAN[k]["ya"]]
                        + [{"nilai": f"N|{v}", "teks": f"Tidak · {t}"} for v, t in PILIHAN[k]["tidak"]]),
        } for k in BAGIAN],
        "bawaan": dict(config.TATALAKSANA_JAWABAN),
        "maks": config.TATALAKSANA_MAKS,
        "filter": dict(config.TATALAKSANA_FILTER),
    }


def urai_jawaban(masuk: dict | None) -> tuple[dict, str]:
    """
    Periksa jawaban dari aplikasi. Kembalikan (jawaban, galat).

    Hanya nilai yang ADA di PILIHAN yang diterima - salah ketik atau isian
    rekaan tidak boleh sampai ke form portal.
    """
    hasil = {}
    for k in BAGIAN:
        teks = str((masuk or {}).get(k) or config.TATALAKSANA_JAWABAN[k])
        jawab, _, nilai = teks.partition("|")
        daftar = PILIHAN[k]["ya" if jawab == "Y" else "tidak"] if jawab in ("Y", "N") else []
        if not any(v == nilai for v, _ in daftar):
            return {}, f"Jawaban {PILIHAN[k]['judul']} tidak dikenal: {teks!r}"
        hasil[k] = (jawab, nilai)
    return hasil, ""


def ringkas_jawaban(jawaban: dict) -> str:
    """Satu baris yang dicatat di log & keterangan hasil."""
    bagian = []
    for k in BAGIAN:
        jawab, nilai = jawaban[k]
        teks = next(t for v, t in PILIHAN[k]["ya" if jawab == "Y" else "tidak"] if v == nilai)
        pendek = teks.split(" (")[0] if jawab == "Y" else teks
        bagian.append(f"{k}={'Ya' if jawab == 'Y' else 'Tidak'}"
                      + (f" ({pendek})" if nilai else ""))
    return ", ".join(bagian)


# ================================================================ daftar
# Pemicu dropdown filter: div yang memuat <span class="line-clamp-2">. Sesudah
# dipilih, tulisan span-nya berganti menjadi nilainya.
_JS_PEMICU = r"""(teks) => {
  const s = [...document.querySelectorAll('span.line-clamp-2')]
              .find(e => e.textContent.trim() === teks);
  return !!s;
}"""

_JS_BARIS_DAFTAR = r"""() => {
  const t = document.querySelector('table');
  if (!t) return null;
  return [...t.querySelectorAll('tbody tr')].map((tr, i) => {
    const td = [...tr.children].map(x => (x.innerText || '').replace(/\s+/g, ' ').trim());
    return {i, nik: td[0] || '', nama: td[1] || '', lahir: td[2] || '',
            pelayanan: td[4] || '', hasil: td[5] || '',
            tombol: !!tr.querySelector('button')};
  }).filter(b => /^\d{16}$/.test(b.nik));
}"""

_JS_LENCANA = r"""() => {
  const tab = [...document.querySelectorAll('div.cursor-pointer')]
                .find(e => /^Belum Pencatatan Tatalaksana/.test(e.textContent.trim()));
  if (!tab) return -1;
  const m = tab.textContent.match(/(\d[\d.]*)\s*$/);
  return m ? parseInt(m[1].replace(/\./g, ''), 10) : 0;
}"""

_JS_DAFTAR_SIAP = r"""() => {
  const t = document.body.innerText || '';
  if (/Memuat|Sedang memuat|Proses pencarian/i.test(t)) return false;
  return !!document.querySelector('table tbody tr td')
      || /Tidak ada data|Data tidak ditemukan|belum ada data/i.test(t);
}"""


def _pilih_filter(halaman, placeholder: str, kotak_cari: str, nilai: str) -> bool:
    """Buka satu dropdown filter daftar lalu klik pilihan yang tulisannya persis."""
    # "Hasil pemeriksaan" masih kotak mati (tanpa span) sampai kelompok
    # skrining terpilih - ditunggu sampai menjadi pemicu sungguhan.
    portal.tunggu_kondisi(halaman, f"() => ({_JS_PEMICU})({portal._teks_js(placeholder)})", 6_000)
    pemicu = halaman.locator("span.line-clamp-2", has_text=re.compile(
        rf"^\s*{re.escape(placeholder)}\s*$"))
    if not pemicu.count():
        return False
    pemicu.first.click()
    kotak = halaman.locator(f'input[placeholder="{kotak_cari}"]')
    try:
        kotak.first.wait_for(state="visible", timeout=6_000)
    except Exception:
        return False
    opsi = kotak.first.locator("xpath=following-sibling::div[1]/div").filter(
        has_text=re.compile(rf"^\s*{re.escape(nilai)}\s*$"))
    if not opsi.count():
        return False
    opsi.first.click()
    # Dropdown berikutnya (Hasil pemeriksaan) baru hidup sesudah yang ini terisi.
    return portal.tunggu_kondisi(halaman, f"() => !({_JS_PEMICU})({portal._teks_js(placeholder)})",
                                 4_000)


def buka_daftar(halaman, kerja) -> tuple[list[dict], int]:
    """
    Buka daftar tatalaksana dengan filter terpasang.

    Mengembalikan (baris halaman pertama, jumlah di lencana Belum Pencatatan).
    Lencana -1 = tak terbaca.
    """
    f = config.TATALAKSANA_FILTER
    halaman.goto(config.HAL_TATALAKSANA, wait_until="domcontentloaded")
    portal.tunggu_siap(halaman, f"() => ({_JS_PEMICU})('Tahun program')", 15_000,
                       "filter tatalaksana")
    for ph, cari, nilai in (("Tahun program", "Cari tahun program", f["tahun"]),
                            ("Kelompok skrining", "Cari kelompok skrining", f["kelompok"]),
                            ("Hasil pemeriksaan", "Cari hasil pemeriksaan", f["hasil"])):
        if not _pilih_filter(halaman, ph, cari, nilai):
            raise RuntimeError(f"filter {ph} = {nilai!r} tidak bisa dipilih")
    tombol = halaman.get_by_text("Tampilkan pencarian", exact=True)
    tombol.first.click()
    if not portal.tunggu_siap(halaman, _JS_DAFTAR_SIAP, 30_000, "daftar tatalaksana"):
        raise RuntimeError("daftar tatalaksana tidak termuat")
    # Tab Belum Pencatatan sudah aktif sejak awal, tapi dipastikan: mencatat
    # dari tab Selesai berarti mencatat ulang.
    if not portal.klik_tab(halaman, "Belum Pencatatan Tatalaksana"):
        raise RuntimeError("tab Belum Pencatatan Tatalaksana tidak ketemu")
    portal.tunggu_siap(halaman, _JS_DAFTAR_SIAP, 10_000, "tab belum pencatatan")
    return halaman.evaluate(_JS_BARIS_DAFTAR) or [], halaman.evaluate(_JS_LENCANA)


# ================================================================ detail
_JS_DETAIL = r"""(hasil) => {
  const rapi = s => (s || '').replace(/\s+/g, ' ').trim();
  // NIK di kartu identitas: label "NIK" lalu nilainya di elemen berikutnya.
  const lab = [...document.querySelectorAll('div,span,p')]
                .find(e => e.children.length === 0 && rapi(e.textContent) === 'NIK');
  const nik = lab && lab.nextElementSibling ? rapi(lab.nextElementSibling.textContent) : '';
  const t = [...document.querySelectorAll('table')].find(x => /Kelompok Skrin/i.test(x.textContent));
  if (!t) return {nik, ada: false};
  const tr = [...t.querySelectorAll('tbody tr')]
               .find(r => r.children.length >= 3 && rapi(r.children[0].textContent).toLowerCase() === hasil.toLowerCase());
  if (!tr) return {nik, ada: true, baris: false};
  return {nik, ada: true, baris: true, status: rapi(tr.children[2].textContent),
          tombol: !!tr.querySelector('button')};
}"""


def baca_detail(halaman) -> dict:
    return halaman.evaluate(_JS_DETAIL, config.TATALAKSANA_FILTER["hasil"]) or {}


def _tunggu_detail(halaman, batas_ms: int = 30_000) -> dict:
    js = (f"() => {{ const d = ({_JS_DETAIL})({portal._teks_js(config.TATALAKSANA_FILTER['hasil'])});"
          " return /ckg-tatalaksana\\/detail/.test(location.pathname) && d.baris && !!d.status; }")
    portal.tunggu_siap(halaman, js, batas_ms, "detail tatalaksana")
    return baca_detail(halaman)


def _selesai(status: str) -> bool:
    return bool(re.search(r"selesai", status or "", re.I))


# ================================================================ form
# Model SurveyJS diambil dari properti komponen React yang merendernya. Dari
# situ nama soal, pilihan, dan JAWABAN yang tersimpan bisa dibaca - lebih
# pasti daripada menebak dari tampilan.
_JS_MODEL = r"""() => {
  let el = document.querySelector('.sd-root-modern');
  for (let up = 0; el && up < 6; up++, el = el.parentElement) {
    const k = Object.keys(el).find(k => k.startsWith('__reactFiber'));
    let f = k ? el[k] : null;
    for (let i = 0; f && i < 40; i++, f = f.return) {
      const p = f.memoizedProps;
      if (p && p.model && p.model.getAllQuestions) return p.model;
    }
  }
  return null;
}"""

# Peta soal per bagian: soal Ya/Tidak, kode (bila Ya), alasan (bila Tidak),
# jenis tindak lanjut (bila Ya). Dikenali dari akhiran nama soal
# (...-diagnosis, ...-obat, dst.) dan bentuknya, bukan dari nomor urut.
_JS_PETA = r"""(bagian) => {
  const m = (""" + _JS_MODEL + r""")();
  if (!m) return null;
  const nilai = q => (q.choices || []).map(c => String(c.value));
  const peta = {};
  for (const b of bagian) {
    const qs = m.getAllQuestions(false).filter(q => q.name.endsWith('-' + b));
    const utama = qs.find(q => q.getType() === 'radiogroup'
                           && nilai(q).sort().join() === 'N,Y');
    if (!utama) { peta[b] = null; continue; }
    const ikut = (q, v) => new RegExp('\\{' + utama.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
                                      + "\\}\\s*=\\s*'" + v + "'").test(q.visibleIf || '');
    const cari = (tipe, v) => qs.find(q => q.getType() === tipe && ikut(q, v));
    peta[b] = {
      utama: utama.name,
      kode: (cari('tagbox', 'Y') || cari('dropdown', 'Y') || {}).name || '',
      jenis: (cari('radiogroup', 'Y') || {}).name || '',
      alasan: (cari('dropdown', 'N') || {}).name || '',
      pilihan: Object.fromEntries(qs.map(q => [q.name,
                 (q.choices || []).map(c => [String(c.value), String(c.text)])])),
    };
  }
  return peta;
}"""

_JS_DATA = r"""() => {
  const m = (""" + _JS_MODEL + r""")();
  if (!m) return null;
  const wajibKosong = m.getAllQuestions(true)
      .filter(q => q.isRequired && q.isEmpty()).map(q => q.title || q.name);
  return {data: m.data, wajibKosong};
}"""

_JS_POPUP_TERBUKA = ("() => [...document.querySelectorAll('.sv-popup')]"
                     ".some(p => p.style.display !== 'none' && p.offsetParent !== null)")


def _soal(halaman, nama: str):
    return halaman.locator(f'[data-name="{nama}"]')


def _tunggu_soal(halaman, nama: str, batas_ms: int = 6_000) -> bool:
    """Soal lanjutan baru muncul sesudah soal Ya/Tidak dijawab."""
    js = f"() => !!document.querySelector('[data-name={portal._teks_js(nama)}]')"
    ok = portal.tunggu_kondisi(halaman, js, batas_ms)
    if ok:
        # SurveyJS baru merender isi soal yang sudah masuk layar.
        try:
            _soal(halaman, nama).first.scroll_into_view_if_needed(timeout=3_000)
        except Exception:
            pass
        halaman.wait_for_timeout(300)
    return ok


def _klik_radio(halaman, nama: str, teks: str) -> bool:
    soal = _soal(halaman, nama)
    if not soal.count():
        return False
    soal.first.scroll_into_view_if_needed(timeout=3_000)
    label = soal.first.locator("label").filter(has_text=re.compile(rf"^\s*{re.escape(teks)}\s*$"))
    if not label.count():
        return False
    label.first.click(timeout=4_000)
    halaman.wait_for_timeout(400)
    return True


def _pilih_daftar(halaman, nama: str, teks: str, tagbox: bool) -> bool:
    """
    Pilih satu pilihan dropdown/tagbox SurveyJS dengan klik sungguhan.

    Tagbox (pilih banyak) TETAP TERBUKA sesudah memilih; ditutup dengan klik
    pada judul soalnya. Escape tidak menutup popup SurveyJS.
    """
    if not _tunggu_soal(halaman, nama):
        return False
    soal = _soal(halaman, nama).first
    pemicu = soal.locator(".sd-tagbox, .sd-dropdown").first
    pemicu.click(timeout=4_000)
    portal.tunggu_kondisi(halaman, portal.ADA_OPSI, 4_000, 100)
    opsi = halaman.locator('[role="option"]').filter(
        has_text=re.compile(rf"^\s*{re.escape(teks)}\s*$"))
    pilih = None
    for j in range(opsi.count()):
        if opsi.nth(j).is_visible():
            pilih = opsi.nth(j)
            break
    if pilih is None:
        return False
    pilih.click(timeout=4_000)
    halaman.wait_for_timeout(400)
    if tagbox or halaman.evaluate(_JS_POPUP_TERBUKA):
        try:
            soal.locator(".sd-question__title").first.click(timeout=3_000)
        except Exception:
            pass
        portal.tunggu_kondisi(halaman, f"() => !({_JS_POPUP_TERBUKA})()", 3_000)
    return True


def isi_form(halaman, jawaban: dict) -> tuple[str, dict]:
    """
    Isi form tatalaksana. Kembalikan (galat, harapan) - galat '' bila semua
    jawaban sudah tercatat di model form dan tidak ada soal wajib kosong.
    TIDAK menekan Kirim.
    """
    if not form.tunggu_siap(halaman, 25_000):
        return ("form tidak ter-render" if not form.stuck(halaman) else "stuck"), {}
    peta = halaman.evaluate(_JS_PETA, BAGIAN)
    if not peta:
        return "model form tidak terbaca", {}
    harapan: dict = {}
    for k in BAGIAN:
        p = peta.get(k)
        if not p:
            return f"soal {k} tidak ada di form", {}
        jawab, nilai = jawaban[k]
        if not _klik_radio(halaman, p["utama"], "Ya" if jawab == "Y" else "Tidak"):
            return f"{k}: pilihan {'Ya' if jawab == 'Y' else 'Tidak'} tidak bisa diklik", {}
        harapan[p["utama"]] = jawab
        if not nilai:
            continue
        if jawab == "Y":
            sasaran = p["kode"] or p["jenis"]
        else:
            sasaran = p["alasan"]
        if not sasaran:
            return f"{k}: soal lanjutan tidak ditemukan", {}
        # Teks pilihan diambil dari FORM yang sedang terbuka, bukan dari
        # PILIHAN: kalau portal mengganti kodenya, isian ditolak di sini.
        teks = dict(p["pilihan"].get(sasaran, [])).get(nilai)
        if not teks:
            return f"{k}: pilihan {nilai!r} tidak ada di form", {}
        if sasaran == p["jenis"]:
            ok = _tunggu_soal(halaman, sasaran) and _klik_radio(halaman, sasaran, teks)
        else:
            ok = _pilih_daftar(halaman, sasaran, teks, tagbox=(sasaran == p["kode"]))
        if not ok:
            return f"{k}: {teks!r} tidak bisa dipilih", {}
        harapan[sasaran] = [nilai] if sasaran == p["kode"] else nilai
    return periksa_isian(halaman, harapan), harapan


def periksa_isian(halaman, harapan: dict) -> str:
    """Bandingkan jawaban yang TERSIMPAN di model form dengan yang diminta."""
    keadaan = halaman.evaluate(_JS_DATA)
    if not keadaan:
        return "model form tidak terbaca"
    data = keadaan.get("data") or {}
    beda = []
    for nama, mau in harapan.items():
        ada = data.get(nama)
        if isinstance(mau, list):
            ada = sorted(str(x) for x in (ada or []))
            mau = sorted(mau)
        if ada != mau:
            beda.append(f"{nama.rsplit('-', 1)[-1]}: {ada!r} (mau {mau!r})")
    if beda:
        return "isian tidak sesuai: " + "; ".join(beda)
    if keadaan.get("wajibKosong"):
        return "soal wajib masih kosong: " + ", ".join(keadaan["wajibKosong"][:4])
    return ""


def kirim(halaman) -> bool:
    if form.kirim(halaman):
        return True
    tombol = halaman.get_by_role("button", name="Kirim", exact=True)
    if not tombol.count():
        return False
    tombol.first.click(timeout=6_000)
    return True


# ================================================================ satu peserta
STATUS_ULANG = pekerjaan.GAGAL_SEMENTARA | {"gagal_isi"}


def _satu_percobaan(halaman, calon: dict, jawaban: dict, r: dict, kerja,
                    baris: list | None = None) -> None:
    """
    Satu percobaan penuh untuk satu peserta. Menulis hasil ke `r`.

    `baris` = daftar yang BARU SAJA dibuka (percobaan pertama); percobaan
    ulang selalu membuka daftar dari awal.
    """
    if baris is None:
        baris, _ = buka_daftar(halaman, kerja)
    nomor = next((b["i"] for b in baris if b["nik"] == calon["nik"]), None)
    if nomor is None:
        # Sudah keluar dari tab Belum: kiriman percobaan sebelumnya ternyata
        # diterima, atau dicatat petugas lain.
        r["status"] = "tuntas" if r.get("terkirim") else "tidak_ditemukan"
        r["keterangan"] += " | tidak ada lagi di tab Belum Pencatatan"
        return
    halaman.locator("table tbody tr").nth(nomor).locator("button").first.click()
    d = _tunggu_detail(halaman)
    # Penjaga terakhir: jangan pernah mencatat tatalaksana orang lain. NIK
    # dari baris daftar harus tertulis di kartu identitas halaman detail.
    try:
        isi = halaman.inner_text("body")
    except Exception:
        isi = ""
    if calon["nik"] not in isi or (d.get("nik") and d["nik"] != calon["nik"]):
        r["status"] = "error"
        r["keterangan"] += " | halaman detail bukan milik NIK ini - dibatalkan"
        return
    if not d.get("baris"):
        r["status"] = "gagal_detail"
        r["keterangan"] += (f" | baris {config.TATALAKSANA_FILTER['hasil']!r}"
                            " tidak ada di halaman detail")
        return
    r["keterangan"] += f" | status awal: {d['status']}"
    if _selesai(d["status"]):
        r["status"] = "tuntas" if r.get("terkirim") else "sudah_tatalaksana"
        return
    if not d.get("tombol"):
        r["status"] = "gagal_mulai"
        r["keterangan"] += " | tombol Mulai Tatalaksana tidak ada"
        return

    t = halaman.locator("table tbody tr").filter(
        has_text=config.TATALAKSANA_FILTER["hasil"]).get_by_role("button", name="Mulai Tatalaksana")
    (t.first if t.count() else halaman.get_by_role("button", name="Mulai Tatalaksana").first).click()
    portal.tunggu_siap(halaman, f"() => location.host === {portal._teks_js(config.HOST_FORM)}"
                                " && document.querySelectorAll('.sd-question').length > 0",
                       30_000, "form tatalaksana")
    galat, _ = isi_form(halaman, jawaban)
    if galat:
        r["status"] = "gagal_isi"
        r["keterangan"] += f" | TIDAK dikirim - {galat}"
        r["gambar"] = simpan_gambar(halaman, f"tatalaksana_{calon['nik'][-4:]}_isi")
        return
    if config.MODE_UJI:
        r["status"] = "uji"
        r["keterangan"] += " | MODE UJI: form terisi & cocok, tidak dikirim"
        return
    if not kirim(halaman):
        r["status"] = "gagal_isi"
        r["keterangan"] += " | tombol Kirim tidak ada"
        return
    r["terkirim"] = True
    r["keterangan"] += " | form dikirim"
    # Portal kembali sendiri ke halaman detail (redirectUrl) - status barisnya
    # yang membuktikan pencatatan diterima.
    d = _tunggu_detail(halaman, 40_000)
    for _ in range(2):
        if _selesai(d.get("status", "")):
            break
        try:
            halaman.reload(wait_until="domcontentloaded")
        except Exception:
            pass
        d = _tunggu_detail(halaman, 20_000)
    if _selesai(d.get("status", "")):
        r["status"] = "tuntas"
        r["keterangan"] += f" | status: {d['status']}"
    else:
        r["status"] = "layanan_sebagian"
        r["keterangan"] += (f" | terkirim, tapi status belum Selesai ({d.get('status') or 'tak terbaca'})"
                            " - dicek ulang")


def _coba_peserta(halaman, calon: dict, jawaban: dict, kerja, urutan: int,
                  baris: list) -> dict:
    r = {"baris": urutan, "nik": calon["nik"], "nama": calon["nama"], "status": "belum",
         "keterangan": f"pelayanan terakhir {calon.get('pelayanan') or '-'}", "tiket": "",
         "tgl_lahir": calon.get("lahir", "")}
    batas = max(1, config.PERCOBAAN_ULANG)
    for percobaan in range(1, batas + 1):
        try:
            _satu_percobaan(halaman, calon, jawaban, r, kerja,
                            baris if percobaan == 1 else None)
        except Exception as e:
            gambar = simpan_gambar(halaman, f"error_tatalaksana_{urutan}")
            r["status"] = "error"
            r["keterangan"] += f" | {type(e).__name__}: " + " ".join(str(e).split())[:300]
            kerja.lapor(f"    ERROR — bukti disimpan: {gambar}")
        if r["status"] not in STATUS_ULANG or kerja.minta_berhenti:
            break
        if percobaan >= batas:
            r["keterangan"] += f" | menyerah setelah {percobaan} percobaan"
            break
        kerja.lapor(f"    percobaan {percobaan} gagal ({r['status']}) - diulang")
        pekerjaan._bersihkan_halaman(halaman, kerja)
        if pekerjaan._galat_jaringan(r):
            pekerjaan._tunggu_jaringan(halaman, kerja)
    r.pop("terkirim", None)
    r.pop("gambar", None)
    return r


# ================================================================ batch
def kerjakan(halaman, kerja, catatan_hasil, jumlah: int, jawaban: dict) -> None:
    """
    Catat tatalaksana sampai `jumlah` peserta, atau sampai daftarnya habis.

    Peserta yang tidak tuntas diingat dan dilewati, supaya robot tidak
    berputar di baris teratas yang sama terus-menerus.
    """
    jumlah = max(1, min(int(jumlah), config.TATALAKSANA_MAKS))
    kerja.total = jumlah
    kerja.lapor(f"Jawaban form: {ringkas_jawaban(jawaban)}")
    sudah: set[str] = set()
    beruntun = 0
    urutan = 0
    while urutan < jumlah and not kerja.minta_berhenti:
        if not kerja.akun:
            kerja.akun = portal.nama_akun(halaman)
        try:
            baris, lencana = buka_daftar(halaman, kerja)
        except Exception as e:
            kerja.pesan = f"Daftar tatalaksana tidak bisa dibuka: {' '.join(str(e).split())[:200]}"
            kerja.lapor(kerja.pesan)
            simpan_gambar(halaman, "error_daftar_tatalaksana")
            break
        if urutan == 0:
            kerja.lapor(f"Belum Pencatatan Tatalaksana: {lencana if lencana >= 0 else '?'} peserta")
            if lencana >= 0:
                kerja.total = min(jumlah, lencana)
        calon = next((b for b in baris if b["nik"] not in sudah), None)
        if calon is None:
            kerja.pesan = ("Daftar Belum Pencatatan habis." if not baris else
                           "Semua peserta di halaman pertama daftar sudah dicoba dan belum tuntas "
                           "- periksa hasilnya, lalu jalankan lagi.")
            kerja.lapor(kerja.pesan)
            kerja.total = urutan          # bilah kemajuan berakhir penuh
            break
        urutan += 1
        sudah.add(calon["nik"])
        kerja.lapor(f"[{urutan}/{kerja.total}] {calon['nama']}")
        r = _coba_peserta(halaman, calon, jawaban, kerja, urutan, baris)
        r["waktu"] = datetime.now().strftime("%H:%M:%S")
        kerja.hasil.append(dict(r))
        kerja.selesai = urutan
        catatan_hasil.tambah(r)
        kerja.lapor(f"    {r['status']} · {r['keterangan'][:200]}")

        beruntun = beruntun + 1 if r["status"] in STATUS_ULANG else 0
        if config.BERHENTI_SETELAH_GAGAL and beruntun >= config.BERHENTI_SETELAH_GAGAL:
            kerja.pesan = (f"Dihentikan: {beruntun} peserta gagal berturut-turut. "
                           "Periksa catatannya, lalu jalankan lagi.")
            kerja.lapor(kerja.pesan)
            break
    if kerja.minta_berhenti:
        kerja.lapor("Dihentikan oleh pengguna.")
