"""
Pengisian satu form skrining (SurveyJS, di form.kemkes.go.id).

Aturan menjawabnya dipindahkan dari macro ALL DEWASA_LANSIA PARAMETER V4.5
(skrip `IsiKirim`/`IsiKirimB` dan pemilih nilai angka), bukan disusun ulang �
aturan itu sudah teruji pada ribuan peserta.

Yang BERBEDA dari macro, dan sengaja:
  * Keputusan tetap dihitung di JS (satu sumber kebenaran), tapi KLIK-nya
    dilakukan Playwright. Macro memakai `el.click()` sintetis lalu menembakkan
    kejadian input/change satu per satu supaya Vue mau menerima; klik Playwright
    memang klik sungguhan sehingga tidak perlu tipuan itu.
  * Angka diketik dengan penekanan tombol asli, menggantikan XType. Kolom angka
    SurveyJS menolak nilai yang dipasang langsung � persoalan yang sama sudah
    terbukti lagi di kolom pencarian NIK portal.
"""
from __future__ import annotations

import re

import config
import portal

# ---------------------------------------------------------------- deteksi
# Penanda satu-satunya bahwa form benar-benar ter-render adalah jumlah
# `.sd-question`. JANGAN memakai `.sd-root-modern`/`.sd-body`: halaman stuck
# "Kembali ke Halaman Utama" tetap punya container itu dalam keadaan kosong,
# sehingga dipakai sebagai penanda akan membuat penjagaan stuck gagal total.
JUMLAH_SOAL = "() => document.querySelectorAll('.sd-question').length"

FORM_STUCK = """() => {
  if (!/form\\.kemkes/i.test(location.host)) return false;
  if (document.querySelectorAll('.sd-question').length > 0) return false;
  const t = (document.body.innerText || '').trim();
  if (/memuat|loading|mohon tunggu/i.test(t)) return false;
  return t.length <= 20 || /Kembali ke Halaman Utama/i.test(t);
}"""

