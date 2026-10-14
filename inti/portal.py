"""
Perkakas khusus portal CKG.

Berisi cara menangani komponen yang tidak standar di portal ini:
  - dropdown buatan sendiri (div, bukan <select>)
  - checkbox tersembunyi (input opacity 0 + div terlihat di atasnya)
  - pemilih tanggal (kalender, bukan kolom ketik)

Pelajaran dari macro UI.Vision yang tetap berlaku di sini:
  * checkbox: yang harus diklik adalah elemen TERLIHAT, bukan input opacity-0
  * dropdown: opsi baru muncul setelah pemicunya diklik
Bedanya, Playwright sudah otomatis menunggu & menggulir, jadi tak perlu
guard/retry buatan sendiri.
"""
from __future__ import annotations

import json
import re
import threading
import time

from playwright.sync_api import Locator, Page, TimeoutError as TimeoutPlaywright

BULAN_ID = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mei", 6: "Jun",
    7: "Jul", 8: "Agt", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Des",
}


# --------------------------------------------------------------------- dasar
def teks_ada(halaman: Page, teks: str) -> bool:
    """Apakah teks muncul di halaman (tidak peka huruf besar/kecil)."""
    isi = halaman.evaluate("() => (document.body.innerText || '')")
    return re.search(re.escape(teks), isi, re.I) is not None


def klik_tombol_persis(halaman: Page, nama: str, timeout: int = 15_000) -> bool:
    """
    Klik tombol yang tulisannya SAMA PERSIS.

    Perlu terpisah dari `klik_tombol` karena pencocokan longgar bisa salah
    sasaran: "Daftarkan" juga cocok dengan "Daftarkan dengan NIK", dan itu
    tombol yang berbeda akibatnya.
    """
    tombol = halaman.get_by_role("button", name=nama, exact=True).first
    try:
        tombol.wait_for(state="visible", timeout=timeout)
        tombol.click()
        return True
    except TimeoutPlaywright:
        return False


def klik_tombol(halaman: Page, nama: str, timeout: int = 15_000) -> bool:
    """Klik tombol berdasarkan tulisannya. False bila tidak ketemu."""
    tombol = halaman.get_by_role("button", name=nama, exact=False).first
    try:
        tombol.wait_for(state="visible", timeout=timeout)
        tombol.click()
        return True
    except TimeoutPlaywright:
        return False



# ------------------------------------------------------------------ pembatas
# Jangkar formulir, dicoba berurutan.
#
# `#nik` TIDAK ADA pada formulir tanpa-NIK. Justru itu tanda keberhasilan
# centang "Tidak punya NIK": `pendaftaran._buka_tanpa_nik` menunggu sampai
# kolom #nik MENGHILANG. Jadi seluruh pencarian yang lewat `wadah_form`
# mengenai wadah kosong, dan diamnya menyeluruh - terbukti pada rekaman
# 9 Sep (struktur_pendaftaran-p1.json): tanggal lahir peserta, jenis kelamin
# peserta, dan tanggal lahir wali sama-sama tak terisi, sedangkan NIK wali,
# nama wali, dan jenis kelamin wali - yang dicari di SELURUH halaman lewat
# `pilih_dropdown_persis` - terisi normal. Tombol "Selanjutnya" lalu tetap
# mati dan pendaftarannya berhenti di 5x_selanjutnya_gagal.
#
# `#tidak-punya-nik` ada di KEDUA bentuk formulir - ia checkbox yang dicentang
# itu sendiri - jadi aman dipakai sebagai jangkar cadangan.
_JANGKAR_FORM = ("//input[@id='nik']", "//input[@id='tidak-punya-nik']")


def wadah_form(halaman: Page) -> Locator:
    """
    Batasi pencarian ke KOTAK FORMULIR pendaftaran saja.

    Penting: tabel daftar peserta di halaman yang sama punya kolom berjudul
    "Tanggal Lahir" dan "Jenis Kelamin". Tanpa pembatasan ini, pencarian
    berdasarkan label bisa tersasar ke judul kolom tabel — dan elemen
    "cursor-pointer" pertama sesudahnya ternyata tautan
    "Lihat petunjuk pengisian nama", bukan kolom tanggal.

    Karena itu TIDAK ADA jalan mundur ke seluruh halaman: bila tak satu pun
    jangkar ketemu, yang dikembalikan wadah kosong, dan pemanggilnya melapor
    "widget tanggal lahir tak ditemukan" - keliru yang bersuara, bukan yang
    diam-diam mengisi kolom yang salah.
    """
    for jangkar in _JANGKAR_FORM:
        f = halaman.locator(f"xpath={jangkar}/ancestor::form[1]")
        if f.count():
            return f.first
        d = halaman.locator(
            f"xpath={jangkar}/ancestor::div"
            "[.//*[contains(normalize-space(.),'Tanggal Lahir')]][1]"
        )
        if d.count():
            return d.first
    return halaman.locator(f"xpath={_JANGKAR_FORM[0]}/ancestor::form[1]").first


def _cari_label(wadah: Locator, label: str) -> Locator:
    """Elemen label di dalam formulir (menerima versi dengan tanda * wajib)."""
    return wadah.locator(
        "xpath=.//*[normalize-space(text())=%s or normalize-space(text())=%s]"
        % (repr(label), repr(label + " *"))
    )


# ---------------------------------------------------------------- dropdown
def _pemicu_dropdown(halaman: Page, label: str) -> Locator:
    """
    Cari kotak dropdown milik sebuah label.

    Portal memakai div ber-class `cursor-pointer` + tinggi `2.9rem` sebagai
    pemicu. Yang dipilih adalah pemicu PERTAMA yang muncul setelah label,
    mengikuti urutan DOM — cara yang sama dipakai di macro setelah pendekatan
    'telusuri induk' terbukti gagal untuk Jenis Kelamin.
    """
    w = wadah_form(halaman)
    return w.locator(
        "xpath=(.//*[normalize-space(text())=%s or normalize-space(text())=%s]"
        "/following::div[contains(@class,'cursor-pointer')][contains(@class,'2.9rem')])[1]"
        % (repr(label), repr(label + " *"))
    )


def pilih_dropdown(halaman: Page, label: str, nilai: str, timeout: int = 15_000) -> bool:
    """
    Pilih satu nilai pada dropdown buatan portal.

    Mengembalikan True bila berhasil. Aman dipanggil saat dropdown sudah
    berisi nilai yang sama — pengecekan dilakukan lebih dulu.
    """
    pemicu = _pemicu_dropdown(halaman, label).first
    try:
        pemicu.wait_for(state="visible", timeout=timeout)
    except TimeoutPlaywright:
        return False
    return _pilih_pada(halaman, pemicu, nilai)


def _pemicu_teks(halaman: Page, teks: str) -> Locator:
    """
    Cari kotak dropdown berdasarkan TEKS yang sedang tampil di dalamnya
    (mis. "Pilih pekerjaan").

    Dipakai di halaman 2 pendaftaran: di sana tidak ada `#nik`, sehingga
    `wadah_form()` tidak bisa dipakai dan pencarian lewat label gagal.
    Teks pemicu justru sudah pasti � terbaca dari rekaman struktur halaman.
    """
    return halaman.locator(
        "xpath=//div[contains(@class,'cursor-pointer')][contains(@class,'2.9rem')]"
        f"[contains(normalize-space(.),{teks!r})]"
    )


def pilih_dropdown_persis(halaman: Page, teks_pemicu: str, nilai: str,
                          timeout: int = 8_000) -> bool:
    """
    Pilih dropdown yang pemicunya bertuliskan teks itu PERSIS, di elemen itu sendiri.

    Bedanya dengan `pilih_dropdown_teks`: di sana pemicu dicari lewat
    `contains(.)`, yang ikut membaca teks seluruh keturunan - sehingga sebuah
    pembungkus besar pun cocok. Akibatnya fatal pada bagian Data Wali:
    pembungkus yang terpilih memuat "Perempuan" milik PESERTA, lalu jalan
    pintas "sudah terisi" di `_pilih_pada` langsung pulang membawa True.
    Dropdown wali tak pernah tersentuh, tapi dilaporkan berhasil.

    `text()` hanya membaca simpul teks milik elemen itu sendiri, jadi yang
    terpilih adalah kotak pemicunya, bukan pembungkusnya.
    """
    pemicu = halaman.locator(f"xpath=//*[normalize-space(text())={teks_pemicu!r}]").last
    try:
        pemicu.wait_for(state="visible", timeout=timeout)
    except TimeoutPlaywright:
        return False

    # Elemen bernilai sama yang SUDAH ADA sebelum dropdown dibuka ditandai dulu.
    # Tanpa ini, "Perempuan" milik PESERTA - yang tampil di atas dan lebih dulu
    # di dokumen - yang terklik: dropdown wali terbuka, opsinya tak tersentuh,
    # dan tidak ada yang terpilih. Cara yang sama sudah terbukti pada kalender.
    halaman.evaluate(
        """(nilai) => document.querySelectorAll('div,li,span,button').forEach(e => {
             // TERLIHAT, bukan sekadar ada. Opsi dropdown sudah tertulis di DOM
             // sejak awal, cuma disembunyikan; menandainya lewat keberadaan
             // membuat opsi yang sah ikut tercoret dan tak ada yang bisa diklik.
             if (e.children.length === 0 && e.offsetParent !== null
                 && (e.textContent || '').trim() === nilai)
               e.setAttribute('data-opsi-lama', '1');
           })""", nilai)

    if (pemicu.get_attribute("aria-expanded") or "").lower() != "true":
        try:
            pemicu.click(timeout=timeout)
        except Exception:
            return False

    # Yang diklik HANYA opsi yang baru muncul, yaitu isi dropdown yang terbuka.
    baru_ = halaman.locator(
        "xpath=//*[(self::div or self::li or self::span or self::button)"
        f" and normalize-space(text())={nilai!r} and not(@data-opsi-lama)]")
    tunggu_kondisi(halaman,
                   "() => !!document.querySelector('div:not([data-opsi-lama])')", 300)
    diklik = False
    for i in range(min(baru_.count(), 8)):
        try:
            if baru_.nth(i).is_visible():
                baru_.nth(i).click(timeout=3_000)
                diklik = True
                break
        except Exception:
            continue
    if not diklik:
        return False
    # Terpilih atau tidak dibuktikan dari HILANGNYA teks ajakan itu, bukan dari
    # kembalian klik. Klik yang "berhasil" tapi tidak mengubah apa pun sudah
    # dua kali membuat laporan ini berbohong.
    return not tunggu_kondisi(halaman, js_ada_teks(teks_pemicu), 1200)


def pilih_dropdown_teks(halaman: Page, teks_pemicu: str, nilai: str,
                        timeout: int = 15_000) -> bool:
    """Seperti `pilih_dropdown`, tapi pemicunya dicari lewat teks isinya."""
    pemicu = _pemicu_teks(halaman, teks_pemicu).first
    try:
        pemicu.wait_for(state="visible", timeout=timeout)
    except TimeoutPlaywright:
        return False
    return _pilih_pada(halaman, pemicu, nilai)