# ---------------------------------------------------------------- keputusan
# Salinan aturan macro. Bedanya: mengembalikan DAFTAR id radio yang harus
# diklik, bukan mengkliknya sendiri.
PILIH_RADIO = """(p) => {
  const rapi = s => (s || '').replace(/\\s+/g, ' ').trim();
  const konteks = rapi(document.body.innerText || '').toLowerCase();
  const geriatri = /kognitif|mobilisasi|malnutrisi|depresi|barthel/i.test(konteks);
  const kanker = /kanker\\s*payudara/i.test(konteks);
  const tidakNormal = /tidak|abnormal|positif|ya/.test((p.param || '').toLowerCase());
  const hasil = [];
  let urutan = -1;   // nomor urut pertanyaan radio dalam form ini

  document.querySelectorAll('[id^="sq_"]').forEach(q => {
    const radio = [...q.querySelectorAll('input[type="radio"]')];
    if (!radio.length) return;
    urutan += 1;
    // JAWABAN LAMA HANYA DILEWATI BILA TIDAK SEDANG MENIMPA.
    //
    // Alur "perbaiki form" membuka form yang SUDAH terjawab - seluruh
    // pertanyaannya sudah punya pilihan - jadi dengan aturan lama tidak ada
    // satu pun yang tersentuh, dan form itu terkirim ulang dengan jawaban
    // salah yang sama persis. `p.timpa` yang membedakannya, dan itu hanya
    // dinyalakan untuk baris yang memang ada di daftar boleh-ditimpa.
    if (radio.some(r => r.checked) && !p.timpa) return;
    const opsi = radio.map(r => {
      const lab = q.querySelector('label[for="' + r.id + '"]') || r.closest('label') || r.parentElement;
      return {id: r.id, teks: rapi(lab && (lab.innerText || lab.textContent))};
    });
    const ada = re => opsi.some(o => re.test(o.teks.trim()));
    const cari = re => opsi.find(o => re.test(o.teks.trim()));
    const soal = rapi(q.innerText);
    let pilih = null;

    if (/dilakukan\\s*pemeriksaan|melakukan\\s*pemeriksaan|pemeriksaan\\s*antropometri|pemeriksaan\\s*gula|pemeriksaan\\s*tekanan/i.test(soal)
        && !/pernah|riwayat/i.test(soal)
        && !/radiograf|toraks|thoraks|rontgen|x-?ray/i.test(soal)) {
      // Pengecualian radiografi toraks: pertanyaan "Apakah dilakukan
      // pemeriksaan radiografi toraks?" pada form X-Ray TB cocok dengan pola
      // di atas, tapi jawabannya "Tidak" - rontgen dada tidak dikerjakan di
      // skrining ini. Terbaca dari jawaban asli petugas pada form X-Ray TB
      // Anak, dan form dewasa memuat pertanyaan yang sama persis.
      pilih = cari(/^ya\\b/i);
    } else if (geriatri) {
      if (/kognitif/i.test(konteks)) {
        pilih = ada(/benar semua/i)
          ? cari(tidakNormal ? /tidak tahu/i : /benar semua/i)
          : cari(tidakNormal ? /^tidak$/i : /^ya$/i);
      } else if (/mobilisasi/i.test(konteks)) {
        pilih = cari(tidakNormal ? /^tidak$/i : /^ya$/i);
      } else if (/malnutrisi|depresi/i.test(konteks)) {
        pilih = cari(tidakNormal ? /^ya$/i : /^tidak$/i);
      } else if (/barthel/i.test(konteks)) {
        if (!tidakNormal) {
          pilih = ada(/^terkendali teratur/i) ? cari(/^terkendali teratur/i) : cari(/^mandiri/i);
        } else {
          pilih = (ada(/^terkendali teratur/i) && cari(/kadang.*tidak terkendali/i))
               || cari(/tergantung pertolongan/i) || cari(/tidak mampu/i)
               || cari(/tergantung orang/i) || cari(/butuh pertolongan/i);
        }
      }
    } else if (kanker) {
      pilih = ada(/sadanis/i) ? cari(/sadanis/i) : cari(/^normal/i);
    } else if (/aktivitas\\s*fisik/i.test(konteks) && urutan === 0) {
      // HANYA pertanyaan pertama yang dijawab "Ya" � itu yang memunculkan
      // kolom jumlah hari & menit. Pertanyaan sesudahnya tetap "Tidak",
      // mengikuti macro (PickYa_Q1, lalu PickTidak_Q2..Q6).
      pilih = cari(/^ya\\b/i);
    }

    // CKG SEKOLAH: soal yang jawabannya ADA di data murid. Form Kebugaran
    // Jasmani kini berupa RADIO (dulu dropdown), dan tanpa blok ini pilihan
    // bawaan di bawah selalu mengenai "Baik sekali" - kebugaran hitungan BB/TB
    // tidak pernah sampai ke portal (uji tiruan 6 Okt 2026). Aturannya sama
    // dengan PILIHAN_SEKOLAH untuk dropdown.
    if (!pilih && p.sekolah) {
      const s = soal.toLowerCase();
      let mau = '';
      if (/tajam penglihatan|daya lihat/.test(s)) {
        const v = String(p.visus || '').toLowerCase();
        const sisi = /kiri/.test(s) ? 'kiri' : 'kanan';
        mau = (v.includes(sisi) || /^(tidak normal|abnormal|ada)/.test(v)) ? 'tidak normal' : 'normal';
      } else if (/serumen/.test(s)) {
        mau = /^ada/i.test(String(p.serumen || '')) ? 'ada serumen' : 'tidak ada serumen';
      } else if (/kacamata/.test(s)) {
        mau = /^ya/i.test(String(p.kacamata || '')) ? 'ya' : 'tidak';
      } else if (/kebugaran/.test(s) && p.kebugaran) {
        mau = String(p.kebugaran).toLowerCase().trim();
      }
      if (mau) {
        pilih = opsi.find(o => o.teks.toLowerCase() === mau)
             || opsi.find(o => o.teks.toLowerCase().startsWith(mau));
      }
    }

    if (!pilih) {
      pilih = cari(/^normal\\b|^tidak ada\\b|^tidak\\b|^negatif|^baik\\b|^lengkap|^sehat|^non\\s*dis/i)
           || cari(/^ya$/i) || opsi[0];
    }
    if (pilih) hasil.push({id: pilih.id, soal: soal.slice(0, 60), jawab: pilih.teks.slice(0, 40)});
  });
  return hasil;
}"""

# Dropdown yang belum terjawab. Yang dikembalikan indeksnya, supaya Playwright
# yang membukanya dengan klik sungguhan.
DROPDOWN_KOSONG = """() => {
  const semua = [...document.querySelectorAll('.sd-dropdown')];
  const keluar = [];
  semua.forEach((dd, i) => {
    if (dd.offsetParent === null) return;
    const kelas = String(dd.className || '');
    if (!/sd-dropdown--empty/.test(kelas)) return;   // sudah terjawab
    keluar.push(i);
  });
  return keluar;
}"""

# Nilai untuk tiap kolom angka � salinan pemilih nilai milik macro.
NILAI_ANGKA = """(p) => {
  const ctx = (document.body.innerText || '').toLowerCase();
  const isian = [...document.querySelectorAll('input[type="number"].sd-input')]
                  .filter(e => e.offsetParent !== null);
  const keluar = [];
  let tc = 0;
  isian.forEach((el, ix) => {
    const q = el.closest('.sd-question');
    const label = q ? (q.innerText || '').toLowerCase() : '';
    let v = null;
    if (/gizi|antropometri/.test(ctx)) {
      if (/berat/.test(label)) v = p.bb;
      // "PANJANG BADAN", bukan tinggi: bayi diukur berbaring, dan form
      // pertumbuhan balita memakai kata itu.
      else if (/tinggi|panjang/.test(label)) v = p.tb;
      else if (/lingkar|perut/.test(label)) v = p.lp;
      else v = [p.bb, p.tb, p.lp][ix];
    } else if (/tekanan\\s*darah/.test(ctx)) {
      if (/ke[- ]?2|kedua/.test(label)) v = null;
      else if (/sistol/.test(label)) v = p.sistole;
      else if (/diastol/.test(label)) v = p.diastole;
      else { v = (tc === 0 ? p.sistole : (tc === 1 ? p.diastole : null)); tc++; }
    } else if (/gula\\s*darah/.test(ctx)) {
      if (/kedua|gds\\s*2|puasa|gdp/.test(label)) v = null;
      else if (/sewaktu|gds/.test(label)) v = p.gds;
      else v = (ix === 0 ? p.gds : null);
    } else if (/hemoglobin|anemia|talasemia/.test(ctx) && p.hb) {
      // CKG Sekolah memuat hasil Hb sungguhan di CSV (mis. 13.2), jadi dipakai
      // apa adanya - bukan diturunkan dari parameter seperti Dewasa/Lansia.
      v = p.hb;
    } else if (/berat\\s*lahir/.test(ctx)) {
      // SATUANNYA GRAM di sini, sedangkan form pertumbuhan memakai KILOGRAM -
      // satu-satunya tempat di portal yang bercampur satuan. Dulu kolom ini
      // diisi p.bb, sehingga balita 1 tahun tercatat berat lahir "10" gram.
      // Kolom kedua = penimbangan pada usia >24 jam, juga gram.
      if (p.berat_lahir) v = (ix === 0 ? p.berat_lahir : (p.berat_kini || null));
      else v = (ix === 0 ? p.bb : null);
    } else if (/aktivitas\\s*fisik/.test(ctx)) {
      // DIBACA DARI FORM ASLINYA (form.kemkes.go.id, 31 Agustus 2026), bukan
      // ditebak. CKG Sekolah punya DUA pertanyaan, dan KEDUANYA menanyakan
      // JUMLAH HARI - tidak ada kolom menit sama sekali:
      //
      //   1. "Dalam 7 hari terakhir, berapa hari Anda aktif secara fisik
      //       dalam waktu total selama minimal 60 menit sehari?"
      //   2. "Biasanya dalam satu minggu, berapa hari ... minimal 60 menit ...?"
      //
      // "60 menit" itu bagian dari PERTANYAANNYA, bukan kolom yang harus diisi.
      // Dua tebakanku sebelumnya sama-sama salah karena tak melihat form ini:
      // mendahulukan "hari" mengisi 5,5 dan mendahulukan "menit" mengisi 30,30 -
      // padahal 30 hari dalam seminggu itu mustahil.
      //
      // Jadi bawaannya JUMLAH HARI. Menit hanya bila pertanyaannya memang
      // menanyakan menit ("berapa menit", "durasi").
      if (/berapa\\s*menit|durasi/.test(label)) v = p.menit_aktivitas || 30;
      else v = p.hari_aktivitas || 6;
    } else {
      v = 0;
    }
    // PENGAMAN TERAKHIR - UKURAN TUBUH TIDAK BOLEH NOL.
    //
    // Cabang "lain-lain" di atas mengisi 0, dan itu memang benar untuk
    // pertanyaan hitungan ("berapa kali ...", "jumlah ..."). Tapi 0 kg dan
    // 0 cm adalah ukuran yang MUSTAHIL, dan itulah yang tercatat di portal
    // begitu judul halamannya tidak memuat kata "gizi"/"antropometri" -
    // persis yang terjadi pada form pertumbuhan balita 2 Sep 2026.
    //
    // Hanya berlaku bila cabang terakhir yang memutuskan (v masih 0), jadi
    // cabang lain yang sudah menetapkan nilainya tidak terganggu.
    if (v === 0) {
      // Kata "badan" TIDAK diwajibkan: judulnya bisa "Berat Badan (kg)"
      // maupun sekadar "Berat (kg)". Yang dikecualikan hanya "berat
      // lahir" - itu gram, bukan berat sekarang - dan "lingkar kepala",
      // yang tidak ada angkanya di data kita sehingga lebih baik
      // dibiarkan kosong daripada diisi lingkar perut.
      if (/berat/.test(label) && !/lahir/.test(label) && p.bb) v = p.bb;
      else if (/tinggi|panjang/.test(label) && p.tb) v = p.tb;
      else if (/lingkar/.test(label) && !/kepala/.test(label) && p.lp) v = p.lp;
      else if (/lingkar\\s*kepala/.test(label)) v = null;
    }
    if (v !== null && v !== undefined && v !== '') keluar.push({indeks: ix, nilai: String(v)});
  });
  return keluar;
}"""