def _pilih_pada(halaman: Page, pemicu: Locator, nilai: str) -> bool:
    """Inti pemilihan: buka pemicu (bila perlu) lalu klik opsi bernama `nilai`."""
    # sudah terisi nilai yang diminta -> tidak perlu diapa-apakan
    if nilai.lower() in (pemicu.inner_text() or "").strip().lower():
        return True

    # jangan klik bila sedang terbuka: klik kedua justru menutupnya
    if (pemicu.get_attribute("aria-expanded") or "").lower() != "true":
        # Bertenggat dan dijaga, dengan alasan yang sama seperti di `centang`:
        # dropdown yang tidak bisa dibuka adalah kegagalan MEMILIH, bukan
        # kerusakan alat, dan harus dilaporkan begitu - bukan melempar galat.
        try:
            pemicu.click(timeout=5_000)
        except Exception:
            return False

    # Opsi portal ini bisa berupa div/li/span/button — bukan selalu role=option.
    # Diambil yang TERLIHAT dan teksnya persis, lalu diklik.
    halaman.wait_for_timeout(400)
    kandidat = halaman.locator(
        "xpath=//*[self::div or self::li or self::span or self::button]"
        f"[normalize-space(text())={nilai!r}]"
    )
    diklik = False
    for i in range(min(kandidat.count(), 8)):
        satu = kandidat.nth(i)
        try:
            if satu.is_visible():
                satu.click(timeout=3_000)
                diklik = True
                break
        except Exception:
            continue
    if not diklik:
        try:
            halaman.get_by_role("option", name=nilai, exact=False).first.click(timeout=3_000)
            diklik = True
        except Exception:
            return False

    halaman.wait_for_timeout(300)
    return True


# ---------------------------------------------------------------- checkbox
def centang(halaman: Page, id_input: str, nyala: bool = True) -> bool:
    """
    Centang checkbox portal.

    Input aslinya opacity-0; yang menerima klik adalah elemen terlihat di
    atasnya. Karena itu klik diarahkan ke elemen di posisi checkbox, bukan
    ke input-nya — persis pelajaran dari macro dulu.
    """
    hasil = halaman.evaluate(
        """(args) => {
            const idInput = args.id;
            const inp = document.getElementById(idInput);
            if (!inp) return 'tak-ada';
            if (inp.checked === args.nyala) return 'sudah';
            const div = document.querySelector(`div#${CSS.escape(idInput)}`);
            let target = div;
            if (!target) {
                const r = inp.getBoundingClientRect();
                target = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
            }
            if (!target || target === inp) target = inp.parentElement || inp;
            target.setAttribute('data-klik-saya', '1');
            target.scrollIntoView({ block: 'center' });
            return 'siap';
        }""",
        {"id": id_input, "nyala": nyala},
    )
    if hasil in ("tak-ada", "sudah"):
        return hasil == "sudah"

    # BERTENGGAT DAN DIJAGA. Versi lama memakai klik tanpa tenggat: bila
    # elemennya tidak pernah bisa diklik, Playwright menunggu 15 detik lalu
    # MELEMPAR - dan lemparan itu lolos sampai `kerjakan_batch`, yang menandai
    # pesertanya "error" sambil MEMBUANG seluruh jejak keterangannya. Satu
    # centang yang meleset jadi terlihat seperti kerusakan besar. Terjadi pada
    # dua murid (2 Sep, 15:16).
    try:
        halaman.locator("[data-klik-saya='1']").first.click(timeout=5_000)
    except Exception:
        halaman.evaluate("() => document.querySelector('[data-klik-saya]')"
                         "?.removeAttribute('data-klik-saya')")
        return False
    halaman.evaluate(
        "() => document.querySelector('[data-klik-saya]')?.removeAttribute('data-klik-saya')"
    )
    halaman.wait_for_timeout(400)
    return bool(halaman.evaluate("(i) => document.getElementById(i)?.checked", id_input)) == nyala


# ---------------------------------------------------------------- tanggal
def _tutup_popup(halaman: Page, popup) -> None:
    """Pastikan popup kalender benar-benar tertutup sebelum lanjut."""
    for _ in range(3):
        try:
            if not popup.count() or not popup.is_visible():
                return
        except Exception:
            return
        try:
            halaman.keyboard.press("Escape")
            halaman.wait_for_timeout(350)
        except Exception:
            pass
    # masih terbuka -> klik area netral di luar kalender
    try:
        halaman.mouse.click(8, 8)
        halaman.wait_for_timeout(300)
    except Exception:
        pass


def _klik_sel(popup, teks: str) -> bool:
    """
    Klik satu sel kalender berdasarkan teksnya.

    Sel bisa berupa <td> dengan teks di elemen anak, jadi dicoba beberapa
    bentuk: seluruh isi <td>, elemen ber-teks persis, lalu pencarian teks
    biasa. Yang diklik hanya yang benar-benar TERLIHAT.
    """
    bentuk = [
        f"xpath=.//td[normalize-space(.)={teks!r}]",
        f"xpath=.//*[normalize-space(text())={teks!r}]",
        f"xpath=.//div[normalize-space(.)={teks!r}]",
    ]
    for pola in bentuk:
        kandidat = popup.locator(pola)
        for i in range(min(kandidat.count(), 12)):
            sel = kandidat.nth(i)
            try:
                if not sel.is_visible():
                    continue
                sel.scroll_into_view_if_needed(timeout=1_500)
                sel.click(timeout=2_500)
                return True
            except Exception:
                continue
    return False


def _panel_tahun_terbuka(popup) -> bool:
    """
    Benar bila kalender sedang menampilkan PILIHAN TAHUN, bukan hari/bulan.

    Panel tahun memuat sederet sel berangka empat digit; tampilan hari paling
    banyak memuat satu (di kepalanya). Empat dipakai sebagai batas aman.
    """
    try:
        return bool(popup.first.evaluate(
            "(e) => [...e.querySelectorAll('td,div,button,li')]"
            ".filter(x => /^(19|20)[0-9]{2}$/.test((x.innerText || '').trim()))"
            ".length >= 4"))
    except Exception:
        return False


def isi_tanggal_lahir(halaman: Page, tanggal, label: str = "Tanggal Lahir",
                     teks_pemicu: str = "Pilih tanggal lahir") -> str:
    """
    Isi tanggal lahir lewat widget kalender.

    Tanggal Lahir BUKAN kolom ketik — tidak ada <input> untuknya. Mengetik
    di sini membuat teks jatuh ke <input> berikutnya (nomor WhatsApp).

    Kembalikan "" bila berhasil, atau keterangan singkat bila gagal —
    supaya jelas langkah mana yang bermasalah.
    """
    w = wadah_form(halaman)

    # Pemicunya bisa ditentukan: bagian Data Wali punya kalendernya SENDIRI,
    # dan portal menulis pemicunya dengan huruf besar ("Pilih Tanggal Lahir")
    # sedangkan milik peserta huruf kecil. XPath `normalize-space` peka huruf,
    # jadi perbedaan itu justru yang membedakan keduanya dengan pasti.
    pemicu = w.locator(
        f"xpath=(.//*[normalize-space(text())={teks_pemicu!r}])[1]")
    if not pemicu.count():
        pemicu = w.locator(
            "xpath=(.//*[normalize-space(text())=%s or normalize-space(text())=%s]"
            "/following::div[contains(@class,'cursor-pointer')]"
            "[not(contains(translate(., 'PETUNJUK', 'petunjuk'), 'petunjuk'))])[1]"
            % (repr(label), repr(label + " *"))
        )
    if not pemicu.count():
        return "widget tanggal lahir tak ditemukan"

    # tandai kalender yang sudah ada supaya popup baru bisa dikenali
    halaman.evaluate(
        "() => document.querySelectorAll('div.mx-datepicker-main')"
        ".forEach(e => e.setAttribute('data-kalender-lama','1'))"
    )
    try:
        pemicu.first.click(timeout=6_000)
    except Exception:
        return "widget tak bisa diklik"
    halaman.wait_for_timeout(700)

    popup = halaman.locator("div.mx-datepicker-main:not([data-kalender-lama])").last
    if not popup.count():
        halaman.keyboard.press("Escape")
        return "popup kalender tak muncul"

    # PANEL TAHUN HARUS BENAR-BENAR TERBUKA.
    #
    # Dulu kliknya dicoba sekali dan kegagalannya ditelan diam-diam
    # (`except: pass`). Akibatnya baru terasa jauh di belakang: kalender tetap
    # pada tampilan HARI, panah ganda di sana memundurkan BULAN - bukan
    # dasawarsa - sehingga 15 kali mundur dari 2026 hanya sampai 2025, lalu
    # dilaporkan "tahun 2018 tak bisa diklik". Padahal 2018 memang tak pernah
    # tampil. Terjadi pada dua murid (3 Sep), dan menjatuhkan seluruh
    # pendaftaran mereka.
    #
    # Jadi dicoba sampai tiga kali, dan HASILNYA DIPERIKSA: panel tahun
    # menampilkan sederet angka empat digit; tampilan hari tidak.
    for _ in range(3):
        if _panel_tahun_terbuka(popup):
            break
        for kelas in ("button.mx-btn-current-year", "button.mx-btn-current-month"):
            b = popup.locator(kelas).first
            if b.count():
                try:
                    b.click(timeout=2_500)
                    halaman.wait_for_timeout(350)
                except Exception:
                    pass
                break
        else:
            break

    # mundur rentang tahun sampai tahun yang dicari terlihat
    for _ in range(15):
        if popup.locator(f"xpath=.//*[normalize-space(.)='{tanggal.year}']").count():
            break
        panah = popup.locator(".mx-btn-icon-double-left").first
        if not panah.count():
            break
        try:
            panah.click(timeout=2_000)
            halaman.wait_for_timeout(250)
        except Exception:
            break

    if not _klik_sel(popup, str(tanggal.year)):
        halaman.keyboard.press("Escape")
        return f"tahun {tanggal.year} tak bisa diklik"
    halaman.wait_for_timeout(400)

    if not _klik_sel(popup, BULAN_ID[tanggal.month]):
        halaman.keyboard.press("Escape")
        return f"bulan {BULAN_ID[tanggal.month]} tak bisa diklik"
    halaman.wait_for_timeout(400)

    hari = popup.locator(
        f"xpath=.//td[not(contains(@class,'not-current-month'))]"
        f"[not(contains(@class,'disabled'))][normalize-space(.)='{tanggal.day}']"
    ).first
    diklik = False
    if hari.count():
        try:
            hari.click(timeout=3_000)
            diklik = True
        except Exception:
            pass
    if not diklik and not _klik_sel(popup, str(tanggal.day)):
        halaman.keyboard.press("Escape")
        return f"tanggal {tanggal.day} tak bisa diklik"

    halaman.wait_for_timeout(500)
    # Verifikasi lewat KETIADAAN teks placeholder, bukan dengan membaca ulang
    # elemen pemicu: begitu tanggal terisi, teks "Pilih tanggal lahir" berganti
    # jadi tanggalnya, sehingga locator lama tidak lagi cocok dan pembacaan
    # ulang akan menggantung sampai kehabisan waktu.
    masih_kosong = w.locator(
        "xpath=.//*[normalize-space(text())='Pilih tanggal lahir']"
    ).count() > 0
    if masih_kosong:
        _tutup_popup(halaman, popup)
        return "sudah diklik tapi kolom tetap kosong"

    # PENTING: tutup popup walau sudah berhasil.
    # Kalau dibiarkan terbuka, ia menutupi elemen di bawahnya (mis. dropdown
    # Jenis Kelamin) sehingga klik berikutnya menunggu sampai kehabisan waktu.
    _tutup_popup(halaman, popup)
    return ""


# ------------------------------------------------- tanggal pemeriksaan (kuota)
def baca_kalender_kuota(halaman: Page) -> list[tuple[int, int]]:
    """
    Baca kalender tanggal pemeriksaan.

    Tombolnya bertuliskan "<tanggal> <sisa kuota>", mis. "3 975".
    Kuota 0 berarti tanggal itu tidak bisa dipilih (biasanya Sabtu/Minggu).
    Kembalikan daftar (tanggal, kuota) urut menaik.
    """
    data = halaman.evaluate(
        r"""() => [...document.querySelectorAll('button')]
              .filter(b => b && b.offsetParent !== null)
              .map(b => (b.innerText || '').replace(/\s+/g, ' ').trim())
              .filter(t => /^\d{1,2} \d+$/.test(t))"""
    )
    hasil = []
    for teks in data:
        hari, kuota = teks.split()
        hasil.append((int(hari), int(kuota)))
    return sorted(hasil)


# KALENDER TANPA KUOTA.
#
# Popup "Konfirmasi Tanggal Pemeriksaan" (sesudah "Mulai Pemeriksaan" ditekan)
# kini hanya menampilkan ANGKA TANGGAL - tombol "29", bukan "29 932". Rekaman
# jalan SDN Lagoa 07 (29 Sep) memperlihatkannya: tombol 1..30 lengkap, dan
# tak satu pun berbentuk "<tanggal> <kuota>". Pembaca kalender lama hanya
# mengenal bentuk berkuota, jadi tanggalnya tidak pernah dipilih, "Simpan"
# ditekan tanpa tanggal, dan pemeriksaan tidak jadi dimulai - petugas harus
# menekan Mulai Pemeriksaan dan memilih tanggal sendiri.
#
# Kalender halaman PENDAFTARAN masih berkuota, jadi bentuk lama tetap dibaca
# lebih dulu; bentuk polos hanya cadangan.
#
# Pencariannya DIBATASI ke wadah yang memuat tulisan "Tanggal Pemeriksaan":
# tombol berangka polos juga dipakai penomoran halaman tabel. Di dalam wadah
# itu, bulan berjalan dikenali sebagai deret 1, 2, 3, ... terpanjang, supaya
# tanggal dari bulan sebelah (28-31 di awal kisi) tidak ikut terhitung.
_JS_KALENDER_POLOS = r"""() => {
  const rapi = s => (s || '').replace(/\s+/g, ' ').trim();
  const angka = b => /^\d{1,2}$/.test(rapi(b.innerText)) ? parseInt(rapi(b.innerText)) : 0;
  const hidup = b => b.offsetParent !== null && !b.disabled
                     && !/disabled|not-current|opacity-50/.test(String(b.className || ''));
  const wadah = [...document.querySelectorAll('div, section, form')]
    .filter(w => w.offsetParent !== null && /Tanggal Pemeriksaan/i.test(w.innerText || ''))
    .filter(w => [...w.querySelectorAll('button')].filter(b => angka(b)).length >= 20)
    .sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length)[0];
  if (!wadah) return [];
  const tombol = [...wadah.querySelectorAll('button')].filter(b => angka(b));
  let mulai = -1, panjang = 0;
  tombol.forEach((b, i) => {
    if (angka(b) !== 1) return;
    let n = 1;
    while (i + n < tombol.length && angka(tombol[i + n]) === n + 1) n++;
    if (n > panjang) { panjang = n; mulai = i; }
  });
  if (mulai < 0) return [];
  document.querySelectorAll('[data-hari-kalender]').forEach(b => b.removeAttribute('data-hari-kalender'));
  const hasil = [];
  tombol.slice(mulai, mulai + panjang).forEach(b => {
    if (!hidup(b)) return;
    b.setAttribute('data-hari-kalender', String(angka(b)));
    hasil.push(angka(b));
  });
  return hasil;
}"""


def _pilih_tanggal_polos(halaman: Page, hari_diinginkan: int | None) -> int | None:
    """Pilih tanggal di kalender tanpa kuota. Hari ini didahulukan."""
    from datetime import date
    try:
        hari = halaman.evaluate(_JS_KALENDER_POLOS)
    except Exception:
        return None
    if not hari:
        return None
    hari_ini = date.today().day
    if hari_diinginkan and hari_diinginkan in hari:
        pilihan = hari_diinginkan
    elif hari_ini in hari:
        pilihan = hari_ini
    else:
        sesudah = sorted(h for h in hari if h > hari_ini)
        pilihan = sesudah[0] if sesudah else sorted(hari)[-1]
    try:
        halaman.locator(f'[data-hari-kalender="{pilihan}"]').first.click(timeout=6_000)
        halaman.wait_for_timeout(500)
        return pilihan
    except Exception:
        return None


def pilih_tanggal_pemeriksaan(halaman: Page, hari_diinginkan: int | None = None) -> int | None:
    """
    Pilih tanggal pemeriksaan di kalender.

    Urutan pilihan:
      1. hari_diinginkan (bila diberi)
      2. HARI INI � termasuk bila kuotanya 0
      3. hari terdekat SESUDAH hari ini yang kuotanya > 0
      4. hari mana pun yang kuotanya > 0

    PENTING: kuota 0 TIDAK berarti tanggal itu terkunci. Portal tetap
    menerimanya, hanya memunculkan konfirmasi "Kuota Pemeriksaan Habis" setelah
    tombol Selanjutnya ditekan. Karena itu hari ini tetap didahulukan � memilih
    hari lain diam-diam berarti peserta terdaftar di tanggal yang salah.
    Konfirmasinya ditangani `lewati_popup_kuota()`.

    Kembalikan tanggal yang dipilih, atau None bila kalender tak terbaca.
    """
    from datetime import date

    kalender = baca_kalender_kuota(halaman)
    if not kalender:
        return _pilih_tanggal_polos(halaman, hari_diinginkan)
    semua = {h: k for h, k in kalender}
    tersedia = {h: k for h, k in kalender if k > 0}

    hari_ini = date.today().day
    if hari_diinginkan and hari_diinginkan in semua:
        pilihan = hari_diinginkan
    elif hari_ini in semua:
        pilihan = hari_ini
    elif tersedia:
        sesudah = sorted(h for h in tersedia if h > hari_ini)
        pilihan = sesudah[0] if sesudah else sorted(tersedia)[0]
    else:
        return None

    kuota = semua[pilihan]
    tombol = halaman.get_by_role("button", name=f"{pilihan} {kuota}", exact=True).first
    try:
        tombol.wait_for(state="visible", timeout=8_000)
        tombol.click()
        halaman.wait_for_timeout(600)
        return pilihan
    except TimeoutPlaywright:
        return None


# Popup galat portal yang MENGHALANGI klik. Overlay-nya menutupi seluruh
# halaman, jadi selama ia terbuka tombol apa pun di belakangnya tidak bisa
# ditekan � gejalanya bukan "popup muncul" melainkan "tombol tidak bisa diklik".
_PESAN_GALAT = ("Gagal memproses data", "Gagal memuat data", "Terjadi kesalahan",
                "Gagal menyimpan")
_TOMBOL_GALAT = ("Oke", "OK", "Ok", "Tutup")


def tutup_popup_galat(halaman: Page) -> str:
    """
    Tutup popup galat portal bila ada. Kembalikan pesannya, atau '' bila tak ada.

    Dipanggil saat sebuah klik gagal: lebih sering penyebabnya popup yang
    menghalangi daripada tombolnya yang benar-benar hilang.
    """
    try:
        isi = halaman.inner_text("body")
    except Exception:
        return ""
    pesan = next((p for p in _PESAN_GALAT if p.lower() in isi.lower()), "")
    if not pesan:
        return ""
    for nama in _TOMBOL_GALAT:
        if klik_tombol_persis(halaman, nama, timeout=2_500):
            halaman.wait_for_timeout(600)
            return pesan
    return pesan + " (tombol tutup tak ditemukan)"


# Popup PEMBERITAHUAN � bukan galat, bukan penolakan. Muncul mis. setelah
# "Daftarkan dengan NIK" berupa anjuran memutakhirkan data ke Dukcapil.
# Pendaftarannya sendiri tetap berhasil, jadi popupnya cukup ditutup.
_PESAN_INFO = ("dukcapil", "perbarui data", "pemutakhiran data",
               "data kependudukan", "belum sesuai")
_TOMBOL_INFO = ("Oke", "OK", "Ok", "Ya", "Lanjut", "Mengerti", "Tutup")


def tutup_popup_info(halaman: Page) -> str:
    """
    Tutup popup pemberitahuan. Kembalikan pesannya, atau '' bila tak ada.

    Dipisahkan dari `tutup_popup_galat` karena artinya berbeda: yang ini tidak
    menandakan kegagalan, jadi tidak boleh membuat peserta dianggap gagal.
    Penolakan "Data peserta tidak valid" TIDAK termasuk di sini dan tetap
    ditangani sendiri.
    """
    try:
        isi = halaman.inner_text("body")
    except Exception:
        return ""
    rendah = isi.lower()
    if "tidak valid" in rendah or POLA_TIDAK_VALID.search(isi):
        return ""
    pesan = next((p for p in _PESAN_INFO if p in rendah), "")
    if not pesan:
        return ""
    # Rekam dulu isi popupnya. Menekan tombol yang salah di sini bisa membatalkan
    # pendaftaran, jadi teks dan daftar tombolnya harus tercatat - bukan cuma
    # "berhasil ditutup", yang tidak bisa dipakai memeriksa apa pun.
    rinci = intip_popup(halaman)
    for nama in _TOMBOL_INFO:
        if klik_tombol_persis(halaman, nama, timeout=2_000):
            halaman.wait_for_timeout(500)
            return f"{pesan} [tombol: {nama}] {rinci}"
    return f"{pesan} [tak ada tombol dikenal] {rinci}"


def intip_popup(halaman: Page) -> str:
    """Teks dan tombol pada lapisan modal teratas, untuk bahan pemeriksaan."""
    try:
        return halaman.evaluate(
            """() => {
                 const rapi = s => (s || '').replace(/\\s+/g, ' ').trim();
                 const lapis = [...document.querySelectorAll('div')].filter(e => {
                   const c = String(e.className || '');
                   return e.offsetParent !== null && /fixed/.test(c)
                          && rapi(e.innerText).length > 10;
                 }).sort((a, b) => a.innerText.length - b.innerText.length);
                 if (!lapis.length) return '(modal tak terdeteksi)';
                 const m = lapis[0];
                 const tombol = [...new Set([...m.querySelectorAll('button')]
                   .filter(b => b.offsetParent !== null)
                   .map(b => rapi(b.innerText)).filter(Boolean))];
                 return rapi(m.innerText).slice(0, 200) + ' || tombol: ' + tombol.join(', ');
               }""")
    except Exception:
        return "(gagal membaca modal)"