# Pilihan yang diinginkan untuk satu dropdown, dilihat dari BUNYI PERTANYAANNYA.
# Perlu per-pertanyaan, bukan per-indeks: form Telinga & Mata sekolah memisahkan
# kanan dan kiri (Q9 vs Q10), sedangkan CSV hanya punya SATU kolom visus yang
# menyebut sisi mana yang terganggu.
# Mengembalikan kata kunci; Python yang mencocokkannya ke teks opsi.
# TANDA TANGAN SATU PARAMETER, BUKAN DUA. Pemanggilnya mengirim
# `[_nilai(orang), i]`, dan Playwright memperlakukan daftar itu sebagai SATU
# argumen - jadi versi `(p, indeks)` membuat `p` berisi seluruh daftar dan
# `indeks` bernilai undefined. Akibatnya `document.querySelectorAll(...)[undefined]`
# selalu kosong dan fungsi ini SELALU mengembalikan '' - tidak pernah sekali pun
# memilih jawaban. Itu lolos tanpa terlihat karena jawaban cadangan di
# `_isi_dropdown` ("normal", "tidak ada", "tidak", "baik") kebetulan sama dengan
# isi seluruh data yang dipakai selama ini. Begitu ada murid yang visusnya
# "Visus Kanan", kekeliruan itu baru terasa.
PILIHAN_SEKOLAH = r"""([p, indeks]) => {
  if (!p.sekolah) return '';
  const rapi = s => (s || '').replace(/\s+/g, ' ').trim().toLowerCase();
  const dd = document.querySelectorAll('.sd-dropdown')[indeks];
  if (!dd) return '';
  const q = dd.closest('.sd-question');
  const t = rapi(q ? q.innerText : '');

  if (/tajam penglihatan|daya lihat/.test(t)) {
    // Satu kolom "Visus Mata" menyebut SISI yang terganggu, jadi jawaban tiap
    // sisi ditentukan dari ada tidaknya nama sisi itu di dalam nilainya:
    // "Visus Kanan dan Kiri" memuat keduanya, "Normal" tidak memuat satu pun.
    // "Tidak Normal" polos - tanpa menyebut sisi - dianggap kena dua-duanya.
    const v = rapi(p.visus);
    const sisi = /kiri/.test(t) ? 'kiri' : 'kanan';
    const kena = v.includes(sisi) || /^(tidak normal|abnormal|ada)/.test(v);
    return kena ? 'tidak normal' : 'normal';
  }
  if (/serumen/.test(t)) {
    return /^ada/i.test(String(p.serumen || '')) ? 'ada serumen' : 'tidak ada serumen';
  }
  if (/kacamata/.test(t)) {
    return /^ya/i.test(String(p.kacamata || '')) ? 'ya' : 'tidak';
  }
  if (/kebugaran/.test(t)) return rapi(p.kebugaran);
  return '';
}"""