def lewati_popup_kuota(halaman: Page) -> bool:
    """
    Tangani konfirmasi "Kuota Pemeriksaan Habis" sesudah tombol Selanjutnya.

    Muncul bila tanggal yang dipilih kuotanya 0 (hari lewat, akhir pekan, atau
    kuota memang habis). Isinya: "Kuota pemeriksaan pada hari ini sudah habis.
    Apakah Anda yakin ingin melanjutkan pendaftaran peserta?" dengan tombol
    "Pilih Tanggal Lain" dan "Lanjut".

    Yang ditekan "Lanjut" � peserta memang harus terdaftar pada tanggal itu,
    bukan digeser diam-diam ke hari lain.

    Nama tombolnya dicocokkan SAMA PERSIS: pencocokan longgar "Lanjut" juga
    mengenai "Lanjutkan" milik popup "Data peserta valid" yang muncul
    sesudahnya, dan keduanya popup yang berbeda.
    """
    if not teks_ada(halaman, "Kuota Pemeriksaan Habis"):
        return False
    return klik_tombol_persis(halaman, "Lanjut", timeout=5_000)


# Menandai semua elemen-daun yang TERLIHAT sebelum dropdown dibuka, supaya
# elemen yang muncul sesudahnya bisa dikenali sebagai opsi � lalu opsi itu
# ditandai balik agar bisa diklik langsung, tanpa perlu menyentuh pemicu lagi.
_TANDAI_LAMA = """() => {
  document.querySelectorAll('[data-ckg-opsi]').forEach(e => e.removeAttribute('data-ckg-opsi'));
  document.querySelectorAll('*').forEach(e => {
    if (e.offsetParent !== null && e.children.length === 0) e.setAttribute('data-ckg-lama', '1');
  });
}"""

_AMBIL_BARU = """() => {
  const keluar = [];
  document.querySelectorAll('*').forEach(e => {
    if (e.offsetParent === null || e.children.length) return;
    if (e.hasAttribute('data-ckg-lama')) return;
    const t = (e.innerText || '').replace(/\\s+/g, ' ').trim();
    if (!t || t.length > 70) return;
    e.setAttribute('data-ckg-opsi', '1');
    keluar.push(t);
  });
  document.querySelectorAll('[data-ckg-lama]').forEach(e => e.removeAttribute('data-ckg-lama'));
  return keluar;
}"""


def ada_pemicu(halaman: Page, teks_pemicu: str) -> bool:
    """Benar bila dropdown dengan teks tersebut masih ada di halaman."""
    return _pemicu_teks(halaman, teks_pemicu).count() > 0


def tunggu_pemicu_hilang(halaman: Page, teks_pemicu: str, batas_ms: int = 1200,
                         nama: str = "") -> bool:
    """
    Tunggu sampai tulisan pemicu dropdown BERGANTI jadi nilai yang dipilih.

    Pengganti jeda tetap sesudah memilih isi dropdown. Syaratnya sah dipakai
    karena pasti SALAH sebelum pemilihan - selama belum dipilih, pemicunya
    memang masih berbunyi "Pilih sekolah" / "Pilih kelas". Bila ternyata
    tulisannya tidak berganti, penantiannya habis tepat pada `batas_ms`, yaitu
    jeda tetap yang digantikannya: kasus terburuk tidak lebih lambat dari dulu.
    """
    mulai = time.monotonic()
    sisa = batas_ms
    while sisa > 0:
        try:
            if not ada_pemicu(halaman, teks_pemicu):
                break
        except Exception:
            pass
        halaman.wait_for_timeout(80)
        sisa -= 80
    lama = int((time.monotonic() - mulai) * 1000)
    JEJAK_WAKTU.append({"nama": nama or f"pemicu '{teks_pemicu}' berganti",
                        "ms": lama, "dulu": batas_ms, "siap": sisa > 0})
    return sisa > 0


def buka_dan_rekam(halaman: Page, teks_pemicu: str) -> list[str]:
    """
    Buka dropdown SEKALI lalu catat pilihan yang muncul. Dropdown dibiarkan
    terbuka � pilih dengan `klik_opsi_baru`, jangan lewat pemicunya lagi.

    Pemicu sengaja tidak disentuh untuk kedua kalinya: klik kedua justru
    menutup dropdown, dan begitu popup-nya terbentang, pemicunya tertutupi
    sehingga klik apa pun ke sana menggantung sampai kehabisan waktu.
    """
    pemicu = _pemicu_teks(halaman, teks_pemicu).first
    if not pemicu.count():
        return []
    try:
        halaman.evaluate(_TANDAI_LAMA)
        pemicu.click(timeout=6_000)
        halaman.wait_for_timeout(800)
        muncul = halaman.evaluate(_AMBIL_BARU)
    except Exception:
        tutup_dropdown(halaman)
        return []

    unik, lihat = [], set()
    for o in muncul:
        if o not in lihat:
            lihat.add(o)
            unik.append(o)
    return unik[:80]


def klik_opsi_baru(halaman: Page, teks: str) -> bool:
    """Klik salah satu opsi yang tadi ditandai oleh `buka_dan_rekam`."""
    kandidat = halaman.locator(
        f"xpath=//*[@data-ckg-opsi][normalize-space(.)={teks!r}]"
    )
    for i in range(min(kandidat.count(), 6)):
        satu = kandidat.nth(i)
        try:
            if satu.is_visible():
                satu.click(timeout=4_000)
                halaman.wait_for_timeout(500)
                return True
        except Exception:
            continue
    return False


# Tombol milik kerangka halaman � bukan opsi wilayah. Disaring supaya daftar
# pilihan lokasi yang terbaca benar-benar hanya nama wilayah.
_TOMBOL_KOP = {
    "CKG Umum", "CKG Sekolah", "Klaster 2", "Klaster 4", "Keluar", "Ganti Password",
    "Cetak QR Screening", "Daftar Baru", "Kembali", "Selanjutnya", "Daftarkan",
    "Cek NIK", "Simpan", "Batal", "Tutup",
}


def opsi_lokasi(halaman: Page) -> list[str]:
    """
    Daftar wilayah yang sedang tampil pada pemilih alamat domisili.

    Pemilih ini bertingkat (provinsi -> kota -> kecamatan -> kelurahan) dan
    isinya berganti tiap tingkat, jadi harus dibaca ulang setiap langkah.
    Nama wilayah selalu berupa <button>, sedangkan header abjad bukan �
    itulah cara membedakannya.

    DUPLIKAT SENGAJA DIPERTAHANKAN. Jejak tingkat sebelumnya tetap tampil
    sebagai tombol, jadi kelurahan "Koja" di kecamatan "Koja" menghasilkan DUA
    tombol bertulisan sama. Kalau dijadikan satu, pemanggil yang membuang jejak
    justru menghapus satu-satunya yang tersisa dan tak ada yang bisa diklik.
    """
    teks = halaman.evaluate(
        r"""() => [...document.querySelectorAll('button')]
              .filter(b => b.offsetParent !== null)
              .map(b => (b.innerText || '').replace(/\s+/g, ' ').trim())
              .filter(t => t && t.length < 60)"""
    )
    return [t for t in teks if t not in _TOMBOL_KOP and "Puskesmas" not in t]


def klik_lokasi(halaman: Page, teks: str, lewati: int = 0) -> bool:
    """
    Klik satu nama wilayah pada pemilih alamat.

    `lewati` = berapa tombol berteks sama yang harus DILEWATI lebih dulu.
    Perlu ada karena jejak tingkat sebelumnya tetap tampil sebagai tombol:
    saat memilih kelurahan "Koja" di kecamatan "Koja", tombol pertama adalah
    jejak kecamatannya, dan mengkliknya justru membatalkan pilihan.
    """
    kandidat = halaman.locator(f"xpath=//button[normalize-space(.)={teks!r}]")
    terlihat = 0
    for i in range(min(kandidat.count(), 8)):
        satu = kandidat.nth(i)
        try:
            if not satu.is_visible():
                continue
            if terlihat < lewati:
                terlihat += 1
                continue
            satu.click(timeout=4_000)
            halaman.wait_for_timeout(900)
            return True
        except Exception:
            continue
    return False


def cari_lokasi(halaman: Page, kata: str) -> bool:
    """
    Ketik pada kotak pencarian di dalam pemilih alamat, bila ada.

    Daftar kelurahan bisa panjang dan harus digulir; menyaringnya lebih dulu
    jauh lebih andal daripada mencari tombolnya satu per satu.
    """
    kotak = halaman.locator(
        "xpath=//input[not(@id='searchNik')][not(@id='detail-domisili')][not(@type='checkbox')]"
    )
    for i in range(min(kotak.count(), 5)):
        satu = kotak.nth(i)
        try:
            if satu.is_visible():
                satu.fill(kata)
                halaman.wait_for_timeout(900)
                return True
        except Exception:
            continue
    return False


def tunggu_kondisi(halaman: Page, js: str, batas_ms: int = 8_000,
                   jeda_ms: int = 150) -> bool:
    """
    Tunggu sampai sebuah ungkapan JS bernilai benar, maksimal `batas_ms`.

    Menggantikan jeda tetap. Jeda tetap harus dipasang selebar kasus terlambat
    supaya aman, jadi pada kasus normal � yang jauh lebih sering � waktunya
    terbuang percuma. Dengan 17-27 form per peserta, selisihnya menit.

    Mengembalikan False bila waktu habis, TANPA melempar galat: pemanggil tetap
    melanjutkan seperti dulu, jadi kegagalan penantian tidak pernah lebih buruk
    daripada jeda tetap.
    """
    sisa = batas_ms
    while sisa > 0:
        try:
            if halaman.evaluate(js):
                return True
        except Exception:
            pass          # halaman sedang berpindah � coba lagi
        halaman.wait_for_timeout(jeda_ms)
        sisa -= jeda_ms
    return False


# Ungkapan yang sering dipakai, dikumpulkan agar tidak tersebar sebagai teks.
ADA_SOAL = "() => document.querySelectorAll('.sd-question').length > 0"
TANPA_SOAL = "() => document.querySelectorAll('.sd-question').length === 0"
# Pemilih HARUS memuat kedua awalan: alur sekolah memakai `rowfrm` untuk
# Pemeriksaan Mandiri dan `row-FRM` untuk Pelayanan oleh Nakes, dan pemilih
# CSS peka huruf besar-kecil sehingga satu pola saja melewatkan separuhnya.
# Tombol kalender bertuliskan "<tanggal> <sisa kuota>", mis. "3 975" - bentuk
# yang tidak dipakai tombol lain mana pun. Inilah tanda kalender SUDAH terpasang.
# Dipakai sebagai syarat penantian sesudah "Mulai Pemeriksaan"; sebelum itu
# ditekan, di halaman detail tidak ada satu pun tombol berbentuk begini.
ADA_KALENDER_KUOTA = (
    r"""() => [...document.querySelectorAll('button')].some(b =>"""
    r""" b.offsetParent !== null &&"""
    r""" /^\d{1,2} \d+$/.test((b.innerText || '').replace(/\s+/g, ' ').trim()))""")

ADA_BARIS_LAYANAN = ("() => document.querySelectorAll("
                     "'[id^=\"rowfrm\"], [id^=\"row-FRM\"]').length > 0")
ADA_OPSI = ("() => [...document.querySelectorAll('[role=option]')]"
            ".some(o => o.offsetParent !== null)")


def klik_teks(halaman: Page, teks: str) -> bool:
    """
    Klik elemen mana pun yang tulisannya sama persis.

    Perlu ada di samping `klik_tombol` karena tidak semua yang bisa diklik
    berupa <button>: tab status pada halaman pelayanan, misalnya, hanya berupa
    elemen teks biasa sehingga pencarian lewat peran tombol tidak menemukannya.
    """
    kandidat = halaman.locator(
        "xpath=//*[self::div or self::li or self::span or self::a or self::p or self::button]"
        f"[normalize-space(text())={teks!r}]"
    )
    for i in range(min(kandidat.count(), 8)):
        satu = kandidat.nth(i)
        try:
            if satu.is_visible():
                satu.click(timeout=4_000)
                halaman.wait_for_timeout(600)
                return True
        except Exception:
            continue
    return False


KLIK_TAB_JS = r"""(mau) => {
  const rapi = s => (s || '').replace(/\s+/g, ' ').trim();
  const lolos = mau.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  // Angka di belakang label = jumlah antrean pada tab itu; boleh ada, boleh
  // tidak. Yang TIDAK boleh: teks lain, supaya kotak pembungkus yang memuat
  // ketiga tab sekaligus tidak ikut terpilih.
  const pola = new RegExp('^' + lolos + '\\s*\\d*$', 'i');
  const calon = [...document.querySelectorAll('div,li,span,a,p,button')]
    .filter(e => e.offsetParent !== null && pola.test(rapi(e.innerText)))
    .sort((a, b) => rapi(a.innerText).length - rapi(b.innerText).length);
  if (!calon.length) return '';
  calon[0].setAttribute('data-klik-tab', '1');
  return rapi(calon[0].innerText);
}"""


def klik_tab(halaman: Page, teks: str) -> str:
    """
    Klik tab status di halaman pelayanan - MESKIPUN ada angka di belakangnya.

    Kembalikan tulisan tab yang diklik ("Belum Pemeriksaan 1"), atau "" bila
    tabnya tidak ketemu.

    KENAPA TIDAK `klik_teks`. Fungsi itu mencocokkan tulisan PERSIS, sedangkan
    portal menempelkan jumlah antrean ke label tabnya begitu ada isinya:

        Belum Pemeriksaan 1   Sedang Pemeriksaan   Selesai Pemeriksaan

    Jadi justru tab YANG ADA ORANGNYA yang tidak pernah bisa diklik, sementara
    dua tab kosong di sebelahnya diklik dengan mulus. Akibatnya peserta yang
    baru dikonfirmasi hadir - yang memang duduk di "Belum Pemeriksaan" -
    dinyatakan "tak ada di ketiga tab", padahal barisnya lengkap dengan tombol
    "Mulai" ada di layar. Terjadi pada seluruh peserta skrining TBC (7 Sep):
    rekaman halamannya memuat baris itu utuh, dan tidak satu pun hasil jalan
    yang pernah berbunyi "tab: Belum Pemeriksaan".
    """
    try:
        tulisan = halaman.evaluate(KLIK_TAB_JS, teks)
    except Exception:
        return ""
    if not tulisan:
        return ""
    try:
        halaman.locator("[data-klik-tab='1']").first.click(timeout=4_000)
        halaman.wait_for_timeout(600)
        return tulisan
    except Exception:
        return ""
    finally:
        try:
            halaman.evaluate("() => document.querySelector('[data-klik-tab]')"
                             "?.removeAttribute('data-klik-tab')")
        except Exception:
            pass


def tutup_dropdown(halaman: Page) -> None:
    """
    Tutup dropdown yang menggantung terbuka supaya tidak menghalangi
    dropdown berikutnya. Escape saja tidak cukup pada dropdown portal ini,
    jadi ditambah klik di luar area popup.
    """
    try:
        halaman.keyboard.press("Escape")
        halaman.evaluate("() => document.body.click()")
        halaman.wait_for_timeout(400)
    except Exception:
        pass

# --------------------------------------------------------------- penantian
# Jejak lama menunggu tiap langkah. Dipakai untuk MEMBUKTIKAN percepatan, bukan
# menebaknya: tiap penantian mencatat berapa lama ia benar-benar menunggu dan
# berapa lama jeda tetap yang digantikannya.
# Per-UTAS, bukan satu daftar bersama: dengan beberapa pekerja berjalan
# bersamaan, satu daftar global membuat catatan waktu mereka saling tercampur
# dan ringkasannya jadi omong kosong.
_lokal = threading.local()


def _jejak() -> list[dict]:
    if not hasattr(_lokal, "waktu"):
        _lokal.waktu = []
    return _lokal.waktu


class _JejakWaktu:
    """Tetap terlihat seperti daftar biasa, supaya pemakaian lama tak berubah."""

    def append(self, x): _jejak().append(x)
    def clear(self): _jejak().clear()
    def __iter__(self): return iter(_jejak())
    def __len__(self): return len(_jejak())
    def __bool__(self): return bool(_jejak())
    def extend(self, x): _jejak().extend(x)
    def __eq__(self, lain): return list(_jejak()) == lain


JEJAK_WAKTU = _JejakWaktu()


def _teks_js(s: str) -> str:
    """Ubah teks Python jadi tulisan literal JS yang aman."""
    return json.dumps(s)


def js_ada_tombol(teks: str) -> str:
    return ("() => [...document.querySelectorAll('button')].some(b => "
            f"b.offsetParent !== null && (b.innerText || '').includes({_teks_js(teks)}))")


def js_tidak(js: str) -> str:
    """Kebalikan sebuah ungkapan `() => ...` - dipakai menunggu sesuatu HILANG."""
    return f"() => !(({js})())"


def js_ada_teks(teks: str) -> str:
    return f"() => ((document.body.innerText || '')).includes({_teks_js(teks)})"


def js_tombol_persis(teks: str) -> str:
    """
    Tombol dengan teks PERSIS itu, bukan yang memuatnya.

    `js_ada_tombol` mencocokkan sebagian teks, dan itu menipu bila nama tombol
    yang satu terkandung di nama tombol yang lain - "Hadir" ada di dalam
    "Konfirmasi Hadir". Penantian yang syaratnya sudah benar sebelum aksi
    dilakukan bukan penantian sama sekali.
    """
    return ("() => [...document.querySelectorAll('button')].some(b => "
            f"b.offsetParent !== null && (b.innerText || '').trim() === {_teks_js(teks)})")


def js_terlihat(pemilih: str) -> str:
    return (f"() => {{ const e = document.querySelector({_teks_js(pemilih)});"
            " return !!e && e.offsetParent !== null; }")


def js_terisi(pemilih: str) -> str:
    return (f"() => {{ const e = document.querySelector({_teks_js(pemilih)});"
            " return !!e && !!(e.value || '').trim(); }")


def js_atau(*bagian: str) -> str:
    """Gabung beberapa ungkapan: benar bila SALAH SATU benar."""
    isi = " || ".join(f"({b})()" for b in bagian)
    return f"() => {isi}"


def nama_akun(halaman: Page) -> str:
    """
    Nama akun yang sedang login, dibaca dari kepala halaman portal.

    Portal menaruhnya sebagai satu elemen berisi nama petugas dan puskesmasnya
    sekaligus - "David Puskesmas Koja" - dan itu terekam apa adanya di
    `struktur_wali.json`. Kata "Puskesmas" yang dipakai sebagai jangkar, bukan
    letaknya di halaman: tata letak berubah, tulisan itu tidak.

    Jangkarnya BUKAN "Puskesmas" saja: akun bisa milik Pustu, Klinik, atau
    Posyandu, dan pada percobaan pertama justru itu yang membuatnya pulang
    kosong. Letaknya di halaman tidak dipakai sama sekali - tata letak portal
    berubah-ubah, tulisan jenis fasilitasnya tidak.

    Kembalikan "" bila tak terbaca; nama akun cuma keterangan, jadi tidak boleh
    menghentikan apa pun bila gagal.
    """
    try:
        return (halaman.evaluate(
            r"""() => {
                 const rapi = s => (s || '').replace(/\s+/g, ' ').trim();
                 const ambil = (sel) => [...document.querySelectorAll(sel)]
                   .filter(e => e.offsetParent !== null)
                   .map(e => rapi(e.innerText))
                   .filter(t => /puskesmas|pustu|klinik|posyandu|poskesdes/i.test(t) && t.length > 8 && t.length < 60)
                   .sort((a, b) => a.length - b.length);
                 // Tombol/tautan akun DIDAHULUKAN. Portal membungkus nama
                 // petugas dan nama puskesmas dalam satu tombol ("David
                 // Puskesmas Koja"), sedangkan <div> di dalamnya hanya memuat
                 // separuhnya. Mengambil yang terpendek tanpa pandang bulu
                 // menghasilkan "Puskesmas Koja" saja - nama petugasnya hilang,
                 // padahal itulah yang membedakan satu pekerja dari pekerja lain.
                 const utuh = ambil('button, a')[0] || ambil('div, span, p')[0] || '';
                 // Nama PETUGASNYA saja. Portal menulis nama petugas dan nama
                 // fasilitasnya menyatu ("David Puskesmas Koja"); yang berguna
                 // untuk membedakan pekerja adalah bagian depannya - fasilitasnya
                 // sama untuk semua browser, jadi tidak membedakan apa pun.
                 const potong = utuh.split(
                   /\s*(?:puskesmas|pustu|klinik|posyandu|poskesdes)/i)[0].trim();
                 // Bila pemotongan menyisakan kosong, elemennya memang hanya
                 // memuat nama fasilitas - lebih baik tampilkan itu daripada
                 // tidak sama sekali.
                 return potong || utuh;
               }""") or "").strip()
    except Exception:
        return ""


def kepala_halaman(halaman: Page, batas: int = 6) -> list[str]:
    """
    Beberapa potong teks teratas halaman - bahan laporan saat nama akun gagal
    terbaca. Tanpa ini, "belum login" yang keliru hanya bisa ditebak sebabnya.
    """
    try:
        return halaman.evaluate(
            r"""(batas) => [...document.querySelectorAll('header, nav, button, a')]
                  .filter(e => e.offsetParent !== null)
                  .map(e => (e.innerText || '').replace(/\s+/g, ' ').trim())
                  .filter(t => t && t.length < 70)
                  .slice(0, batas)""", batas) or []
    except Exception:
        return []


def klik_salah_satu(halaman: Page, nama_nama, timeout: int = 6_000) -> str:
    """
    Klik tombol PERTAMA dari daftar yang benar-benar ADA di halaman.

    KENAPA BUKAN DICOBA SATU PER SATU. Pola lama `for nama in (...): klik_tombol
    (nama, timeout=3000)` membayar SELURUH tenggat untuk tiap nama yang tidak
    ada. Terukur pada data nyata: tombol simpan tanggal pemeriksaan bernama
    "Simpan" - pilihan KETIGA - sehingga 90 peserta masing-masing membuang tiga
    detik menunggu "Konfirmasi" lalu tiga detik lagi menunggu "Ya". Enam detik
    per peserta, hanya untuk mengetahui sesuatu yang bisa ditanyakan sekali.

    Di sini halaman ditanya SEKALI: dari sekian nama, mana yang ada? Yang tidak
    ada tidak memakan waktu sama sekali. Tenggatnya hanya dipakai menunggu
    salah satunya MUNCUL, bukan menunggu yang lain menyerah.

    Kembalikan nama tombol yang diklik, atau "" bila tak satu pun bisa diklik.
    """
    daftar = list(nama_nama)
    ada = tunggu_kondisi(halaman, js_atau(*[js_tombol_persis(n) for n in daftar]),
                         timeout, 80)
    if not ada:
        return ""
    hidup = halaman.evaluate(
        """(nama) => {
             const t = [...document.querySelectorAll('button')]
               .filter(b => b.offsetParent !== null && !b.disabled)
               .map(b => (b.innerText || '').trim());
             return nama.find(n => t.includes(n)) || '';
           }""", daftar)
    if not hidup:
        return ""
    return hidup if klik_tombol_persis(halaman, hidup, timeout=3_000) else ""