def _visus(p: dict) -> str:
    """
    Satu nilai visus, apa pun tata letak CSV yang dipakai.

    Template sekolah kembali memakai SATU kolom "Visus Mata". Berkas lama yang
    sudah terlanjur dibuat masih memuat dua kolom kanan & kiri, jadi keduanya
    disatukan di sini - bukan di skrip halaman - supaya sisi mana pun yang
    ditandai tidak normal tetap terbawa.
    """
    if str(p.get("visus", "")).strip():
        return str(p["visus"])
    def kena(kunci: str) -> bool:
        return bool(re.search(r"tidak|abnormal|ada", str(p.get(kunci, "")), re.I))
    ka, ki = kena("visus_kanan"), kena("visus_kiri")
    if ka and ki:
        return "Visus Kanan dan Kiri"
    if ka:
        return "Visus Kanan"
    if ki:
        return "Visus Kiri"
    return "Normal"


def _nilai(orang) -> dict:
    """
    Angka dan parameter peserta yang dibutuhkan skrip di atas.

    Untuk CKG Sekolah, berat, tinggi, dan hemoglobin memakai ANGKA NYATA dari
    CSV — bukan diturunkan dari parameter seperti Dewasa/Lansia, karena data
    murid memang memuat hasil pengukurannya. Gula darah dan tekanan darah tetap
    berupa parameter di kedua kategori.
    """
    p = orang.parameter
    dasar = {
        # Aktivitas fisik: 6 atau 7 hari, 30 menit. Diundi dari NIK lewat
        # `_pecahan`, jadi peserta yang sama SELALU menjawab sama - dijalankan
        # ulang berapa kali pun. Itu penting karena peserta yang gagal memang
        # dijalankan ulang, dan jawaban yang berubah-ubah akan terlihat seperti
        # dua orang berbeda di catatan portal.
        "hari_aktivitas": 6 if orang._pecahan(7) < 0.5 else 7,
        "menit_aktivitas": 30,
        "bb": orang.bb, "tb": orang.tb,
        "lp": orang.lingkar_perut,
        "sistole": orang.sistole, "diastole": orang.diastole,
        "gds": orang.gds,
        "param": p.get("geriatri", "Normal"),
    }
    # BALITA memakai angka tubuhnya sendiri. Tanpa ini, `orang.bb`/`orang.tb`
    # menurunkan ukuran ORANG DEWASA dari parameter gizi - anak satu tahun
    # tercatat 64 kg dan 151 cm. Angkanya sudah lama ada di `peserta.py`
    # (bb_balita, tb_balita, berat lahir dalam gram), hanya belum pernah
    # dipakai siapa pun; di sinilah tempatnya masuk.
    if getattr(orang, "dari_balita", False):
        dasar.update({
            "bb": orang.bb_balita,
            "tb": orang.tb_balita,
            # Form "Berat Lahir" (rowfrm000010) memakai GRAM, sedangkan form
            # pertumbuhan memakai KILOGRAM. Satu-satunya tempat di seluruh
            # portal yang bercampur satuan, jadi dipisah namanya.
            "berat_lahir": orang.berat_lahir_gram,
            "berat_kini": orang.berat_kini_gram,
            "imunisasi": p.get("imunisasi", "Lengkap"),
            "balita": True,
        })
        return dasar

    if "sekolah" not in p and "kelas" not in p:
        return dasar

    def angka(kunci: str, cadangan: float) -> float:
        try:
            return float(str(p.get(kunci, "")).replace(",", "."))
        except ValueError:
            return cadangan

    dasar.update({
        "hb": angka("hemoglobin", 13),
        "gigi": p.get("gigi", "Normal"),
        "serumen": p.get("serumen", "Tidak Ada"),
        "visus": _visus(p),
        "kacamata": p.get("berkacamata", "Tidak"),
        "kebugaran": p.get("kebugaran", "Baik"),
        "cemas": p.get("gejala_cemas", "Normal"),
        "depresi": p.get("gejala_depresi", "Normal"),
        "sekolah": True,
    })
    return dasar