def js_dan(*bagian: str) -> str:
    """Gabung beberapa ungkapan: benar hanya bila SEMUANYA benar."""
    isi = " && ".join(f"({b})()" for b in bagian)
    return f"() => {isi}"


# Portal menampilkan tirai "Proses pencarian data.." sambil MENGGANTI isi tabel
# dengan baris rangka abu-abu. Rangka itu <tr> sungguhan: ia menambah jumlah
# baris dan mengubah tanda tabel, sehingga setiap penantian yang hanya melihat
# "tabelnya berubah" atau "ada lebih dari satu <tr>" pulang saat data BELUM ada.
# Barisnya lalu dibaca kosong dan pesertanya dinyatakan tidak ketemu.
# Bagian "Data Wali" tidak punya id sendiri, dan kolomnya pun tidak - jadi
# tidak ada selektor tetap yang bisa dihafal. Yang tetap adalah URUTAN: kolom
# wali selalu berada SESUDAH judul "Data Wali" di dalam dokumen. Itulah yang
# dipakai, supaya penamaan internal portal boleh berubah tanpa mematahkan alur.
JS_MEDAN_WALI = r"""() => {
  const judul = [...document.querySelectorAll('*')].find(e =>
      e.children.length === 0 && /^\s*(Isi\s+)?Data\s+Wali\s*$/i.test(e.textContent || ''));
  if (!judul) return null;
  const semua = [...document.querySelectorAll('input, select, textarea')];
  return semua
    .filter(e => (judul.compareDocumentPosition(e) & Node.DOCUMENT_POSITION_FOLLOWING)
                 && e.offsetParent !== null)
    .map(e => ({
      id: e.id || '', name: e.getAttribute('name') || '', jenis: e.type || '',
      placeholder: e.placeholder || '', nilai: (e.value || '').slice(0, 40),
      terkunci: !!(e.readOnly || e.disabled),
      // Nomor urut di antara SELURUH isian halaman. Wajib, karena kolom wali
      // memakai id yang SAMA dengan kolom peserta ("Nama Lengkap"): memilih
      // lewat id akan selalu mengenai milik peserta, dan kolom wali tetap
      // kosong sementara laporannya mengaku berhasil.
      urutan: semua.indexOf(e),
    }));
}"""

# Portal MENGISI SENDIRI data wali dari Kartu Keluarga begitu "Gunakan Data"
# dipakai - terbukti pada seorang balita: NIK, nama, tanggal lahir, dan
# jenis kelamin ibunya sudah terisi tanpa satu ketikan pun, dan kolomnya berubah
# jadi tampilan mati, bukan isian. Karena itu "sudah terisi" harus dikenali;
# memaksa mengetik di atasnya hanya merusak data yang sudah benar.
JS_WALI_TERISI = r"""() => {
  const badan = (document.body.innerText || '').replace(/\s+/g, ' ');
  const i = badan.search(/Data Wali/i);
  if (i < 0) return false;
  return /\d{16}/.test(badan.slice(i, i + 400));
}"""

JS_TIDAK_MEMUAT = ("() => !/Proses pencarian data|Memuat data|Sedang memuat/i"
                   ".test(document.body.innerText || '')")


def tunggu_siap(halaman: Page, js: str, batas_ms: int, nama: str = "",
                dasar_ms: int = 120) -> bool:
    """
    Ganti jeda tetap: tunggu sampai halaman BENAR-BENAR siap.

    `batas_ms` diisi dengan nilai jeda tetap yang digantikan, jadi kasus
    terburuk tidak pernah lebih lambat daripada sebelumnya - yang berubah hanya
    kasus normal, yang justru hampir selalu terjadi.

    `dasar_ms` adalah jeda terkecil yang tetap dijalani. Komponen Vue di portal
    ini kerap menaruh elemennya lebih dulu, baru mengikatkan penanganannya
    sepersekian detik kemudian; kembali pada milidetik nol membuat klik
    berikutnya mendarat di elemen yang belum hidup.
    """
    mulai = time.monotonic()
    if dasar_ms:
        halaman.wait_for_timeout(dasar_ms)
    sisa = max(batas_ms - dasar_ms, 400)
    siap = tunggu_kondisi(halaman, js, sisa, 100)
    lama = int((time.monotonic() - mulai) * 1000)
    JEJAK_WAKTU.append({"nama": nama or "?", "ms": lama, "dulu": batas_ms, "siap": siap})
    return siap


def ringkas_waktu(bersihkan: bool = True) -> dict:
    """Ringkasan penantian sejak terakhir dibersihkan."""
    if not JEJAK_WAKTU:
        return {"langkah": 0, "detik": 0.0, "dulu": 0.0, "hemat": 0.0, "gagal": []}
    kini = sum(x["ms"] for x in JEJAK_WAKTU)
    dulu = sum(x["dulu"] for x in JEJAK_WAKTU)
    gagal = [x["nama"] for x in JEJAK_WAKTU if not x["siap"]]
    lambat = sorted(JEJAK_WAKTU, key=lambda x: -x["ms"])[:3]
    hasil = {"langkah": len(JEJAK_WAKTU), "detik": round(kini / 1000, 1),
             "dulu": round(dulu / 1000, 1), "hemat": round((dulu - kini) / 1000, 1),
             "gagal": gagal,
             # Tiga penantian terlama, supaya titik lambat berikutnya ketahuan
             # dari ukuran - bukan dari mengira-ngira bagian mana yang berat.
             "lambat": [f"{x['nama']} {x['ms'] / 1000:.1f}s" for x in lambat if x["ms"] > 700]}
    if bersihkan:
        JEJAK_WAKTU.clear()
    return hasil

# Tanda isi tabel: jumlah baris + tulisan baris pertama. Dipakai untuk menunggu
# tabel BERUBAH, bukan sekadar "ada isinya".
# Kolom pencarian sesudah mode diganti ke NIK. Portal MENGGANTI elemennya saat
# mode berpindah, jadi yang ditunggu bukan sekian milidetik melainkan munculnya
# kolom yang memang menyebut NIK.
ADA_KOLOM_NIK = ("() => [...document.querySelectorAll('input')].some(e => "
                 "e.offsetParent !== null && /nik/i.test((e.placeholder || '') + ' ' "
                 "+ (e.id || '') + ' ' + (e.name || '')))")


def js_ada_kolom_cari() -> str:
    """
    Kolom pencarian daftar peserta sudah siap - apa pun mode pencariannya.

    Pasangan longgar dari ADA_KOLOM_NIK, dipakai saat yang dicari nomor tiket:
    di mode itu tidak ada satu pun kolom yang menyebut "nik", jadi menunggu
    ADA_KOLOM_NIK dijamin habis waktu sia-sia setiap kali.
    """
    return ("() => [...document.querySelectorAll('input')].some(e => "
            "e.offsetParent !== null && !e.disabled && "
            "/nik|tiket|cari|search/i.test((e.placeholder || '') + ' ' "
            "+ (e.id || '') + ' ' + (e.name || '')))")

JS_TANDA_TABEL = r"""() => {
  const b = [...document.querySelectorAll('tr')];
  const satu = b[1] ? (b[1].innerText || '').replace(/\s+/g, ' ').trim().slice(0, 70) : '';
  return b.length + '|' + satu;
}"""


def tanda_tabel(halaman: Page) -> str:
    try:
        return str(halaman.evaluate(JS_TANDA_TABEL))
    except Exception:
        return ""


def tunggu_beda(halaman: Page, sebelum: str, batas_ms: int, nama: str = "",
                dasar_ms: int = 150) -> bool:
    """
    Tunggu sampai isi tabel BERBEDA dari `sebelum`.

    Menunggu "ada tombol di tabel" tidak bisa dipakai sesudah pencarian: tabel
    yang belum tersaring pun sudah penuh tombol, jadi syaratnya benar seketika
    dan barisnya dibaca SEBELUM hasil pencarian masuk. Itu membuat peserta yang
    sebenarnya ada dinyatakan tidak ketemu.

    Kalau isinya memang tidak berubah - misalnya pencarian menghasilkan daftar
    yang sama - penantian berakhir pada batas waktu dan pemanggil tetap lanjut,
    persis seperti jeda tetap yang digantikannya.
    """
    import time as _t
    mulai = _t.monotonic()
    if dasar_ms:
        halaman.wait_for_timeout(dasar_ms)
    sisa = max(batas_ms - dasar_ms, 400)
    beda = tunggu_kondisi(
        halaman, f"() => {{ const f = {JS_TANDA_TABEL}; return f() !== {json.dumps(sebelum)}; }}",
        sisa, 100)
    lama = int((_t.monotonic() - mulai) * 1000)
    JEJAK_WAKTU.append({"nama": nama or "tabel berubah", "ms": lama,
                        "dulu": batas_ms, "siap": beda})
    return beda


def tunggu_tabel_tenang(halaman: Page, batas_ms: int, nama: str = "",
                        tenang_ms: int = 700) -> bool:
    """
    Tunggu sampai tabel benar-benar DIAM, bukan sekadar "sedang tidak memuat".

    KENAPA `JS_TIDAK_MEMUAT` SAJA TIDAK CUKUP. Ia menjawab keadaan SEKARANG,
    dan sesudah sebuah tab diklik ada jeda sebelum portal mulai mengambil
    datanya. Diperiksa di celah itu, jawabannya "tidak sedang memuat" - padahal
    pemuatannya belum dimulai. Barisnya lalu dibaca dari tabel tab SEBELUMNYA,
    muridnya tidak ketemu, dan "Memuat data.." baru muncul sesudahnya.

    Terjadi pada seorang murid (SD NEGERI LAGOA 09, 6 Sep): rekaman
    halamannya pada detik vonis berakhir dengan "Memuat data..", padahal
    sapuan tabnya baru saja menyatakan ketiga tab selesai memuat. Muridnya
    sendiri ada di tab Selesai Pemeriksaan.

    Syaratnya karena itu dua-duanya: TIDAK sedang memuat, DAN isi tabelnya
    tidak berubah lagi selama `tenang_ms`. Pemuatan yang baru mau mulai akan
    mengubah isinya, jadi syarat kedua menangkap yang tidak terlihat oleh
    syarat pertama.
    """
    import time as _t
    mulai = _t.monotonic()
    sisa = batas_ms
    tanda = None
    tenang = False
    while sisa > 0:
        if not tunggu_kondisi(halaman, JS_TIDAK_MEMUAT, sisa, 100):
            break
        sekarang = tanda_tabel(halaman)
        if tanda is not None and sekarang == tanda:
            tenang = True
            break
        tanda = sekarang
        halaman.wait_for_timeout(min(tenang_ms, max(sisa, 100)))
        sisa -= tenang_ms
    lama = int((_t.monotonic() - mulai) * 1000)
    JEJAK_WAKTU.append({"nama": nama or "tabel tenang", "ms": lama,
                        "dulu": batas_ms, "siap": tenang})
    return tenang