def tunggu_siap(halaman, batas_ms: int = 20_000) -> bool:
    """Tunggu sampai pertanyaan form benar-benar ter-render."""
    habis = batas_ms
    while habis > 0:
        try:
            if halaman.evaluate(JUMLAH_SOAL) > 0:
                return True
        except Exception:
            pass
        halaman.wait_for_timeout(400)
        habis -= 400
    return False


def stuck(halaman) -> bool:
    """Benar bila form gagal ter-render (halaman kosong / 'Kembali ke Halaman Utama')."""
    for _ in range(4):
        try:
            if not halaman.evaluate(FORM_STUCK):
                return False
        except Exception:
            return False
        halaman.wait_for_timeout(500)
    return True


def _klik_radio(halaman, id_radio: str) -> bool:
    """
    Klik satu pilihan radio.

    Input radio SurveyJS disembunyikan secara visual, jadi yang diklik adalah
    label pembungkusnya � pola yang sama dengan checkbox kustom portal.
    """
    inp = halaman.locator(f'[id="{id_radio}"]')
    if not inp.count():
        return False
    label = inp.locator("xpath=ancestor::label[1]")
    for sasaran in (label, inp):
        try:
            if sasaran.count():
                sasaran.first.scroll_into_view_if_needed(timeout=2_000)
                sasaran.first.click(timeout=3_000)
                return True
        except Exception:
            continue
    try:
        inp.first.click(timeout=3_000, force=True)
        return True
    except Exception:
        return False


def jawab_radio(halaman, orang, timpa: bool = False) -> int:
    keputusan = halaman.evaluate(PILIH_RADIO, {**_nilai(orang), "timpa": bool(timpa)})
    terjawab = 0
    for k in keputusan:
        if _klik_radio(halaman, k["id"]):
            terjawab += 1
    if keputusan:
        halaman.wait_for_timeout(500)
    return terjawab


def jawab_dropdown(halaman, orang) -> int:
    """
    Jawab dropdown yang masih kosong.

    Dropdown dibuka satu per satu dan pilihannya dipersempit ke pertanyaan
    yang bersangkutan: Escape TIDAK menutup dropdown SurveyJS, sehingga
    beberapa popup bisa terbuka bersamaan dan pemilih global bisa salah sasaran.
    """
    konteks = (halaman.inner_text("body") or "").lower()
    aktivitas = "aktivitas fisik" in konteks
    tekanan = "tekanan darah" in konteks

    terjawab = 0
    for _ in range(12):
        kosong = halaman.evaluate(DROPDOWN_KOSONG)
        # Di form Tekanan Darah hanya tiga dropdown pertama yang wajib;
        # sisanya opsional dan sengaja dilewati, sama seperti di macro.
        if tekanan:
            kosong = [i for i in kosong if i < 3]
        if not kosong:
            break
        i = kosong[0]
        dd = halaman.locator(".sd-dropdown").nth(i)
        try:
            if (dd.get_attribute("aria-expanded") or "").lower() != "true":
                dd.scroll_into_view_if_needed(timeout=2_000)
                dd.click(timeout=4_000)
            portal.tunggu_kondisi(halaman, portal.ADA_OPSI, 3_000, 100)
        except Exception:
            break

        # Dropdown PERTAMA form Aktivitas Fisik harus "Ya" � itu yang
        # memunculkan kolom jumlah hari & menit. Dropdown sesudahnya "Tidak".
        khas = ""
        try:
            khas = halaman.evaluate(PILIHAN_SEKOLAH, [_nilai(orang), i]) or ""
        except Exception:
            khas = ""
        if khas:
            kunci = (khas,)
        elif aktivitas and i == 0:
            kunci = ("ya",)
        else:
            kunci = ("normal", "tidak ada", "tidak", "negatif", "baik", "lengkap", "sesuai")

        opsi = halaman.locator('[role="option"]')
        pilih = None
        for j in range(min(opsi.count(), 40)):
            satu = opsi.nth(j)
            try:
                if not satu.is_visible():
                    continue
                teks = (satu.inner_text() or "").strip().lower()
                if teks in kunci or any(teks.startswith(k) for k in kunci):
                    pilih = satu
                    break
                if pilih is None:
                    pilih = satu
            except Exception:
                continue
        if pilih is None:
            break
        try:
            pilih.click(timeout=3_000)
            terjawab += 1
            halaman.wait_for_timeout(500)
        except Exception:
            break
    return terjawab


def _tunggu_kolom_angka(halaman, batas_ms: int = 2_800) -> None:
    """
    Tunggu kolom angka muncul pada form yang memunculkannya secara bersyarat.

    Di form Aktivitas Fisik, kolom jumlah hari dan menit baru dirender setelah
    pertanyaan pertama dijawab "Ya", jadi pembacaan langsung bisa mendapati
    nol kolom padahal sebentar lagi ada.
    """
    if not halaman.evaluate(
            "() => /aktivitas\\s*fisik/i.test(document.body.innerText || '')"):
        return
    sisa = batas_ms
    while sisa > 0:
        if halaman.evaluate(
                "() => document.querySelectorAll('input[type=number].sd-input').length") > 0:
            return
        halaman.wait_for_timeout(400)
        sisa -= 400


def isi_angka(halaman, orang) -> int:
    """Isi kolom angka dengan ketikan asli (pengganti XType di macro)."""
    _tunggu_kolom_angka(halaman)
    daftar = halaman.evaluate(NILAI_ANGKA, _nilai(orang))
    terisi = 0
    for d in daftar:
        kolom = halaman.locator('input[type="number"].sd-input').nth(d["indeks"])
        try:
            kolom.scroll_into_view_if_needed(timeout=2_000)
            kolom.click(timeout=3_000)
            kolom.press("Control+a")
            kolom.press("Backspace")
            ketik = getattr(kolom, "press_sequentially", None) or kolom.type
            ketik(d["nilai"], delay=50)
            kolom.press("Tab")
            terisi += 1
            halaman.wait_for_timeout(200)
        except Exception:
            continue
    return terisi


def kirim(halaman) -> bool:
    """Tekan tombol Kirim. Tombolnya <input type=button value=Kirim>, bukan <button>."""
    tombol = halaman.locator(
        'input.sd-btn--action[value="Kirim"], input.sd-navigation__complete-btn, '
        'input[type="button"][value="Kirim"]'
    )
    if not tombol.count():
        return False
    try:
        tombol.first.click(timeout=6_000)
        # Sesudah Kirim, portal meninggalkan halaman form. Menunggu soal
        # menghilang jauh lebih cepat daripada jeda tetap saat portal lancar.
        portal.tunggu_kondisi(halaman, portal.TANPA_SOAL, 8_000)
        return True
    except Exception:
        return False


def isi_satu_form(halaman, orang, timpa: bool = False) -> str:
    """
    Isi dan kirim satu form. Kembalikan '' bila berhasil, atau sebab gagalnya.

    `timpa=True` berarti jawaban yang SUDAH ADA ikut diganti - dipakai alur
    perbaikan, misalnya membetulkan form Kesehatan Jiwa yang terlanjur terisi
    salah. Di luar itu jawaban lama tidak pernah disentuh: menimpa jawaban
    petugas adalah hal terakhir yang boleh dilakukan sembarangan.
    """
    if not tunggu_siap(halaman):
        return "stuck" if stuck(halaman) else "form tidak ter-render"

    # Dua lintasan: sebagian pertanyaan baru muncul setelah pertanyaan
    # sebelumnya dijawab, jadi sekali jalan tidak cukup.
    for _ in range(2):
        jawab_radio(halaman, orang, timpa)
        jawab_dropdown(halaman, orang)
        halaman.wait_for_timeout(500)
    isi_angka(halaman, orang)

    sisa = halaman.evaluate(
        """() => [...document.querySelectorAll('[id^="sq_"]')].filter(q => {
             const r = [...q.querySelectorAll('input[type=radio]')];
             return r.length && !r.some(x => x.checked);
           }).length"""
    )
    if not kirim(halaman):
        return f"tombol Kirim tidak ada (sisa {sisa} soal)"
    return "" if sisa == 0 else f"terkirim tapi {sisa} soal radio kosong"