# BARIS PESERTA DICOCOKKAN PER KATA UTUH, DAN BARIS JUDUL TABEL TIDAK IKUT.
#
# `tr:has-text("BUDI")` memakai pencocokan SEBAGIAN tanpa peduli besar-kecil
# huruf, dan judul kolom tabel pelayanan berbunyi "Pemeriksaan MANDIRI".
# Jadi baris judul itulah yang terambil sebagai baris peserta BUDI
# (3172030507770000, perbaikan jiwa laki-laki, 13-14 Sep): statusnya "tak
# terbaca", ketiga tab tidak pernah diperiksa karena barisnya dikira sudah
# ketemu, tombol "Mulai" tentu tidak ada di judul kolom - dan hasilnya
# `gagal_mulai` yang sama persis di tiga jalan berturut-turut. Nama pendek
# lain punya jebakan serupa: "ANI" di "PELAYANAN", "EKA" di "PEMERIKSAAN".
#
# Tanda baca di antara kata tetap dilonggarkan, sebab portal menulis nama
# menurut Dukcapil: "M. ADI PUTRA" di CSV tercatat "M Adi Putra".
# Dicocokkan lewat `innerText` di dalam halaman, BUKAN `filter(has_text=...)`.
# `has_text` membaca teks sel yang MENEMPEL tanpa pemisah - baris "1 | Andi |
# Belum" terbaca "1AndiBelum" - sehingga batas kata tidak pernah ketemu dan
# nama yang jelas ada di layar dinyatakan tidak ada. Terbukti pada uji tiruan
# 14 Sep sebelum perbaikan ini dipasang. `innerText` memisahkan tiap sel dengan
# tab, jadi batas katanya nyata.
_JS_BARIS_BERNAMA = r"""(kata) => {
  const s = x => ' ' + (x || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim() + ' ';
  const mau = ' ' + kata.join(' ') + ' ';
  // Baris TERSEMBUNYI tidak ikut, dan baris BERTOMBOL didahulukan.
  //
  // Portal merender tabelnya lebih dari sekali - ada salinan yang tidak tampak
  // di layar, dan salinan itu tidak membawa tombol aksi. Terambil salah satu,
  // gejalanya persis seperti seorang peserta (18 Sep): barisnya jelas ada di
  // layar lengkap dengan tombol "Konfirmasi Hadir", tapi macro melaporkan
  // "tak ada tombol aksi di baris peserta".
  const tampak = t => t.offsetParent !== null || t.getClientRects().length > 0;
  const bertombol = [], polos = [];
  document.querySelectorAll('tr').forEach((t, i) => {
    if (t.querySelector('th') || t.closest('thead')) return;
    if (!s(t.innerText).includes(mau)) return;
    if (!tampak(t)) return;
    (t.querySelector('button') ? bertombol : polos).push(i);
  });
  return bertombol.concat(polos);
}"""


def baris_bernama(halaman: Page, teks: str) -> Locator:
    """
    Baris DATA tabel yang memuat `teks` sebagai kata utuh.

    Yang dikembalikan Locator biasa - `.count()`, `.first`, `.nth()` tetap
    berlaku - disusun dari nomor urut baris yang cocok saat dipanggil.
    """
    kata = [k.lower() for k in re.findall(r"[A-Za-z0-9]+", teks or "")]
    semua = halaman.locator("tr")
    nomor = halaman.evaluate(_JS_BARIS_BERNAMA, kata) if kata else []
    if not nomor:
        return halaman.locator("tr[data-baris-bernama-tak-ada]")   # kosong
    hasil = semua.nth(nomor[0])
    for i in nomor[1:]:
        hasil = hasil.or_(semua.nth(i))
    return hasil


def js_ada_nama(nama: str) -> str:
    """
    Benar bila ada baris tabel memuat nama itu.

    Tanda baca dan besar-kecil huruf diabaikan: "M. ADI PUTRA PRATAMA" di CSV
    tercatat "M Adi Putra Pratama" di portal. Inilah penantian yang benar
    sesudah mencari orang - bukan "tabelnya berubah", sebab tabel yang berubah
    jadi kosong pun sudah dianggap berubah.
    """
    # Per kata utuh dan tanpa baris judul - alasannya di `baris_bernama`. Tanpa
    # itu penantian ini langsung dianggap selesai oleh judul "Pemeriksaan
    # Mandiri" untuk peserta bernama BUDI, sebelum hasil pencariannya tampil.
    return ("(() => { const s = x => ' ' + (x || '').toLowerCase()"
            ".replace(/[^a-z0-9]+/g, ' ').trim() + ' ';"
            f" const mau = s({_teks_js(nama)});"
            " return () => mau.trim() !== '' && [...document.querySelectorAll('tr')]"
            "   .some(t => !t.querySelector('th') && !t.closest('thead')"
            "              && s(t.innerText).includes(mau)); })()")


def js_tiket() -> str:
    """Benar bila nomor tiket sudah tampil di halaman."""
    return (r"() => /No\.?\s*Tiket\s*:?\s*[A-Za-z0-9]+-[A-Za-z0-9]+/i"
            ".test(document.body.innerText || '')")

# Portal menyatakan hal ini dengan beberapa awalan berbeda:
#     "Peserta sudah menerima layanan"
#     "Individu sudah menerima layanan"
# Polanya sengaja longgar - kata di depannya tidak dipedulikan, "pelayanan"
# maupun "layanan" sama-sama cocok, spasi ganda dan besar-kecil huruf diabaikan.
#
# Yang membuat dua peserta dilaporkan "gagal" BUKAN tulisannya,
# melainkan TEMPATNYA: popup ini tidak pernah diperiksa di titik-titik
# kegagalan halaman 1 dan halaman 2. Kalimatnya cocok sejak dulu; tidak ada
# yang menanyakannya di sana. Itulah yang diperbaiki - lihat jaring pengaman
# di `pendaftaran.daftar_peserta`.
POLA_SUDAH_DILAYANI = re.compile(r"sudah\s+menerima\s+(?:pe)?layanan", re.I)
SUDAH_DILAYANI_JS = (r"() => /sudah\s+menerima\s+(?:pe)?layanan/i"
                     ".test(document.body.innerText || '')")


# Popup KEDUA, dan artinya BERBEDA:
#
#     "Individu sudah terdaftar"
#     "<nama> sudah terdaftar dengan detail: Puskesmas pengampu / Tanggal
#      pemeriksaan / Layanan"
#
# "sudah menerima layanan" berarti pemeriksaannya sudah jalan. "sudah
# terdaftar" hanya berarti pendaftarannya ada - BELUM tentu sudah dikonfirmasi
# hadir, dan halaman pendaftaran tidak bisa membedakannya. Jadi ini bukan
# kegagalan: langkah yang benar adalah meneruskan ke pencarian NIK untuk
# konfirmasi hadir.
#
# Polanya menuntut kata "sudah" di tengah supaya TIDAK mengenai judul tabel
# "Data Individu Terdaftar" yang selalu ada di halaman itu. Diuji pada halaman
# aslinya: cocok saat popup terbuka, tidak cocok saat popup ditutup.
POLA_SUDAH_TERDAFTAR = re.compile(
    r"(?:individu|peserta)\s+sudah\s+terdaftar"
    r"|sudah\s+terdaftar\s+dengan\s+detail", re.I)
SUDAH_TERDAFTAR_JS = (r"() => /(?:individu|peserta)\s+sudah\s+terdaftar"
                      r"|sudah\s+terdaftar\s+dengan\s+detail/i"
                      ".test(document.body.innerText || '')")


# Portal menolak data dengan DUA bunyi, dan yang kedua baru ketahuan 2 Sep:
#
#     "Data peserta tidak valid"
#     "Data peserta atau wali tidak valid"     <- muncul bila data wali ikut
#
# Kode lama mencocokkan tulisan PERSIS "Data peserta tidak valid", jadi bunyi
# kedua tidak pernah kena. Akibatnya berantai dan menyesatkan: penolakan tidak
# terdeteksi, alurnya menerobos ke halaman 2 yang tidak pernah terbuka, lalu
# peserta dicatat `gagal` - bukan `tidak_valid`. Dan karena percobaan ulang
# dengan "Cek NIK" hanya dipicu oleh `tidak_valid`, jalur penyelamat itu pun
# tidak pernah jalan.
#
# Polanya dibuat menerima sisipan apa pun di antara "data" dan "tidak valid",
# supaya bunyi ketiga - kalau nanti ada - ikut tertangkap.
#
# Bunyi ketiga memang datang (14 Okt 2026), dan TIDAK memuat "tidak valid":
#
#     "Data Tidak Ditemukan, NIK tidak terdapat di database Kependudukan
#      Silakan perbaiki data yang dimasukkan. Pastikan data sudah benar dan
#      sesuai KTP/KK."                                   [Periksa Kembali]
#
# Tanpa dikenali, penolakan itu tercatat "error" - bukan tidak_valid - dan
# pesertanya diulang-ulang percuma. Kalimat "Silakan perbaiki data yang
# dimasukkan" ada di SEMUA popup penolakan yang kita kenal, jadi ikut
# dijadikan penanda supaya bunyi berikutnya pun tertangkap.
_TIDAK_VALID = (r"data\s+(?:peserta|wali|individu)[^.\n]{0,40}?tidak\s+valid"
                r"|NIK\s+tidak\s+terdapat\s+di\s+database"
                r"|data\s+tidak\s+ditemukan,\s*NIK"
                r"|silakan\s+perbaiki\s+data\s+yang\s+dimasukkan")
POLA_TIDAK_VALID = re.compile(_TIDAK_VALID, re.I)
TIDAK_VALID_JS = (r"() => /" + _TIDAK_VALID.replace("/", r"\/")
                  + r"/i.test(document.body.innerText || '')")


def pesan_penolakan(halaman: Page) -> str:
    """
    Kalimat penolakan portal APA ADANYA, untuk disimpan di keterangan.

    Selama ini yang tercatat cuma "data peserta ditolak portal" - fakta bahwa
    ada penolakan, bukan sebabnya. Tiga murid SDN Lagoa 01 (murid A,
    murid B, murid C) ditolak berulang kali
    sejak 6 Sep PADAHAL Cek NIK-nya berhasil dan portal menawarkan "Gunakan
    Data" - dan tidak ada satu pun catatan yang bisa menjelaskan kenapa, sebab
    bunyi popupnya tidak pernah disimpan.

    Yang diambil kalimat di sekitar "tidak valid" beserta kelanjutannya,
    dirapikan spasinya dan dipotong supaya keterangan tidak membengkak.
    """
    try:
        teks = halaman.evaluate("() => document.body.innerText || ''")
    except Exception:
        return ""
    m = POLA_TIDAK_VALID.search(teks)
    if not m:
        return ""
    awal = teks.rfind("\n", 0, m.start()) + 1
    potong = " ".join(teks[awal:m.end() + 220].split())
    # Tombol-tombol modal ikut terbaca; dibuang supaya yang tersisa kalimatnya.
    for tombol in ("Periksa Kembali", "Tutup", "Batal", "Lanjutkan", "Kembali"):
        potong = potong.replace(tombol, " ")
    return " ".join(potong.split())[:200]


def data_tidak_valid(halaman: Page) -> bool:
    """Benar bila portal menyatakan data peserta / wali tidak valid."""
    try:
        return bool(POLA_TIDAK_VALID.search(
            halaman.evaluate("() => document.body.innerText || ''")))
    except Exception:
        return False


def sudah_terdaftar(halaman: Page) -> bool:
    """Benar bila portal menyatakan peserta SUDAH TERDAFTAR (bukan sudah dilayani)."""
    try:
        return bool(POLA_SUDAH_TERDAFTAR.search(
            halaman.evaluate("() => document.body.innerText || ''")))
    except Exception:
        return False


# Popup "Individu sudah menerima layanan" MENYEBUTKAN SELURUH RINCIAN
# pemeriksaan yang sudah terjadi - bukan cuma layanannya:
#
#     Individu sudah menerima layanan
#     Budi Santoso telah selesai diperiksa dengan detail
#     Puskesmas pemeriksa:  BANJARAN
#     Sekolah:              MIS PUI GENTENG 2      <- sekolah LAIN
#     Kelas:                Kelas 1                <- kelas LAIN
#     Tanggal pemeriksaan:  29 Apr 2026
#     Layanan:              CKG Sekolah
#
# Dulu hanya baris "Layanan:" yang dibaca, dan itu membuang keterangan yang
# paling menjelaskan: murid yang di CSV tertulis MIS AL IKHWAN / Kelas 2
# ternyata sudah diperiksa di MIS PUI GENTENG 2 / Kelas 1 oleh puskesmas lain.
# Tanpa rincian ini ia dicari di sekolah+kelas yang salah, tidak ketemu di mana
# pun, lalu divonis `tidak_ditemukan` - padahal pemeriksaannya sudah selesai.
#
# Dibaca DARI DALAM KOTAK POPUP, bukan dari seluruh halaman, dan BARIS DEMI
# BARIS, bukan dengan regex bebas. Dua-duanya sudah terbukti perlu:
#   * "CKG Umum" juga tertulis di menu samping - dua kali sehalaman;
#   * regex bebas untuk 'Layanan:' mengenai JUDUL POPUPNYA SENDIRI
#     ("Individu sudah menerima layanan") dan mengembalikan nama peserta.
# Diuji langsung di halaman portal, bukan dikira-kira.
RINCIAN_POPUP_JS = r"""() => {
  const kotak = [...document.querySelectorAll('div,section,dialog')]
    .filter(e => e.offsetParent !== null
              && /sudah menerima layanan/i.test(e.innerText || '')
              && /puskesmas pemeriksa/i.test(e.innerText || ''))
    .sort((a, b) => (a.innerText || '').length - (b.innerText || '').length)[0];
  if (!kotak) return {};
  const baris = (kotak.innerText || '').split('\n').map(s => s.trim()).filter(Boolean);
  const hasil = {};
  for (let i = 0; i < baris.length; i++) {
    // Label dan nilainya duduk di dua <div> sebaris, jadi innerText memisahnya
    // dengan baris baru. Bentuk sebaris ("Layanan: CKG Umum") tetap diterima
    // supaya perubahan tata letak portal tidak mematikan pembacaan ini.
    const m = baris[i].match(/^([A-Za-z ]{3,30})\s*:\s*(.*)$/);
    if (!m) continue;
    const kunci = m[1].trim().toLowerCase();
    const nilai = m[2].trim() || (baris[i + 1] || '').trim();
    if (nilai && !/:$/.test(nilai)) hasil[kunci] = nilai;
  }
  return hasil;
}"""


# Modal pemilih portal ("Pilih jenjang pendidikan", "Pilih sekolah", ...) yang
# TERBUKA TAPI KOSONG - kerusakan portal yang berulang.
#
# KENAPA TIDAK CUKUP MENGHITUNG `opsi_lokasi`. Fungsi itu memindai
# `.cursor-pointer` SE-HALAMAN, dan yang ikut terjaring justru menu samping:
# saat daftar kelas benar-benar kosong, yang terbaca "tersedia" adalah
# ['Tatalaksana'] - satu item menu. Jadi "kosong" tidak pernah terdeteksi
# sebagai kosong. Terbukti pada dua murid (2 Sep, 15:34).
#
# Yang benar: lihat KE DALAM kotak modalnya. Saat kosong, satu-satunya simpul
# berteks di dalamnya adalah JUDUL modal itu sendiri - diperiksa langsung di
# portal: 1 daun, isinya "Pilih jenjang pendidikan".
MODAL_KOSONG_JS = r"""() => {
  const rapi = s => (s || '').replace(/\s+/g, ' ').trim();
  const modal = [...document.querySelectorAll('.modal-content')]
    .filter(e => e.offsetParent !== null)
    .sort((a, b) => (a.innerText || '').length - (b.innerText || '').length)[0];
  if (!modal) return false;
  // Tombol silang tidak dihitung: di portal ia berisi <svg> tanpa teks, tapi
  // di tempat lain bisa bertuliskan "x" - dan satu huruf itu cukup membuat
  // modal kosong terbaca "berisi".
  const daun = [...modal.querySelectorAll('*')]
    .filter(e => e.children.length === 0 && rapi(e.innerText)
              && !e.closest('button'));
  return daun.length <= 1;
}"""

TUTUP_MODAL_JS = r"""() => {
  const modal = [...document.querySelectorAll('.modal-content')]
    .filter(e => e.offsetParent !== null)
    .sort((a, b) => (a.innerText || '').length - (b.innerText || '').length)[0];
  if (!modal) return false;
  const x = modal.querySelector('button');
  if (!x) return false;
  x.click();
  return true;
}"""


def modal_daftar_kosong(halaman: Page) -> bool:
    """Benar bila modal pemilih sedang terbuka TANPA satu pilihan pun."""
    try:
        return bool(halaman.evaluate(MODAL_KOSONG_JS))
    except Exception:
        return False


def tutup_modal(halaman: Page) -> bool:
    """
    Tutup modal pemilih lewat tombol silangnya.

    `tutup_dropdown` mengklik body, dan itu TIDAK cukup di sini: modal ini
    duduk di atas lapisan `fixed ... z-9000` yang menutupi seluruh halaman,
    termasuk tombol "Selanjutnya". Selama ia terbuka, langkah berikutnya
    dilaporkan "tak bisa diklik" - padahal tombolnya baik-baik saja.
    """
    try:
        ok = bool(halaman.evaluate(TUTUP_MODAL_JS))
    except Exception:
        ok = False
    if not ok:
        return False
    # DIPERIKSA, BUKAN DIANDAIKAN: klik yang diterima belum tentu menutup
    # apa pun, dan modal yang mengira dirinya tertutup justru yang membuat
    # tombol berikutnya "tak bisa diklik".
    halaman.wait_for_timeout(400)
    return not bool(halaman.evaluate(
        "() => !!document.querySelector('.modal-content')?.offsetParent"))


PUSKESMAS_KITA_JS = r"""() => {
  const rapi = s => (s || '').replace(/\s+/g, ' ').trim();
  // Nama puskesmas yang sedang login tertulis di kepala halaman, di bawah nama
  // petugas. Diambil dari simpul DAUN supaya yang terbaca hanya namanya, bukan
  // seluruh blok menu - dan "Puskesmas pemeriksa:" milik popup dibuang, sebab
  // itu label, bukan nama.
  const calon = [...document.querySelectorAll('*')]
    .filter(e => e.children.length === 0
              && /^Puskesmas\s+\S/i.test(rapi(e.innerText))
              && !/:$/.test(rapi(e.innerText)))
    .map(e => rapi(e.innerText));
  return calon.length ? calon[0] : '';
}"""


def _sederhana_puskesmas(nama: str) -> str:
    """'Puskesmas Koja', 'KOJA', 'PKM Koja' -> 'koja'. Untuk dibandingkan."""
    s = re.sub(r"\b(puskesmas|pkm|kecamatan|kelurahan)\b", " ", (nama or "").lower())
    return re.sub(r"[^a-z0-9]", "", s)


def pendaftaran_gagal(halaman: Page) -> str:
    """
    Kalimat popup "Pendaftaran Gagal" bila sedang tampil; '' bila tidak.

    Popup ini jawaban portal atas "Daftarkan" yang GAGAL DISIMPAN - bunyinya
    "Data pendaftaran gagal disimpan. Silakan coba beberapa saat lagi." dengan
    satu tombol "Tutup". Macro dulu tidak mengenalnya: ia terus mencari nomor
    tiket sampai 45 detik habis, lalu mencatat "tiket tidak terbaca" - dan
    begitu tiga kali berturut pada seorang peserta (30 Sep). Sebab yang
    sebenarnya tidak pernah tertulis di hasilnya.
    """
    try:
        teks = halaman.evaluate("() => document.body.innerText || ''")
    except Exception:
        return ""
    m = re.search(r"Pendaftaran Gagal\s*([^\n]*)", teks)
    if not m:
        return ""
    return " ".join(("Pendaftaran Gagal. " + m.group(1)).split())[:160]


def puskesmas_kita(halaman: Page) -> str:
    """Nama puskesmas yang sedang login, dibaca dari kepala halaman portal."""
    try:
        return (halaman.evaluate(PUSKESMAS_KITA_JS) or "").strip()
    except Exception:
        return ""


def puskesmas_lain(halaman: Page, pemeriksa: str) -> bool:
    """
    Benar bila `pemeriksa` JELAS bukan puskesmas kita.

    Kalau salah satu namanya tidak terbaca, jawabannya False - bukan True.
    Menuduh "puskesmas lain" hanya karena nama kita sendiri gagal dibaca akan
    menghentikan peserta yang sebenarnya milik kita sendiri.
    """
    kita = _sederhana_puskesmas(puskesmas_kita(halaman))
    dia = _sederhana_puskesmas(pemeriksa)
    return bool(kita and dia and kita != dia)


def rincian_popup(halaman: Page) -> dict:
    """
    Seluruh rincian yang disebut popup "sudah menerima layanan".

    Kuncinya huruf kecil persis seperti tulisan portal: "puskesmas pemeriksa",
    "sekolah", "kelas", "tanggal pemeriksaan", "layanan". Yang tidak disebut
    popup memang tidak ada kuncinya - jangan diandaikan selalu lengkap.
    """
    try:
        return halaman.evaluate(RINCIAN_POPUP_JS) or {}
    except Exception:
        return {}


def layanan_pada_popup(halaman: Page) -> str:
    """Nama layanan yang disebut popup "sudah menerima layanan" ("CKG Umum")."""
    return (rincian_popup(halaman).get("layanan") or "").strip()


def sudah_dilayani(halaman: Page) -> bool:
    """Benar bila portal menyatakan peserta sudah menerima (pe)layanan."""
    try:
        return bool(POLA_SUDAH_DILAYANI.search(
            halaman.evaluate("() => document.body.innerText || ''")))
    except Exception:
        return False
