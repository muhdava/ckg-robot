"""
Alur CKG SEKOLAH: pendaftaran murid + konfirmasi hadir.

Berbeda cukup jauh dari alur individu (`pendaftaran.py`), dan tiap perbedaan di
bawah ini sudah DIPASTIKAN dari portal, bukan disalin dari catatan macro:

  1. Rute `/ckg-pendaftaran-anak-sekolah`, dengan filter Sekolah + Kelas di atas
     daftar. Tanpa filter itu, tabel murid tidak menampilkan apa pun.
  2. Halaman 1 TIDAK punya kalender tanggal pemeriksaan - jadi tidak ada urusan
     kuota maupun popup "Kuota Pemeriksaan Habis".
  3. Checkbox `noWali` sudah tercentang dari sananya.
  4. Halaman 2 memuat Nama Sekolah + Jenjang Pendidikan, dan alamat domisili
     diisi lewat checkbox "sama dengan alamat sekolah" - CSV sekolah memang
     tidak punya kolom provinsi/kota/kecamatan/kelurahan.
  5. Tombol "Selanjutnya" halaman 2 BUKAN <button>, melainkan <div> yang
     memakai kelas `bg-disabled` saat mati. `klik_tombol()` tidak akan pernah
     menemukannya; yang cocok `portal.klik_teks()`.
  6. Sesudah halaman 2, tiket LANGSUNG terbit - tidak ada langkah
     "Daftarkan dengan NIK".
"""
from __future__ import annotations

import re

import config
import layanan
import pendaftaran
import portal
from browser import simpan_gambar
from pendaftaran import HasilDaftar, _rekam, pekerjaan_untuk, status_nikah_untuk
from peserta import Peserta


def _mati(halaman, teks: str) -> bool:
    """
    Apakah tombol berteks itu sedang MATI.

    Portal menandainya dengan kelas `bg-disabled`, dan itu jauh lebih baik
    daripada menunggu klik gagal: kita bisa langsung melaporkan bahwa ada
    kolom wajib yang belum terisi.
    """
    return bool(halaman.evaluate(
        """(t) => {
             const rapi = s => (s || '').replace(/\\s+/g, ' ').trim();
             return [...document.querySelectorAll('div, button')]
               .filter(e => e.offsetParent !== null && rapi(e.innerText) === t)
               .some(e => /bg-disabled/.test(String(e.className || '')));
           }""", teks))


def _isian_kosong(halaman) -> dict:
    """
    Kolom wajib yang masih kosong — bahan laporan saat tombol mati.

    Filter Sekolah + Kelas di atas daftar murid DIKECUALIKAN: saat formulir
    pendaftaran terbuka keduanya memang kosong dan tidak ada hubungannya
    dengan tombol yang mati, tapi kehadirannya di laporan sempat membuat
    kolom yang benar-benar bermasalah tenggelam. Kolom sekolah pada formulir
    tulisannya berbeda ("Pilih nama sekolah", "Pilih jenjang pendidikan"),
    jadi keduanya tetap terlaporkan.
    """
    return halaman.evaluate(
        """() => {
             const rapi = s => (s || '').replace(/\\s+/g, ' ').trim();
             const vis = e => e && e.offsetParent !== null;
             const saring = ['pilih sekolah', 'pilih kelas'];
             return {
               dropdown: [...document.querySelectorAll('div')]
                 .filter(e => { const c = String(e.className || '');
                    return vis(e) && c.includes('cursor-pointer')
                        && c.includes('2.9rem') && /^Pilih /i.test(rapi(e.innerText))
                        && !saring.includes(rapi(e.innerText).toLowerCase()); })
                 .map(e => rapi(e.innerText).slice(0, 32)),
               isian: [...document.querySelectorAll('input, textarea')]
                 .filter(e => vis(e) && e.type !== 'checkbox' && !(e.value || '').trim()
                              && e.id !== 'searchNik' && e.id !== 'rt' && e.id !== 'rw')
                 .map(e => e.id || e.getAttribute('name') || '?'),
             };
           }""")


# ------------------------------------------------------------- halaman 2
def isi_halaman2(halaman, orang: Peserta, hasil: dict, jejak: list) -> None:
    """Isi data pendukung: status nikah, disabilitas, sekolah, kelas, alamat."""
    param = orang.parameter

    if portal.ada_pemicu(halaman, "Pilih status pernikahan"):
        nikah = status_nikah_untuk(orang)
        hasil["keterangan"] += (f" | status nikah: {nikah}"
                                if portal.pilih_dropdown_teks(
                                    halaman, "Pilih status pernikahan", nikah)
                                else f" | status nikah GAGAL ({nikah})")
    else:
        hasil["keterangan"] += " | status nikah: sudah terisi"

    if portal.ada_pemicu(halaman, "Pilih penyandang disabilitas"):
        nilai = (param.get("disabilitas") or "Tidak").strip()
        # Dicocokkan lewat pola, bukan tulisan utuh: portal memakai "Tidak
        # memiliki disabilitas" / "Memiliki disablilitas" - beda jauh dari
        # nilai di CSV, dan yang kedua salah ketik di portalnya sendiri.
        pola = (r"^\s*(memiliki|penyandang|ya)\b" if nilai.lower().startswith("ya")
                else r"tidak|non|bukan")
        ok, tersedia = _pilih_berkotak_pola(
            halaman, "Pilih penyandang disabilitas", pola)
        hasil["keterangan"] += (f" | disabilitas: {nilai}" if ok
                                else f" | disabilitas GAGAL ({nilai}); "
                                     f"tersedia: {tersedia[:6]}")
    else:
        hasil["keterangan"] += " | disabilitas: sudah terisi"

    # Pekerjaan biasanya sudah "Pelajar" dari portal; hanya diisi bila kosong.
    if portal.ada_pemicu(halaman, "Pilih pekerjaan"):
        _pilih_berkotak_cari(halaman, "Pilih pekerjaan", pekerjaan_untuk(orang))

    # --- Nama Sekolah & Kelas: SELALU diisi ulang ---
    # Murid yang datanya sudah ada di sistem datang dengan keduanya terisi data
    # TAHUN LALU. Banyak yang pindah sekolah atau naik kelas, jadi membiarkan
    # yang sudah terisi berarti mendaftarkan mereka di kelas yang salah.
    for label, kunci in (("Nama Sekolah", "sekolah"), ("Jenjang Pendidikan", "kelas")):
        nilai = (param.get(kunci) or "").strip()
        if not nilai:
            continue
        terpilih, sebab = _isi_dropdown_label(halaman, label, nilai)
        hasil["keterangan"] += (f" | {kunci}: {terpilih}" if terpilih
                                else f" | {kunci} GAGAL ({nilai}) - {sebab}")
        if not terpilih and sebab.startswith("DAFTAR KOSONG"):
            hasil["daftar_kosong"] = kunci

    # --- Alamat domisili: disalin dari alamat sekolah ---
    isi_alamat(halaman, orang, hasil)

    halaman.wait_for_timeout(600)
    _rekam(halaman, jejak, "5c_halaman2_sekolah")


_JS_TANDAI_OPSI = r"""(nilai) => {
     const rapi = s => (s || '').replace(/\s+/g, ' ').trim();
     const mau = rapi(nilai).toLowerCase();
     const lama = document.getElementById('ckg_opsi');
     if (lama) lama.removeAttribute('id');

     // Pemicu dropdown dan sel tabel dibuang lebih dulu: keduanya bisa
     // bertuliskan nama sekolah yang sama persis dengan opsinya - pemicunya
     // karena sudah terisi, sel tabel karena daftar murid memuat kolom
     // Sekolah - dan mengklik salah satunya tidak memilih apa pun.
     const pemicu = e => { const c = String(e.className || '');
         return c.includes('cursor-pointer') && c.includes('2.9rem'); };
     const daun = [...document.querySelectorAll('div, li, span, p, button')]
         .filter(e => e.offsetParent !== null && e.children.length === 0
                      && !pemicu(e) && !e.closest('[class*="2.9rem"]')
                      && !e.closest('table'));

     const persis = daun.filter(e => rapi(e.innerText).toLowerCase() === mau);
     const mirip  = daun.filter(e => {
         const t = rapi(e.innerText).toLowerCase();
         return t.length >= 6 && (t.includes(mau) || mau.includes(t)); });
     const calon = persis.length ? persis : mirip;
     if (!calon.length) return '';

     // Daftar opsi selalu digambar sebagai lapisan melayang. Bila ada yang
     // begitu, itu yang dipakai - sisanya cuma tulisan biasa di halaman.
     const melayang = e => {
       for (let n = e, i = 0; n && i < 8; n = n.parentElement, i++) {
         const p = getComputedStyle(n).position;
         if (p === 'absolute' || p === 'fixed') return true;
       }
       return false;
     };
     const pilih = calon.find(melayang) || calon[calon.length - 1];
     pilih.scrollIntoView({block: 'center'});
     pilih.setAttribute('id', 'ckg_opsi');
     return rapi(pilih.innerText);
   }"""


def _pilih_opsi(halaman, nilai: str) -> str:
    """
    Klik opsi bertuliskan `nilai` pada dropdown yang SEDANG TERBUKA.

    Opsi dropdown portal ini tidak seragam: pemilih alamat memakai <button>,
    sedangkan filter Sekolah/Kelas memakai <div> polos tanpa kelas sama sekali.
    Karena itu opsi dicari sebagai elemen-daun mana pun yang teksnya cocok,
    lalu ditandai tepat sebelum diklik - bukan jauh sebelumnya.

    Mengembalikan teks opsi yang diklik, atau "" bila tak ada yang cocok.
    """
    teks = halaman.evaluate(_JS_TANDAI_OPSI, nilai)
    if not teks:
        return ""
    try:
        halaman.locator("#ckg_opsi").click(timeout=4_000)
    except Exception:
        return ""
    halaman.wait_for_timeout(700)
    return teks


def _pilih_berkotak_cari(halaman, teks_pemicu: str, nilai: str) -> tuple[bool, list[str]]:
    """
    Buka dropdown lalu pilih isinya - mengetik hanya bila perlu.

    Kembalikan (berhasil, daftar_opsi). Daftar opsinya ikut dikembalikan supaya
    kegagalan bisa dilaporkan apa adanya: "tersedia: [...]" langsung menunjukkan
    tulisan yang portal pakai, tanpa perlu menebak-nebak lagi.

    DIPASTIKAN DARI PORTAL, dan dua-duanya sempat membuat filter sekolah gagal:

      * Seluruh daftar sekolah (137 baris) sudah ada di DOM begitu dropdown
        terbuka, jadi mengetik sama sekali tidak wajib.
      * Mengetik justru MEMBANGUN ULANG daftarnya: penanda yang dipasang
        sebelum mengetik hilang semua (137 -> 0), sehingga opsi hasil saringan
        tidak bisa diklik lewat penanda itu.
      * Kata cari harus lebih pendek dari teks yang tampil. Nama lengkap
        "SMKS TANJUNG PRIOK 2 JAKARTA" tidak menemukan apa pun, sedangkan
        "SMKS TANJUNG PRIOK 2" menemukannya - kata terakhir cuma ada di
        tampilan, tidak di data yang dicari.
    """
    tersedia = portal.buka_dan_rekam(halaman, teks_pemicu)
    if not tersedia:
        return False, []

    if _pilih_opsi(halaman, nilai):           # daftarnya utuh - langsung pilih
        return True, tersedia

    # Daftar terlalu panjang / dipangkas server: saring, kata demi kata dari
    # belakang, dan pilih dari daftar yang BARU dibangun.
    kata = nilai.split()
    for n in range(len(kata), 0, -1):
        if not portal.cari_lokasi(halaman, " ".join(kata[:n])):
            break                              # dropdown ini tanpa kotak cari
        halaman.wait_for_timeout(700)
        if _pilih_opsi(halaman, nilai):
            return True, tersedia

    portal.tutup_dropdown(halaman)
    return False, tersedia


def _pilih_berkotak_pola(halaman, teks_pemicu: str, pola: str) -> tuple[bool, list[str]]:
    """
    Pilih opsi yang COCOK DENGAN POLA, bukan yang tulisannya harus sama persis.

    Ada dropdown yang tulisannya tidak bisa ditebak dari nilai di CSV. Contoh
    nyatanya disabilitas: pilihannya "Tidak memiliki disabilitas" dan "Memiliki
    disablilitas" - lengkap dengan salah ketik dari portalnya - sehingga
    mencocokkan dengan "Non disabilitas" selalu gagal, dropdown terbuka lalu
    tidak terisi, dan tombol Selanjutnya tetap mati.
    """
    tersedia = portal.buka_dan_rekam(halaman, teks_pemicu)
    if not tersedia:
        return False, []
    cocok = next((o for o in tersedia if re.search(pola, o, re.I)), "")
    if not cocok:
        portal.tutup_dropdown(halaman)
        return False, tersedia
    return bool(_pilih_opsi(halaman, cocok)), tersedia


def _sama(a: str, b: str) -> bool:
    """Bandingkan isi dropdown dengan nilai yang diminta, longgar pada spasi."""
    bersih = lambda s: " ".join((s or "").split()).strip().lower()
    return bersih(a) == bersih(b)


def _tandai_pemicu(halaman, label: str) -> bool:
    """
    Tandai dropdown milik sebuah LABEL, apa pun isinya sekarang.

    Perlu ada di samping pencarian lewat teks pemicu ("Pilih nama sekolah"):
    murid yang datanya sudah ada di sistem datang dengan sekolah dan kelas
    SUDAH TERISI - dan isinya data tahun lalu. Mencari lewat teks "Pilih ..."
    tidak akan menemukannya, sehingga sekolah lama diam-diam dibiarkan.

    Labelnya TIDAK dicari sebagai elemen-daun: "Nama Sekolah *" ternyata
    membungkus tanda bintang sebagai anak elemen, jadi syarat "tanpa anak"
    membuatnya tak pernah cocok. Yang dipakai: teks elemen sama dengan label
    setelah tanda bintang dibuang, dan elemen itu bukan pembungkus besar yang
    justru memuat dropdown-nya sendiri.

    DROPDOWN-NYA DICARI DI DALAM PEMBUNGKUS LABEL, bukan "dropdown pertama
    setelah label" di seluruh halaman. Halaman ini punya filter Sekolah + Kelas
    di atas daftar murid, dan filter itu menampilkan kelas yang sedang dipakai
    petugas untuk mencari - mis. "Kelas 12". Saat filter yang tertandai, isinya
    kebetulan sama dengan nilai yang diminta, jadi kode menyimpulkan "sudah
    tepat", tidak membuka apa pun, dan murid tetap terdaftar di kelas tahun
    lalu. Label dan kolomnya selalu satu pembungkus kecil, jadi penambatan itu
    yang dipakai - dan pembungkus yang kelewat besar ditolak.
    """
    return bool(halaman.evaluate(
        r"""(label) => {
             const rapi = s => (s || '').replace(/\s+/g, ' ').trim();
             const bersih = s => rapi(s).replace(/\*$/, '').trim().toLowerCase();
             const lama = document.getElementById('mdd_sek');
             if (lama) lama.removeAttribute('id');

             const kotak = e => {
               const c = String(e.className || '');
               return e.offsetParent !== null && c.includes('cursor-pointer')
                      && c.includes('2.9rem'); };
             const dd = [...document.querySelectorAll('div')].filter(kotak);
             if (!dd.length) return false;

             const mau = label.toLowerCase();
             const cap = [...document.querySelectorAll('*')].filter(e =>
                 e.offsetParent !== null && bersih(e.innerText) === mau
                 && !dd.some(d => e.contains(d)));
             if (!cap.length) return false;

             // Naik dari label selangkah demi selangkah, berhenti pada
             // pembungkus pertama yang memuat dropdown. Batas 600 huruf
             // menjaga supaya pembungkus sebesar satu halaman - yang juga
             // memuat filter di atas - tidak ikut terpakai.
             for (const l of cap) {
               let n = l.parentElement;
               for (let naik = 0; n && naik < 6; naik++, n = n.parentElement) {
                 if (rapi(n.innerText).length > 600) break;
                 const isi = [...n.querySelectorAll('div')].filter(kotak)
                     .filter(d => l.compareDocumentPosition(d)
                                  & Node.DOCUMENT_POSITION_FOLLOWING);
                 if (isi.length) {
                   isi[0].scrollIntoView({block: 'center'});
                   isi[0].setAttribute('id', 'mdd_sek');
                   return true;
                 }
               }
             }
             return false;
           }""", label))


def _label_terlihat(halaman) -> list:
    """Daftar tulisan yang ADA di halaman — bahan pemeriksaan saat label meleset."""
    try:
        return halaman.evaluate(
            r"""() => {
                 const rapi = s => (s || '').replace(/\s+/g, ' ').trim();
                 return [...new Set([...document.querySelectorAll('label, p, span, div')]
                   .filter(e => e.offsetParent !== null)
                   .map(e => rapi(e.innerText).replace(/\*$/, '').trim())
                   .filter(t => t && t.length < 30))].slice(-24);
               }""")
    except Exception:
        return []


def _isi_dropdown_label(halaman, label: str, nilai: str) -> tuple[str, str]:
    """
    Isi dropdown milik `label` dengan `nilai` — SELALU, walau sudah terisi.

    Kembalikan (terpilih, sebab_gagal). Sebabnya dibedakan supaya kegagalan
    bisa diperiksa tanpa menebak: label yang tak ketemu dan opsi yang tak ada
    butuh perbaikan yang sama sekali berbeda.
    """
    if not _tandai_pemicu(halaman, label):
        return "", f"label '{label}' tidak ketemu; yang ada: {_label_terlihat(halaman)}"

    sekarang = (halaman.locator("#mdd_sek").inner_text() or "").strip()
    if _sama(sekarang, nilai):
        # Sudah tepat. Isi awalnya ikut dilaporkan supaya kalau yang tertandai
        # ternyata kotak yang salah, itu langsung terlihat di catatan.
        return f"{sekarang} (sudah tepat)", ""

    try:
        halaman.locator("#mdd_sek").click(timeout=5_000)
        halaman.wait_for_timeout(700)
    except Exception as e:
        return "", f"dropdown tak bisa dibuka ({type(e).__name__})"

    # Cara memilihnya sama persis dengan filter di atas halaman - komponennya
    # memang satu, termasuk daftar yang dibangun ulang tiap kali diketik.
    cocok = _pilih_opsi(halaman, nilai)
    if not cocok:
        kata = nilai.split()
        for n in range(len(kata), 0, -1):
            if not portal.cari_lokasi(halaman, " ".join(kata[:n])):
                break
            halaman.wait_for_timeout(700)
            cocok = _pilih_opsi(halaman, nilai)
            if cocok:
                break
    if not cocok:
        # Ditanya SELAGI modalnya masih terbuka - sesudah ditutup, tidak ada
        # lagi yang bisa dilihat.
        modal_kosong = portal.modal_daftar_kosong(halaman)
        tersedia = portal.opsi_lokasi(halaman)
        # Modal ini duduk di atas lapisan `fixed z-9000` yang menutupi seluruh
        # halaman; mengklik body saja tidak menutupnya, dan selama ia terbuka
        # tombol "Selanjutnya" dilaporkan "tak bisa diklik".
        if not portal.tutup_modal(halaman):
            portal.tutup_dropdown(halaman)
        if modal_kosong:
            # PORTALNYA yang tidak memuat apa-apa, bukan nilainya yang salah.
            # Terbukti dari tangkapan layar 2 Sep: modal "Pilih jenjang
            # pendidikan" terbuka, kotak carinya sudah berisi "Kelas", dan di
            # bawahnya kosong sama sekali. Dibedakan karena perlakuannya
            # berbeda: nilai yang salah harus diperbaiki di CSV, sedangkan ini
            # tidak bisa diapa-apakan siapa pun - tinggal dilewati.
            return "", "DAFTAR KOSONG - portal tidak memuat satu pilihan pun"
        return "", f"opsi '{nilai}' tak ada; tersedia: {tersedia[:8]}"
    halaman.wait_for_timeout(900)

    # BACA ULANG. Mengklik opsi bukan bukti nilainya berganti - dropdown Vue
    # portal ini punya riwayat "terlihat terpilih" tanpa modelnya ikut berubah,
    # dan kalau itu terjadi murid terdaftar di kelas atau sekolah yang lama.
    if not _tandai_pemicu(halaman, label):
        return "", "setelah dipilih, dropdown tak bisa dibaca ulang"
    kini = (halaman.locator("#mdd_sek").inner_text() or "").strip()
    if not _sama(kini, nilai):
        return "", f"TIDAK BERUBAH - masih '{kini}', diminta '{nilai}'"
    return kini, ""


KELURAHAN_KOJA = ("Rawa Badak Selatan", "Rawa Badak Utara", "Tugu Selatan",
                  "Tugu Utara", "Lagoa", "Koja")


def wilayah_domisili(orang: Peserta) -> list:
    """Jalur wilayah untuk cadangan domisili murid, atau [] bila kelurahan tak diketahui."""
    alamat = (orang.alamat or "").lower()
    kel = next((k for k in KELURAHAN_KOJA if k.lower() in alamat), "")
    kel = kel or (getattr(config, "KELURAHAN_DOMISILI_SEKOLAH", "") or "").strip()
    if not kel:
        return []
    return [("provinsi", "DKI Jakarta"), ("kota", "Kota Adm. Jakarta Utara"),
            ("kecamatan", "Koja"), ("kelurahan", kel)]


def isi_alamat(halaman, orang: Peserta, hasil: dict) -> None:
    """
    Isi alamat domisili lewat checkbox "sama dengan alamat sekolah".

    CSV sekolah tidak memuat provinsi/kota/kecamatan/kelurahan, jadi penelusuran
    bertingkat seperti alur individu tidak mungkin. Checkbox inilah jalannya.

    HASILNYA DIVERIFIKASI: checkbox ini punya riwayat tercentang secara visual
    tanpa Vue menyalin alamatnya, dan kalau itu terjadi tombol Selanjutnya tetap
    mati tanpa penjelasan.
    """
    if halaman.locator("#alamat-sama-dengan-sekolah").count():
        portal.centang(halaman, "alamat-sama-dengan-sekolah")
        halaman.wait_for_timeout(900)

    terisi = not portal.ada_pemicu(halaman, "Pilih alamat domisili")
    if terisi:
        hasil["keterangan"] += " | alamat: disalin dari sekolah"
    else:
        # LOKASI SEKOLAH KOSONG -> CENTANG TIDAK MENYALIN APA PUN.
        #
        # SMPN 136 (7 Okt 2026): kolom "Lokasi Sekolah" di halaman 2 kosong,
        # jadi "sama dengan alamat sekolah" tercentang tanpa hasil, Alamat
        # Domisili tetap "Domisili tidak boleh kosong", dan Selanjutnya mati -
        # enam murid gagal tiga kali. Centangnya dilepas, lalu wilayah dipilih
        # bertingkat seperti alur dewasa. Kelurahan diambil dari alamat murid
        # bila menyebut salah satu kelurahan, kalau tidak dari pengaturan
        # "kelurahan domisili sekolah". Tidak ditebak.
        jalur = wilayah_domisili(orang)
        if not jalur:
            hasil["keterangan"] += (" | alamat domisili MASIH KOSONG - Lokasi Sekolah di portal "
                                    "kosong dan kelurahan tak diketahui; isi 'kelurahan domisili "
                                    "sekolah' di pengaturan.txt")
        else:
            if halaman.locator("#alamat-sama-dengan-sekolah").count():
                portal.centang(halaman, "alamat-sama-dengan-sekolah", nyala=False)
                halaman.wait_for_timeout(600)
            hasil["keterangan"] += " | Lokasi Sekolah kosong - domisili dipilih sendiri"
            pendaftaran.pilih_domisili(halaman, jalur, hasil, [])

    # Detail alamat: textarea (di alur individu berupa input biasa).
    try:
        kolom = halaman.locator("#detail-domisili")
        if kolom.count() and not (kolom.input_value() or "").strip():
            kolom.fill(orang.alamat or (orang.parameter.get("sekolah") or "-"))
    except Exception as e:
        hasil["keterangan"] += f" | detail alamat GAGAL: {type(e).__name__}"


# ---------------------------------------------------------------- pendaftaran
def _isi_identitas_manual(halaman, orang: Peserta, hasil: dict) -> None:
    """
    Ketik nama, tanggal lahir, dan jenis kelamin dari CSV ke formulir murid.

    Dipakai dua jalur: sebagai cadangan ketika Cek NIK tidak menemukan data,
    dan sebagai jalur utama ketika Cek NIK memang dimatikan
    (`config.CEK_NIK_SEKOLAH`).
    """
    # `.first`: begitu bagian Data Wali ikut terbuka, id "Nama Lengkap" ada DUA
    # di halaman - milik murid dan milik wali - dan tanpa ini Playwright menolak
    # dengan "strict mode violation".
    try:
        halaman.locator("#Nama\\ Lengkap").first.fill(orang.nama)
    except Exception as e:
        # DULU DITELAN DIAM-DIAM (`except: pass`). Akibatnya kolom nama yang
        # gagal terisi tidak meninggalkan satu pun jejak, lalu kegagalannya
        # muncul jauh kemudian sebagai "HALAMAN 2 TIDAK TERBUKA" - keluhan yang
        # sama sekali tidak menunjuk sebabnya.
        hasil["keterangan"] += f" | nama GAGAL diisi: {type(e).__name__}"
    lahir = orang.tanggal_lahir
    if lahir:
        galat = portal.isi_tanggal_lahir(halaman, lahir)
        if galat:
            hasil["keterangan"] += f" | tgl lahir GAGAL: {galat}"
    else:
        hasil["keterangan"] += f" | tgl lahir tak terbaca dari berkas: {orang.tgl_lahir_teks!r}"
    # Nilai balik pemilihan jenis kelamin dulu dibuang. Kolom ini WAJIB: kalau
    # gagal dipilih, "Selanjutnya" tidak akan pernah bekerja, dan itu harus
    # kelihatan di keterangan.
    #
    # Ditanyakan dulu apakah pemicunya MASIH berbunyi "Pilih jenis kelamin".
    # Sesudah Cek NIK portal kadang sudah mengisinya sendiri; kalau begitu
    # pemicunya sudah berganti jadi "Laki-laki"/"Perempuan", pencarian lewat
    # teks lama tidak menemukan apa pun, dan tanpa penjagaan ini kita menunggu
    # 15 detik sia-sia lalu melaporkan kegagalan yang tidak pernah terjadi.
    if orang.jenis_kelamin and portal.ada_pemicu(halaman, "Pilih jenis kelamin"):
        if not portal.pilih_dropdown_teks(halaman, "Pilih jenis kelamin",
                                          orang.jenis_kelamin, timeout=6_000):
            hasil["keterangan"] += f" | jenis kelamin GAGAL dipilih: {orang.jenis_kelamin!r}"


def _jawaban_portal(halaman, orang: Peserta, hasil: dict, dari: str) -> bool:
    """
    Baca jawaban portal atas halaman 1: dilayani / terdaftar / ditolak.

    Kembalikan True bila salah satunya benar - artinya vonisnya sudah
    ditetapkan dan pemanggil harus berhenti di situ.

    DITANYA BERULANG KALI, DI TIAP TITIK KEGAGALAN. Portal tidak selalu
    menjawab dalam 2,5 detik pertama: pada seorang murid (6 Sep) popup
    "Data peserta tidak valid" baru muncul SESUDAH ketiga pertanyaan ini lewat,
    lalu tertangkap oleh penantian halaman 2 - yang tidak tahu apa-apa tentang
    popup, dan melaporkannya sebagai "HALAMAN 2 TIDAK TERBUKA | seluruh isian
    halaman 1 TERISI - portal tidak menanggapi". Vonisnya jadi `gagal` (yang
    diulang tiap jalan, selalu dengan hasil sama) padahal seharusnya
    `tidak_valid`. Rekaman halamannya memuat kalimat penolakan itu utuh.
    """
    if portal.sudah_dilayani(halaman):
        _tandai_dilayani(halaman, orang, hasil, dari)
        return True
    if portal.sudah_terdaftar(halaman):
        hasil.update(status="sudah_terdaftar",
                     keterangan=(hasil["keterangan"]
                                 + f" | {dari}: individu sudah terdaftar").lstrip(" |"))
        return True
    if portal.data_tidak_valid(halaman):
        # Bunyi popupnya disimpan SEBELUM ditutup - sesudah "Periksa Kembali"
        # diklik, kalimatnya hilang dari halaman dan tidak bisa dibaca lagi.
        pesan = portal.pesan_penolakan(halaman)
        simpan_gambar(halaman, f"sek_ditolak_{orang.baris_csv}")
        portal.klik_tombol_persis(halaman, "Periksa Kembali", timeout=3_000)
        hasil.update(status="tidak_valid",
                     keterangan=(hasil["keterangan"]
                                 + f" | {dari}: data peserta ditolak portal"
                                 + (f" - portal bilang: {pesan!r}" if pesan else "")
                                 ).lstrip(" |"))
        return True
    return False


def _tandai_dilayani(halaman, orang: Peserta, hasil: dict, dari: str) -> None:
    """
    Tandai murid yang ditolak karena SUDAH dilayani - beserta DI MANA.

    Popup penolakan menyebutkan sendiri seluruh rincian pemeriksaan yang sudah
    terjadi: puskesmas, sekolah, kelas, tanggal, dan layanannya. Empat vonis
    yang bisa keluar dari situ, dan bedanya penting:

      ckg_umum        layanannya "CKG Umum" - sudah diperiksa lewat jalur
                      umum, bukan jalur sekolah. Tidak ada lagi yang bisa
                      dikerjakan di sini.
      sekolah_berbeda sekolah di portal BUKAN sekolah yang tertulis di CSV.
      kelas_berbeda   sekolahnya sama, kelasnya yang berbeda.
      sudah_pelayanan sekolah dan kelasnya cocok - murid ini memang sudah
                      selesai diperiksa di tempatnya sendiri.

    KENAPA DUA VONIS BARU ITU PERLU. Daftar konfirmasi hadir dan daftar
    pelayanan sama-sama disaring Sekolah + Kelas. Murid yang di portal tercatat
    di sekolah/kelas lain TIDAK AKAN PERNAH muncul di kedua daftar itu, berapa
    kali pun dicari, sehingga dari luar ia tampak persis seperti murid yang
    tidak ada - dan dulu memang divonis `tidak_ditemukan`. Terjadi pada seorang
    murid (4 Sep): di CSV MIS AL IKHWAN / Kelas 2, di portal ternyata sudah
    diperiksa di MIS PUI GENTENG 2 / Kelas 1 oleh Puskesmas BANJARAN.
    Vonis yang benar bukan "tidak ditemukan", melainkan "sekolahnya berbeda".
    """
    rincian = portal.rincian_popup(halaman)
    layanan = (rincian.get("layanan") or "").strip()
    sekolah_portal = (rincian.get("sekolah") or "").strip()
    kelas_portal = (rincian.get("kelas") or "").strip()
    sekolah_csv = (orang.parameter.get("sekolah") or "").strip()
    kelas_csv = (orang.parameter.get("kelas") or "").strip()

    if re.fullmatch(r"\s*ckg\s*umum\s*", layanan, re.I):
        status = "ckg_umum"
    elif sekolah_portal and sekolah_csv and not _sama(sekolah_portal, sekolah_csv):
        status = "sekolah_berbeda"
    elif kelas_portal and kelas_csv and not _sama(kelas_portal, kelas_csv):
        status = "kelas_berbeda"
    else:
        status = "sudah_pelayanan"

    # Rincian popup ikut disimpan APA ADANYA. Vonisnya cuma satu kata; yang
    # menjelaskan duduk perkaranya - sekolah mana, kelas berapa, diperiksa
    # puskesmas mana, tanggal berapa - ada di sini.
    urut = ("puskesmas pemeriksa", "sekolah", "kelas", "tanggal pemeriksaan", "layanan")
    isi = ", ".join(f"{k}: {rincian[k]}" for k in urut if rincian.get(k))
    hasil.update(status=status,
                 keterangan=(hasil["keterangan"] + f" | {dari}: sudah menerima layanan"
                             + (f" ({isi})" if isi else "")).lstrip(" |"))


def daftar_murid(halaman, orang: Peserta, jejak: list | None = None) -> HasilDaftar:
    """
    Daftarkan satu murid lewat alur CKG Sekolah.

    DITOLAK SAAT DIKETIK MANUAL -> DICOBA SEKALI LAGI DENGAN "CEK NIK".
    Identitas yang diketik dari CSV kadang berbeda tipis dari catatan Dukcapil
    (ejaan nama, tanggal lahir), dan portal menolaknya sebagai "Data peserta
    tidak valid". Tombol "Cek NIK" mengambil identitas itu langsung dari
    Dukcapil - persis yang dicocokkan portal - jadi percobaan kedua memakai
    data itu, bukan menyerah pada percobaan pertama.

    Diulang PALING BANYAK sekali, dan hanya bila percobaan pertama memang
    tanpa Cek NIK; kalau tidak, percobaan kedua akan mengulang hal yang sama.
    """
    jejak = jejak if jejak is not None else []
    # NAMA DI DATA BUKAN NAMA. SMPN 136 (7 Okt 2026): lima murid yang kolom
    # namanya di file sekolah berisi angka ("94", "11,3" - nilai gula darah /
    # Hb yang salah ketik ke kolom nama). Diketik apa adanya, portal tidak mau
    # membuka halaman 2. NIK-nya sah, jadi identitasnya diambil lewat "Cek NIK"
    # ("Gunakan Data") - nama dari file sama sekali tidak dipakai.
    if not any(ch.isalpha() for ch in (orang.nama or "")):
        hasil = _daftar_sekali(halaman, orang, jejak, True)
        hasil["keterangan"] = (f"nama di data {orang.nama!r} bukan nama - identitas diambil "
                               "lewat Cek NIK | " + hasil["keterangan"])
        return hasil
    hasil = _daftar_sekali(halaman, orang, jejak, config.CEK_NIK_SEKOLAH)
    if hasil["status"] != "tidak_valid" or config.CEK_NIK_SEKOLAH:
        return hasil
    kedua = _daftar_sekali(halaman, orang, jejak, True)
    kedua["keterangan"] = ("ditolak saat diketik manual, diulang dengan Cek NIK | "
                           + kedua["keterangan"])
    return kedua


def _daftar_sekali(halaman, orang: Peserta, jejak: list,
                   pakai_cek_nik: bool) -> HasilDaftar:
    """Satu kali percobaan pendaftaran, dengan atau tanpa tombol "Cek NIK"."""
    hasil = HasilDaftar(nama=orang.nama, nik=orang.nik, baris=orang.baris_csv,
                        status="belum", keterangan="", tiket="")

    halaman.goto(config.HAL_SEKOLAH, wait_until="domcontentloaded")
    portal.tunggu_siap(halaman, portal.js_ada_tombol("Daftar Baru"), 2000,
                       "halaman sekolah termuat")

    if not portal.klik_tombol(halaman, "Daftar Baru"):
        hasil.update(status="gagal", keterangan="tombol 'Daftar Baru' tidak ditemukan")
        return hasil
    portal.tunggu_siap(halaman, portal.js_terlihat("#nik"), 1500, "formulir murid terbuka")

    try:
        halaman.locator("#nik").fill(orang.nik)
    except Exception as e:
        hasil.update(status="gagal", keterangan=f"kolom NIK tidak bisa diisi: {type(e).__name__}")
        return hasil

    if pakai_cek_nik:
        portal.klik_tombol(halaman, "Cek NIK")
        portal.tunggu_siap(halaman, portal.js_atau(
            portal.js_ada_tombol("Gunakan Data"),
            portal.js_terisi(r"#Nama\ Lengkap"),
            portal.js_ada_teks("tidak valid"), portal.TIDAK_VALID_JS), 2500, "jawaban Cek NIK")
        _rekam(halaman, jejak, "3_setelah_cek_nik")

        if portal.sudah_dilayani(halaman):
            _tandai_dilayani(halaman, orang, hasil, "ditolak sesudah Cek NIK")
            return hasil

        if portal.teks_ada(halaman, "tidak valid") or portal.data_tidak_valid(halaman):
            hasil.update(status="tidak_valid", keterangan="NIK/data dinyatakan tidak valid")
            return hasil

        if portal.klik_tombol(halaman, "Gunakan Data", timeout=4_000):
            hasil["keterangan"] = "data sudah ada di sistem (Gunakan Data)"
            portal.tunggu_siap(halaman, portal.js_terisi(r"#Nama\ Lengkap"), 1500,
                               "data Dukcapil termuat")
        elif not any(ch.isalpha() for ch in (orang.nama or "")):
            hasil.update(status="tidak_valid",
                         keterangan=f"NIK tidak dikenali Cek NIK dan nama di data ({orang.nama!r}) "
                                    "bukan nama - isi nama murid yang benar dulu")
            return hasil
        else:
            hasil["keterangan"] = "isi manual"
            _isi_identitas_manual(halaman, orang, hasil)
    else:
        # Cek NIK sengaja TIDAK ditekan: seluruh identitas diketik dari CSV.
        #
        # Dua penjaga dulu menumpang jawaban Cek NIK - "sudah dilayani" dan
        # "tidak valid". Keduanya TIDAK hilang: penantian sesudah "Selanjutnya"
        # halaman 1 sudah memeriksa SUDAH_DILAYANI_JS, dan penolakan data tetap
        # muncul di halaman 3. Yang berubah cuma kapan ketahuannya - lebih
        # lambat satu halaman, bukan tidak terjaga.
        hasil["keterangan"] = "isi manual (Cek NIK dilewati)"
        _rekam(halaman, jejak, "3_tanpa_cek_nik")
        _isi_identitas_manual(halaman, orang, hasil)

    try:
        kolom_hp = halaman.locator("#No\\ Whatsapp")
        if kolom_hp.count() and not (kolom_hp.input_value() or "").strip().isdigit():
            kolom_hp.fill("")
            kolom_hp.fill(orang.no_hp_bersih)
    except Exception:
        pass

    _rekam(halaman, jejak, "4_identitas_terisi")

    # Halaman 1 -> 2. Di sini "Selanjutnya" masih <button>.
    if not portal.klik_tombol(halaman, "Selanjutnya", timeout=8_000):
        if not portal.klik_teks(halaman, "Selanjutnya"):
            kosong = _isian_kosong(halaman)
            simpan_gambar(halaman, f"sek_h1_{orang.baris_csv}")
            hasil.update(status="gagal",
                         keterangan=hasil["keterangan"] + f" | 'Selanjutnya' halaman 1 mati {kosong}")
            return hasil
    portal.tunggu_siap(halaman, portal.js_atau(
        portal.js_ada_tombol("Lanjutkan"),
        portal.js_ada_teks("Pilih status pernikahan"),
        portal.SUDAH_DILAYANI_JS,
        portal.SUDAH_TERDAFTAR_JS,
        portal.TIDAK_VALID_JS), 2500, "jawaban halaman 1")

    if _jawaban_portal(halaman, orang, hasil, "setelah Selanjutnya"):
        return hasil

    portal.klik_tombol(halaman, "Lanjutkan", timeout=4_000)
    portal.tunggu_siap(halaman, portal.js_ada_teks("Pilih penyandang disabilitas"),
                       1200, "halaman 2 murid terbuka")

    HALAMAN_2 = portal.js_atau(
        portal.js_ada_teks("Isi data pendukung"),
        portal.js_ada_teks("Pilih penyandang disabilitas"),
        portal.js_ada_teks("Jenjang Pendidikan"))

    # HALAMAN 2 HARUS BENAR-BENAR TERBUKA SEBELUM DIISI.
    #
    # Bila halaman 1 gagal - misalnya tanggal lahir tak terisi - "Selanjutnya"
    # tidak memindahkan apa pun, dan versi lama tetap menjalankan `isi_halaman2`
    # DI ATAS HALAMAN 1. Hasilnya menyesatkan: yang dilaporkan "label 'Nama
    # Sekolah' tidak ketemu" (memang tidak ada di halaman 1), lalu ditutup
    # "'Selanjutnya' halaman 2 mati; belum terisi: {}" - kotak kosong yang tidak
    # menjelaskan apa pun. Terjadi pada tiga murid (3 Sep), dan
    # sebab sesungguhnya tertulis di baris kedua jejaknya: tanggal lahir gagal.
    if not portal.tunggu_kondisi(halaman, HALAMAN_2, 6_000, 200):
        # Sebelum divonis gagal: popup galat portal ("Terjadi kesalahan - Belum
        # bisa memproses data") menutupi halaman dan menelan klik berikutnya,
        # sehingga gejalanya menyerupai "portal diam saja". Alur Dewasa/Lansia
        # sudah lama menanganinya di titik yang sama; alur sekolah belum, jadi
        # satu galat sesaat langsung jadi kegagalan permanen.
        pesan = portal.tutup_popup_galat(halaman)
        if pesan:
            hasil["keterangan"] += f" | popup galat sesudah Selanjutnya: {pesan}"
            portal.klik_tombol(halaman, "Selanjutnya", timeout=8_000)
            portal.tunggu_siap(halaman, portal.js_atau(
                HALAMAN_2, portal.js_ada_tombol("Lanjutkan"),
                portal.SUDAH_DILAYANI_JS, portal.SUDAH_TERDAFTAR_JS,
                portal.TIDAK_VALID_JS), 2500, "jawaban halaman 1 (ulang)")
            if _jawaban_portal(halaman, orang, hasil, "sesudah popup galat"):
                return hasil
            portal.klik_tombol(halaman, "Lanjutkan", timeout=4_000)

    if not portal.tunggu_kondisi(halaman, HALAMAN_2, 6_000, 200):
        # DITANYA SEKALI LAGI SEBELUM DIVONIS GAGAL. Jawaban portal bisa datang
        # terlambat - sesudah kedua pertanyaan di atas lewat - dan yang
        # menangkapnya justru penantian halaman 2, yang tidak tahu apa-apa
        # tentang popup penolakan. Lihat `_jawaban_portal`.
        if _jawaban_portal(halaman, orang, hasil, "terlambat, sesudah halaman 2 ditunggu"):
            return hasil
        simpan_gambar(halaman, f"sek_h1_{orang.baris_csv}")
        _rekam(halaman, jejak, "5x_halaman2_tak_terbuka")
        # KEADAAN YANG TERAMATI, bukan tudingan ke langkah sebelumnya.
        #
        # Pesan lama berbunyi "kegagalannya ada di halaman 1, lihat langkah
        # sebelum ini" - dan ketika langkah sebelumnya TIDAK mencatat apa pun,
        # pembacanya diarahkan ke tempat kosong. Terjadi pada tiga murid
        # (3 Sep): formulirnya lengkap dan benar di layar, tombolnya
        # hidup, portalnya yang diam. Yang berguna dilaporkan adalah apa yang
        # BISA dilihat sekarang - kolom wajib mana yang masih kosong - supaya
        # "form lengkap tapi portal diam" bisa dibedakan dari "ada yang kosong".
        kosong = _isian_kosong(halaman)
        rincian = "; ".join(f"{k}: {v}" for k, v in kosong.items() if v)
        hasil.update(status="gagal",
                     keterangan=hasil["keterangan"]
                     + " | HALAMAN 2 TIDAK TERBUKA"
                     + (f" | masih kosong -> {rincian}" if rincian
                        else " | seluruh isian halaman 1 TERISI - portal tidak menanggapi"))
        return hasil
    _rekam(halaman, jejak, "5_halaman_2_sekolah")

    isi_halaman2(halaman, orang, hasil, jejak)

    if config.MODE_UJI:
        hasil.update(status="uji",
                     keterangan=hasil["keterangan"] + " | MODE UJI: berhenti sebelum mendaftarkan")
        simpan_gambar(halaman, f"sek_uji_{orang.baris_csv}")
        return hasil

    # Halaman 2 -> tiket. Di sini "Selanjutnya" berupa <div>, bukan <button>.
    #
    # Sejak 29 Sep portal menamai tombol kirim halaman 2 "Daftarkan" pada
    # formulir perorangan. Bila bentuk yang sama sampai ke formulir murid,
    # nama tombolnya dibaca dari halaman, bukan dipatok.
    kirim = "Selanjutnya"
    if not halaman.evaluate(portal.js_ada_teks("Selanjutnya")) and halaman.evaluate(
            "() => [...document.querySelectorAll('div, button')].some(e => "
            "e.offsetParent !== null && (e.innerText || '').replace(/\\s+/g, ' ').trim()"
            " === 'Daftarkan')"):
        kirim = "Daftarkan"
        hasil["keterangan"] += " | tombol halaman 2: Daftarkan"
    if _mati(halaman, kirim):
        kosong = _isian_kosong(halaman)
        simpan_gambar(halaman, f"sek_h2_{orang.baris_csv}")
        _rekam(halaman, jejak, "6x_halaman2_mati")
        if hasil.get("daftar_kosong"):
            # BUKAN kegagalan robot, dan bukan pula data yang salah: portal
            # tidak menampilkan daftar pilihannya sama sekali, sehingga kolom
            # wajib itu memang tidak bisa diisi oleh siapa pun - petugas
            # sekalipun. Ditandai tersendiri supaya tidak tercampur dengan
            # kegagalan yang perlu diperbaiki, dan supaya batch langsung
            # lanjut ke peserta berikutnya tanpa membuang waktu.
            hasil.update(status="daftar_kosong",
                         keterangan=hasil["keterangan"]
                         + f" | DILEWATI: daftar {hasil['daftar_kosong']} kosong di portal"
                           " - bukan kesalahan data, coba lagi nanti")
            return hasil
        hasil.update(status="gagal",
                     keterangan=hasil["keterangan"] + f" | '{kirim}' halaman 2 mati; belum terisi: {kosong}")
        return hasil

    if not portal.klik_teks(halaman, kirim):
        # Inilah cabang yang sebenarnya kena pada dua murid
        # (2 Sep, 15:34): tombolnya tidak mati, hanya TERTUTUP modal kosong
        # yang tidak bisa ditutup. Sebabnya sama, jadi vonisnya juga sama.
        if hasil.get("daftar_kosong"):
            hasil.update(status="daftar_kosong",
                         keterangan=hasil["keterangan"]
                         + f" | DILEWATI: daftar {hasil['daftar_kosong']} kosong di portal"
                           " - bukan kesalahan data, coba lagi nanti")
            return hasil
        hasil.update(status="gagal",
                     keterangan=hasil["keterangan"] + f" | '{kirim}' halaman 2 tak bisa diklik")
        return hasil
    portal.tunggu_siap(halaman, portal.js_atau(
        portal.js_ada_teks("No. Tiket"),
        portal.SUDAH_DILAYANI_JS,
        portal.SUDAH_TERDAFTAR_JS), 2500, "tiket murid terbit")

    # Tiket terbit langsung — tanpa langkah "Daftarkan dengan NIK".
    pola = re.compile(r"No\.?\s*Tiket\s*:?\s*([A-Za-z0-9]+-[A-Za-z0-9]+)", re.I)
    sisa = 20_000
    while sisa > 0:
        m = pola.search(halaman.inner_text("body"))
        if m:
            hasil["tiket"] = m.group(1)
            break
        # Lihat `portal.pendaftaran_gagal`: jawaban portal, bukan tiket yang lambat.
        gagal_simpan = portal.pendaftaran_gagal(halaman)
        if gagal_simpan:
            simpan_gambar(halaman, f"sek_daftar_gagal_{orang.baris_csv}")
            portal.klik_tombol_persis(halaman, "Tutup", timeout=3_000)
            hasil.update(status="gagal",
                         keterangan=hasil["keterangan"] + f" | portal: {gagal_simpan}")
            return hasil
        if portal.sudah_dilayani(halaman):
            _tandai_dilayani(halaman, orang, hasil, "sesudah daftar")
            return hasil
        # Popup "Individu sudah terdaftar" BUKAN kegagalan. Tanpa pemeriksaan
        # ini, perulangan di bawah berputar sampai 20 detik lalu memvonis
        # "tanpa_tiket" - padahal muridnya memang terdaftar dan yang tersisa
        # hanyalah memastikan kehadirannya.
        if portal.sudah_terdaftar(halaman):
            hasil.update(status="sudah_terdaftar",
                         keterangan=hasil["keterangan"] + " | portal: individu sudah terdaftar")
            return hasil
        info = portal.tutup_popup_info(halaman)
        if info:
            hasil["keterangan"] += f" | pemberitahuan dilewati: {info}"
        halaman.wait_for_timeout(500)
        sisa -= 500

    _rekam(halaman, jejak, "7_setelah_daftar_sekolah")
    if not hasil["tiket"]:
        simpan_gambar(halaman, f"sek_tiket_{orang.baris_csv}")
        hasil.update(status="tanpa_tiket", keterangan=hasil["keterangan"] + " | tiket tidak terbaca")
        return hasil

    portal.klik_tombol(halaman, "Tutup", timeout=5_000)
    hasil.update(status="terdaftar")
    return hasil


# ------------------------------------------------------- cari & konfirmasi
# Tulisan yang dipakai portal saat daftar pilihannya KOSONG. Ia tetap merender
# satu baris, jadi dropdown-nya terlihat "punya pilihan" padahal tidak ada satu
# pun yang bisa dipilih.
#
# Perlu ada di samping `portal.modal_daftar_kosong`: pemeriksa itu menghitung
# isi `.modal-content`, dan dropdown filter pada halaman ini BUKAN modal - jadi
# ia selalu menjawab "tidak kosong". Akibatnya keadaan yang jelas-jelas
# kerusakan portal dilaporkan sebagai "filter kelas GAGAL", yaitu bahasa untuk
# kesalahan data. Terjadi pada seorang murid (4 Sep), yang daftar
# kelasnya berisi persis satu baris: "Data tidak ditemukan".
_KOSONG_PLACEHOLDER = re.compile(
    r"^(data\s*)?tidak\s*(ada|ditemukan)|^tidak\s*ada\s*data|^no\s*data", re.I)


def daftar_placeholder(tersedia: list[str]) -> bool:
    """Benar bila daftar pilihannya hanya berisi tulisan 'tidak ada data'."""
    isi = [t.strip() for t in (tersedia or []) if t and t.strip()]
    return bool(isi) and all(_KOSONG_PLACEHOLDER.search(t) for t in isi)


def pasang_filter(halaman, orang: Peserta, hasil: dict) -> bool:
    """
    Pasang filter Sekolah + Kelas. Dipakai halaman pendaftaran MAUPUN pelayanan
    murid — keduanya menampilkan "Silahkan lakukan filter sekolah dan kelas
    terlebih dahulu" selama filternya kosong.
    """
    param = orang.parameter
    sekolah = (param.get("sekolah") or "").strip()
    kelas = (param.get("kelas") or "").strip()
    if not sekolah or not kelas:
        hasil["keterangan"] += " | nama sekolah / kelas kosong di CSV"
        return False

    for teks_pemicu, nilai, nama in (("Pilih sekolah", sekolah, "sekolah"),
                                     ("Pilih kelas", kelas, "kelas")):
        if portal.ada_pemicu(halaman, teks_pemicu):
            ok, tersedia = _pilih_berkotak_cari(halaman, teks_pemicu, nilai)
            if not ok:
                # Ditanya SESUDAH percobaan gagal dan SEBELUM modalnya
                # ditutup - di luar dua batas itu tidak ada yang bisa dilihat.
                modal_kosong = (portal.modal_daftar_kosong(halaman)
                                or daftar_placeholder(tersedia))
                if not portal.tutup_modal(halaman):
                    portal.tutup_dropdown(halaman)
                if modal_kosong:
                    # Kerusakan yang SAMA seperti di formulir halaman 2, dan
                    # memang muncul juga di sini - saat murid dicari untuk
                    # dikonfirmasi hadir. Portal membuka dropdownnya tanpa
                    # memuat satu pilihan pun, jadi filternya tidak bisa
                    # dipasang oleh siapa pun.
                    hasil["keterangan"] += (f" | DAFTAR {nama.upper()} KOSONG di "
                                            "portal - bukan kesalahan data")
                    hasil["daftar_kosong"] = nama
                else:
                    hasil["keterangan"] += (f" | filter {nama} GAGAL ({nilai}); "
                                            f"tersedia: {tersedia[:6]}")
                simpan_gambar(halaman, f"sek_filter_{orang.baris_csv}")
                return False
            # Dulu jeda tetap 1,2 detik - dua kali per murid, dan filter ini
            # dipasang DUA KALI (daftar murid lalu daftar pelayanan): 4,8 detik
            # per murid hanya untuk berjaga-jaga.
            portal.tunggu_pemicu_hilang(halaman, teks_pemicu, 1200,
                                        f"filter {nama} terpasang")

    # Halaman PELAYANAN tidak memuat daftarnya sendiri: sesudah kedua filter
    # terisi barulah tombol "Tampilkan Pencarian" muncul, dan sebelum ditekan
    # tabelnya benar-benar kosong (0 baris) - bukan sekadar belum termuat.
    # Halaman pendaftaran tidak punya tombol ini, jadi kehadirannya diperiksa
    # dulu, bukan dianggap wajib.
    # DITUNGGU DULU KEMUNCULANNYA. Tombolnya baru dipasang portal sesudah
    # kedua filter benar-benar mengendap, dan tenggat 4 detik pernah kurang:
    # pada seorang murid (3 Sep) langkah "tampilkan pencarian" TIDAK ADA di jejaknya,
    # sehingga tabelnya tak pernah tampil dan muridnya divonis tidak ada.
    portal.tunggu_kondisi(halaman, portal.js_ada_tombol("Tampilkan Pencarian"),
                          6_000, 200)
    if portal.klik_tombol(halaman, "Tampilkan Pencarian", timeout=6_000):
        hasil["keterangan"] += " | tampilkan pencarian"
        # "tr > 1" saja tidak cukup: baris rangka abu-abu pun <tr>.
        portal.tunggu_siap(halaman, portal.js_dan(
            portal.JS_TIDAK_MEMUAT,
            portal.js_atau("() => document.querySelectorAll('tr').length > 1",
                           portal.js_ada_teks("Tidak ada data"))),
            config.TUNGGU_MUNCUL_MS, "daftar murid tampil")

    hasil["keterangan"] += f" | filter: {sekolah} / {kelas}"
    return True


def cari_murid(halaman, orang: Peserta, hasil: dict, jejak: list,
               muat_ulang: bool = False):
    """
    Temukan baris murid di halaman pendaftaran sekolah.

    Urutannya WAJIB: Sekolah -> Kelas -> NIK. Tanpa dua filter pertama, tabel
    hanya menampilkan "Silahkan lakukan filter sekolah dan kelas terlebih
    dahulu" - tidak ada baris untuk dicari.

    `muat_ulang` WAJIB dinyalakan bila halaman sedang tidak menampilkan daftar
    murid - lihat alasannya di bawah.
    """
    # JANGAN memuat ulang bila sudah berada di halaman ini. Tombol "Periksa
    # Skrining Mandiri" pada modal "Berhasil Hadir" memakai `regId` yang
    # disimpan aplikasi di memori sewaktu murid didaftarkan; `goto` memuat
    # ulang seluruh halaman dan menghapusnya, sehingga tombol itu pasti gagal.
    #
    # TAPI URL BUKAN PENANDA ISI LAYAR. Formulir "Daftar Baru" dan popup
    # "sudah menerima layanan" hidup di URL YANG SAMA dengan daftar murid.
    # Jadi sesudah pendaftaran ditolak, syarat di bawah terpenuhi - halaman
    # tidak dimuat ulang - padahal yang tampak masih formulir tertutup popup:
    # filter Sekolah/Kelas tidak ada, kolom NIK tidak ada, pencarian gagal
    # tanpa suara, dan alurnya jatuh ke halaman pelayanan. Itulah kenapa
    # pemuatan ulang harus bisa DIMINTA, bukan disimpulkan dari URL.
    if muat_ulang or config.HAL_SEKOLAH.rsplit("/", 1)[-1] not in halaman.url:
        halaman.goto(config.HAL_SEKOLAH, wait_until="domcontentloaded")
        halaman.wait_for_timeout(2500)
    # SAH atau TIDAK, itu yang menentukan arti "tak ketemu".
    #
    # Filter Sekolah+Kelas yang gagal dipasang berarti daftarnya TIDAK PERNAH
    # TAMPIL - "muridnya tidak ada di sana" jadi kalimat tentang daftar yang
    # belum sempat dilihat. Dulu keduanya sama-sama mengembalikan None, jadi
    # tak ada yang bisa membedakannya di kemudian hari, dan murid yang jelas
    # ADA di halaman konfirmasi hadir divonis `tidak_ditemukan`. Terjadi pada
    # seorang murid (4 Sep).
    hasil["cari_konfirmasi_sah"] = False

    # FILTER YANG GAGAL ITU KERUSAKAN PORTAL, DAN OBATNYA MUAT ULANG.
    #
    # Daftar kelas yang datang kosong ("Data tidak ditemukan") atau dropdown
    # yang tidak mau menerima pilihan bukan soal data murid - halamannya yang
    # tidak beres. Sekali dimuat ulang, daftarnya biasanya normal lagi. Tanpa
    # pengulangan di sini, satu kedipan portal cukup untuk membuat murid yang
    # jelas ada di daftar konfirmasi hadir divonis tidak ada - persis yang
    # menimpa seorang murid (4 Sep).
    #
    # Diulang di SINI, bukan diserahkan ke pengulangan seluruh peserta: yang
    # perlu diulang cuma memuat halaman dan memasang filter, sedangkan
    # mengulang pesertanya berarti mendaftarkannya lagi dari awal.
    percobaan_maks = max(1, config.PERCOBAAN_ULANG)
    for percobaan in range(1, percobaan_maks + 1):
        if percobaan > 1:
            hasil["keterangan"] += (f" | filter/pencarian gagal - halaman dimuat"
                                    f" ulang, dicoba lagi ({percobaan}/{percobaan_maks})")
            halaman.goto(config.HAL_SEKOLAH, wait_until="domcontentloaded")
            portal.tunggu_siap(halaman, portal.js_ada_tombol("Daftar Baru"),
                               config.TUNGGU_MUNCUL_MS, "halaman sekolah dimuat ulang")
        if not pasang_filter(halaman, orang, hasil):
            continue
        if not _cari_nik(halaman, orang, hasil, jejak):
            continue
        hasil["cari_konfirmasi_sah"] = True
        break
    if not hasil["cari_konfirmasi_sah"]:
        return None
    _rekam(halaman, jejak, "8_hasil_pencarian_sekolah")

    def temukan():
        b = portal.baris_bernama(halaman, orang.nama)
        if b.count():
            return b.first
        # Nama di portal bisa berbeda dari CSV; filter Sekolah+Kelas+NIK sudah
        # cukup sempit, jadi bila tersisa tepat satu baris data, itu muridnya.
        satu = halaman.evaluate(
            """() => {
                 const b = [...document.querySelectorAll('tr')]
                   .map((t, i) => ({i, teks: (t.innerText || '').trim(),
                                    tombol: t.querySelectorAll('button').length}))
                   .filter(x => x.tombol > 0 && x.teks.length > 20);
                 return b.length === 1 ? b[0].i : -1;
               }""")
        if satu >= 0:
            hasil["keterangan"] += " | nama beda, dipakai satu-satunya baris hasil"
            return halaman.locator("tr").nth(satu)
        return None

    baris = temukan()
    if baris is not None:
        return baris

    # MURID YANG BARU DIDAFTARKAN BELUM LANGSUNG TERINDEKS PORTAL.
    #
    # Pencarian pertama benar-benar kosong, lalu beberapa detik kemudian
    # muridnya muncul. Alur Dewasa/Lansia sudah lama mengulang Enter untuk ini
    # (peserta AKQ-KBA, FVL-RB9, 89P-NLL); alur sekolah belum, jadi murid yang
    # pendaftarannya BERHASIL - tiketnya sudah terbit - divonis tidak ada.
    # Terjadi pada murid A (X6N-ZPS), murid B
    # (GD7-DK2), dan murid C (5CV-8CA) pada 4 Sep.
    #
    # Hanya dijalankan bila TIKETNYA ADA. Tiket itu bukti pendaftarannya baru
    # saja diterima portal - jadi muridnya PASTI ada, tinggal soal waktu. Murid
    # tanpa tiket tidak ikut menunggu, sehingga yang memang tidak terdaftar
    # tidak jadi lebih lambat.
    if hasil.get("tiket"):
        kolom = layanan._kolom_cari(halaman)
        habis, putaran = config.TUNGGU_MUNCUL_MS, 0
        while kolom is not None and habis > 0:
            halaman.wait_for_timeout(1500)
            habis -= 1500
            putaran += 1
            try:
                kolom.press("Enter")
            except Exception:
                break
            portal.tunggu_siap(halaman, portal.js_dan(
                portal.JS_TIDAK_MEMUAT,
                portal.js_atau(portal.js_ada_nama(orang.nama),
                               portal.js_ada_teks("Tidak ada data"))),
                3000, "hasil pencarian murid (ulang)")
            baris = temukan()
            if baris is not None:
                hasil["keterangan"] += f" | muncul sesudah dicari ulang {putaran}x"
                return baris
        hasil["keterangan"] += (f" | sudah punya tiket {hasil['tiket']} tapi tetap "
                                f"tak muncul sesudah dicari ulang {putaran}x")

    hasil["keterangan"] += " | murid tidak ketemu di daftar"
    simpan_gambar(halaman, f"sek_cari_{orang.baris_csv}")
    return None


def _cari_nik(halaman, orang: Peserta, hasil: dict, jejak: list) -> bool:
    """Ubah mode pencarian ke NIK, ketik NIK, Enter. Dipakai dua halaman."""
    layanan._pilih_mode_nik(halaman, hasil, jejak)
    portal.tunggu_siap(halaman, portal.ADA_KOLOM_NIK, 800, "kolom NIK siap")
    kolom = layanan._kolom_cari(halaman)
    if kolom is None:
        hasil["keterangan"] += " | kolom pencarian NIK tidak ketemu"
        return False
    sebelum = portal.tanda_tabel(halaman)
    try:
        if not layanan._ketik_cari(halaman, kolom, orang.nik):
            hasil["keterangan"] += (" | kolom NIK TIDAK BERISI NIK yang benar "
                                    "sesudah diketik - pencarian dibatalkan")
            return False
        kolom.press("Enter")
    except Exception as e:
        hasil["keterangan"] += f" | kolom cari gagal: {type(e).__name__}"
        return False
    portal.tunggu_beda(halaman, sebelum, 2500, "hasil pencarian NIK murid")
    # Tabel berubah BUKAN berarti hasilnya sudah ada - lihat JS_TIDAK_MEMUAT.
    # Yang ditunggu: tirai pemuatan hilang DAN ada jawabannya, entah muridnya
    # muncul entah portal berkata tidak ada.
    portal.tunggu_siap(halaman, portal.js_dan(
        portal.JS_TIDAK_MEMUAT,
        portal.js_atau(portal.js_ada_nama(orang.nama),
                       portal.js_ada_teks("Tidak ada data"))),
        config.TUNGGU_MUNCUL_MS, "hasil pencarian murid termuat")
    return True


def _baris_pelayanan(halaman, orang: Peserta, tiket: str):
    """
    Baris murid di daftar pelayanan — dicari lewat nomor tiket lebih dulu.

    Tiket jauh lebih dapat dipercaya daripada nama: nama di portal kerap
    berbeda dari CSV ("M. ADI" vs "Muhammad Adi"), sedangkan tiketnya baru
    saja kita baca sendiri dari modal "Berhasil Hadir".
    """
    for kunci in (tiket, orang.nama):
        if not kunci:
            continue
        calon = portal.baris_bernama(halaman, kunci)
        if calon.count():
            return calon.first
    satu = halaman.evaluate(
        """() => {
             const b = [...document.querySelectorAll('tr')]
               .map((t, i) => ({i, teks: (t.innerText || '').trim(),
                                tombol: t.querySelectorAll('button').length}))
               .filter(x => x.tombol > 0 && x.teks.length > 20);
             return b.length === 1 ? b[0].i : -1;
           }""")
    return halaman.locator("tr").nth(satu) if satu >= 0 else None


def mulai_lewat_pelayanan(halaman, orang: Peserta, hasil: dict, jejak: list) -> bool:
    """
    Buka pemeriksaan murid lewat `/ckg-pelayanan-sekolah`.

    Perlu ada karena tombol "Periksa Skrining Mandiri" pada modal "Berhasil
    Hadir" MEMANG tidak bisa dipakai dari jalur ini - dan itu bukan soal klik
    yang meleset. Penangannya di portal berbunyi:

        const L = o.regId || o.selectedIndividu?.reg_id;
        const u = await enkripsi(L); ...
        navigateTo({path: "/ckg-pelayanan-sekolah/detail-pemeriksaan"})

    Murid yang dikonfirmasi dari DAFTAR tidak punya `regId` di memori aplikasi,
    sehingga `enkripsi(undefined)` melempar "toLowerCase of undefined": modal
    tertutup, halaman tidak berpindah. Yang mengisi `regId` itu tombol "Mulai"
    di daftar pelayanan - jadi ke sanalah kita masuk.

    Pencarian NIK sengaja TIDAK dipakai di sini: filter Sekolah + Kelas sudah
    menyisakan satu kelas saja, dan mengganti mode pencarian di halaman ini
    justru gagal lalu menutupi kolom yang mau dibaca.
    """
    # Modal tiket HANYA ada bila murid baru saja didaftarkan. Pada alur lanjutan
    # tidak ada modal sama sekali, dan `klik_tombol` membayar tenggat penuh 3
    # detik untuk membuktikan ketiadaannya - tiap murid, tanpa hasil apa pun.
    # Ditanya dulu dengan satu evaluasi murah; jawabannya sama, harganya nol.
    if halaman.evaluate(portal.js_ada_tombol("Tutup")):
        portal.klik_tombol(halaman, "Tutup", timeout=3_000)   # lepas modal tiket
        halaman.wait_for_timeout(600)
    halaman.goto(config.HAL_PELAYANAN_SEKOLAH, wait_until="domcontentloaded")
    portal.tunggu_siap(halaman, portal.js_ada_teks("Pilih sekolah"), 2500,
                       "halaman pelayanan murid termuat")
    if not pasang_filter(halaman, orang, hasil):
        return False

    # TABEL HARUS BENAR-BENAR TAMPIL sebelum apa pun disimpulkan darinya.
    # Halaman pelayanan tidak memuat daftarnya sendiri - baru muncul sesudah
    # "Tampilkan Pencarian" ditekan. Bila langkah itu terlewat, layar yang
    # kosong BUKAN berarti muridnya tidak ada; tabelnya memang belum pernah
    # ditampilkan. Menyimpulkan "tidak_ditemukan" dari layar seperti itu
    # keliru dan menyesatkan - terjadi pada seorang murid (3 Sep), yang
    # sebenarnya ada di tab "Belum Pemeriksaan".
    if not portal.tunggu_kondisi(halaman, portal.js_atau(
            "() => document.querySelectorAll('tr').length > 1",
            portal.js_ada_teks("Tidak ada data")), 8_000, 200):
        hasil["keterangan"] += (" | daftar pelayanan TIDAK TAMPIL - tabelnya "
                                "belum pernah dimuat, jadi 'tidak ada' bukan "
                                "kesimpulan yang sah")
        simpan_gambar(halaman, f"sek_tabel_{orang.baris_csv}")
        hasil["status"] = "gagal_mulai"      # boleh diulang, bukan soal data
        return False

    tiket = (hasil.get("tiket") or "").strip()
    dipersempit = False
    cari_sah = True
    if not tiket:
        # Tanpa tiket - alur pelayanan, yang memang tidak mendaftarkan siapa
        # pun - murid dicari lewat NIK. Satu kelas bisa memuat lebih dari satu
        # halaman, jadi mengandalkan nama saja tidak cukup.
        #
        # HASILNYA DIPAKAI, bukan dibuang. Versi lama memanggilnya lalu
        # mengabaikan jawabannya: ketika pencariannya sendiri gagal - pada
        # Raihan Putra Narendra (3 Sep) "kolom cari gagal: TimeoutError" -
        # tabel yang tampil masih berisi SATU KELAS PENUH, tidak pernah
        # dipersempit, dan muridnya divonis "tidak ada". Pencarian yang gagal
        # bukan bukti apa pun.
        cari_sah = bool(_cari_nik(halaman, orang, hasil, jejak))
        dipersempit = True

    # Tab yang masih memuat saat dibaca - kalau ada, "tak ada di daftar" TIDAK
    # boleh disimpulkan. Dikumpulkan lewat daftar, bukan nilai balik, supaya
    # `telusuri_tab` tetap bisa dipanggil dua kali seperti sekarang.
    belum_selesai_muat: list[str] = []

    def telusuri_tab():
        """Buka ketiga tab status, kembalikan (baris, nama_tab) yang cocok."""
        for tab in ("Belum Pemeriksaan", "Sedang Pemeriksaan", "Selesai Pemeriksaan"):
            tanda_tab = portal.tanda_tabel(halaman)
            # `klik_tab`, bukan `klik_teks`: begitu sebuah tab ada antreannya,
            # portal menempelkan jumlahnya ke label ("Belum Pemeriksaan 1") dan
            # pencocokan teks persis tidak mengenainya lagi. Lihat
            # `portal.klik_tab` - satu bug yang sama menjatuhkan seluruh
            # peserta skrining TBC pada 7 Sep.
            if not portal.klik_tab(halaman, tab):
                belum_selesai_muat.append(f"{tab} (tab tidak terbuka)")
                continue
            portal.tunggu_beda(halaman, tanda_tab, 2000, f"tab {tab}")
            # Rangka abu-abu juga mengubah tabel - lihat portal.JS_TIDAK_MEMUAT.
            #
            # NILAI BALIKNYA DIPAKAI. Dulu dibuang, dan itu membuat seluruh
            # penantian ini tidak menjamin apa pun: sesudah tenggatnya habis
            # tabelnya tetap dibaca walau masih bertuliskan "Memuat data..",
            # tidak ketemu siapa-siapa, lalu muridnya divonis tidak ada.
            # Terjadi pada seorang murid (4 Sep) - rekaman halamannya
            # berakhir dengan "Memuat data.." tepat saat ia dinyatakan tak ada,
            # padahal barisnya memang ada di tab Belum Pemeriksaan, lengkap
            # dengan tiket XX4-MDV dan tombol Mulai.
            #
            # Tenggatnya ikut "tunggu muncul" di pengaturan (12 detik), bukan
            # 6 detik mati: daftar satu kelas memang bisa lama.
            #
            # DIAM, bukan sekadar "sedang tidak memuat". Sesudah tab diklik ada
            # celah sebelum portal mulai mengambil data; diperiksa di celah itu
            # jawabannya "sudah selesai" padahal belum mulai, lalu baris tab
            # SEBELUMNYA yang terbaca. Lihat `portal.tunggu_tabel_tenang`.
            if not portal.tunggu_tabel_tenang(halaman, config.TUNGGU_MUNCUL_MS,
                                              f"tab {tab} tenang"):
                belum_selesai_muat.append(tab)
            ketemu = _baris_pelayanan(halaman, orang, tiket)
            if ketemu is not None:
                hasil["keterangan"] += f" | pelayanan tab: {tab}"
                return ketemu, tab
        return None, ""

    baris, ketemu_di = telusuri_tab()
    if baris is None and not dipersempit:
        # SATU KELAS BISA RATUSAN MURID. Bila tiketnya ada, daftar ini tidak
        # pernah dipersempit lewat NIK - yang tampil adalah SELURUH kelas, dan
        # portal hanya merender sebagiannya. Murid yang berada di luar bagian
        # itu terbaca "tak ada di daftar" padahal ia ada, bahkan sudah duduk di
        # tab "Selesai Pemeriksaan" - lalu divonis `tidak_ditemukan`, bukan
        # `sudah_pelayanan`. Terjadi pada kelas berisi 128 murid (RBS 07).
        #
        # Jadi sebelum menyerah, daftarnya dipersempit lewat NIK dan ketiga
        # tabnya ditelusuri sekali lagi. Ongkosnya hanya dibayar oleh murid
        # yang memang tidak ketemu - yang ketemu sejak awal tidak terpengaruh.
        hasil["keterangan"] += " | tak ketemu di daftar penuh, dipersempit lewat NIK"
        if _cari_nik(halaman, orang, hasil, jejak):
            baris, ketemu_di = telusuri_tab()

    # Sapuan tadi membaca tabel yang masih memuat -> jawabannya belum sah.
    # Ditunggu sampai benar-benar selesai lalu disapu SEKALI LAGI, sebelum
    # mengulang seluruh peserta dari awal: ongkosnya beberapa detik, sedangkan
    # mengulang peserta berarti mendaftar dan mencari ulang dari nol.
    if baris is None and belum_selesai_muat:
        hasil["keterangan"] += (" | tabel masih memuat di tab "
                                + ", ".join(sorted(set(belum_selesai_muat)))
                                + " - ditunggu lalu disapu ulang")
        portal.tunggu_tabel_tenang(halaman, config.TUNGGU_MUNCUL_MS,
                                   "daftar pelayanan tenang")
        belum_selesai_muat.clear()
        baris, ketemu_di = telusuri_tab()

    # Murid di tab "Selesai" memang sudah rampung - tidak ada tombol Mulai di
    # sana, dan melaporkannya sebagai gagal hanya membuat batch terlihat rusak.
    # Sama seperti alur dewasa: "Selesai" itu keputusan portal tentang MURIDNYA,
    # bukan jaminan tiap formnya terisi. Mode sapu tetap membukanya.
    if ketemu_di.startswith("Selesai") and not layanan.mode_sapu():
        hasil["status"] = "sudah_pelayanan"
        return False
    _rekam(halaman, jejak, "11b_daftar_pelayanan_sekolah")
    if baris is None:
        hasil["keterangan"] += f" | murid ({tiket or orang.nama}) tak ada di daftar pelayanan"
        # Bukan kegagalan alat: murid memang tidak ada di sekolah/kelas itu,
        # atau NIK-nya keliru. Dibedakan supaya tidak tercampur dengan murid
        # yang ketemu tapi gagal dimulai pemeriksaannya.
        #
        # KECUALI bila pencariannya sendiri tidak sah: filter yang tak bisa
        # dipasang karena daftarnya kosong, atau kolom pencarian NIK yang
        # gagal. Pada dua keadaan itu tabelnya tidak pernah dipersempit ke
        # muridnya, jadi "tak ada di daftar" bukan kesimpulan yang sah -
        # melainkan kegagalan alat yang layak diulang.
        if hasil.get("daftar_kosong"):
            hasil["status"] = "daftar_kosong"
        elif not cari_sah:
            hasil["keterangan"] += (" | pencarian NIK GAGAL, jadi 'tak ada di "
                                    "daftar' bukan kesimpulan yang sah")
            hasil["status"] = "gagal_mulai"
        elif belum_selesai_muat:
            # Tabel yang masih memuat belum menjawab apa pun. Ini kegagalan
            # alat yang layak diulang, BUKAN vonis atas muridnya.
            hasil["keterangan"] += (" | tabel masih MEMUAT saat dibaca di tab "
                                    + ", ".join(sorted(set(belum_selesai_muat)))
                                    + " - 'tak ada di daftar' bukan kesimpulan yang sah")
            hasil["status"] = "gagal_mulai"
        else:
            hasil["status"] = "tidak_ditemukan"
        simpan_gambar(halaman, f"sek_pelayanan_{orang.baris_csv}")
        return False

    try:
        baris.locator('button:has-text("Mulai")').first.click(timeout=6_000)
    except Exception as e:
        hasil["keterangan"] += f" | tombol 'Mulai' gagal diklik: {type(e).__name__}"
        simpan_gambar(halaman, f"sek_mulai_{orang.baris_csv}")
        return False
    halaman.wait_for_timeout(2000)

    # Ditanya SEKALI tombol mana yang ada. Antrean lama membayar tenggat penuh
    # untuk tiap nama yang tidak ada di halaman.
    dipakai = portal.klik_salah_satu(halaman, ("Konfirmasi", "Ya", "Mulai", "Simpan"), 2_500)
    if dipakai:
        hasil["keterangan"] += f" | konfirmasi mulai: {dipakai}"

    sampai = portal.tunggu_kondisi(
        halaman, "() => location.href.includes('detail-pemeriksaan')", batas_ms=10_000)
    if not sampai:
        hasil["keterangan"] += " | dari pelayanan pun tak sampai halaman detail"
        simpan_gambar(halaman, f"sek_detail_{orang.baris_csv}")
    return sampai


def _kelas_tersedia(halaman, orang: Peserta) -> list[str]:
    """
    Kelas yang BENAR-BENAR ditawarkan portal untuk sekolah ini.

    Dibaca dari dropdownnya, bukan ditebak dari "Kelas 1..6": penamaannya milik
    portal, dan sekolah yang bukan SD memakai angka yang lain sama sekali.
    """
    sekolah = (orang.parameter.get("sekolah") or "").strip()
    if not sekolah:
        return []
    halaman.goto(config.HAL_SEKOLAH, wait_until="domcontentloaded")
    halaman.wait_for_timeout(2500)
    if not portal.ada_pemicu(halaman, "Pilih sekolah"):
        return []
    ok, _ = _pilih_berkotak_cari(halaman, "Pilih sekolah", sekolah)
    if not ok:
        portal.tutup_dropdown(halaman)
        return []
    portal.tunggu_pemicu_hilang(halaman, "Pilih sekolah", 1200,
                                "filter sekolah terpasang")
    opsi = portal.buka_dan_rekam(halaman, "Pilih kelas")
    portal.tutup_dropdown(halaman)
    return [] if daftar_placeholder(opsi) else [o for o in opsi if o.strip()]


def cari_di_kelas_lain(halaman, orang: Peserta, hasil: dict, jejak: list) -> bool:
    """
    Cari murid di KELAS LAIN sekolah yang sama.

    KENAPA PERLU. Daftar konfirmasi hadir dan daftar pelayanan sama-sama
    disaring Sekolah + Kelas, jadi murid yang di portal tercatat di kelas lain
    daripada yang tertulis di CSV TIDAK AKAN PERNAH muncul - berapa kali pun
    dicari. Dari luar ia terlihat persis seperti murid yang tidak ada.

    Terjadi pada seorang murid (MIS AL IKHWAN, 4 Sep): portal menjawab
    "sudah menerima layanan (CKG Sekolah)" - jadi pendaftarannya JELAS ADA -
    tapi NIK-nya tidak ketemu di Kelas 2, baik di daftar konfirmasi hadir
    maupun di ketiga tab halaman pelayanan.

    HANYA dijalankan bila portal SUDAH MENGAKUI muridnya ada ("sudah
    terdaftar" / "sudah menerima layanan"). Murid yang datanya DITOLAK portal
    tidak ikut disapu: penolakan itu berarti identitasnya tidak diterima sama
    sekali, jadi tidak ada catatan yang bisa ditemukan di kelas mana pun, dan
    menyapunya hanya membayar satu pemuatan halaman per kelas untuk sesuatu
    yang sudah pasti kosong.

    Bila ketemu, `orang.parameter["kelas"]` DIGANTI ke kelas yang benar supaya
    langkah-langkah berikutnya memakai filter yang sama.
    """
    semula = (orang.parameter.get("kelas") or "").strip()
    calon = [k for k in _kelas_tersedia(halaman, orang) if not _sama(k, semula)]
    if not calon:
        hasil["keterangan"] += " | daftar kelas tidak terbaca, sapuan kelas lain dilewati"
        return False
    hasil["keterangan"] += f" | disapu ke kelas lain: {calon}"
    # KELAS ASLINYA DIPULIHKAN DI `finally`, bukan di baris terakhir. Galat di
    # tengah sapuan - pada seorang murid itu "ERR_NAME_NOT_RESOLVED" saat
    # berpindah ke Kelas 2 - melompati pemulihan biasa, dan murid itu tertinggal
    # dengan kelas sapuan. Percobaan berikutnya lalu mencarinya di Kelas 2,
    # tentu tidak ketemu, dan menjatuhkan `tidak_ditemukan` atas murid yang
    # sudah duduk di tab Selesai kelas aslinya.
    ketemu = False
    try:
        for kelas in calon:
            orang.parameter["kelas"] = kelas
            if cari_murid(halaman, orang, hasil, jejak, muat_ulang=True) is not None:
                hasil["keterangan"] += (f" | KELAS DI PORTAL BERBEDA: ketemu di {kelas!r},"
                                        f" di CSV tertulis {semula!r}")
                ketemu = True
                return True
    finally:
        if not ketemu:
            orang.parameter["kelas"] = semula
    hasil["keterangan"] += f" | tidak ada di kelas mana pun ({len(calon)} kelas disapu)"
    return False


def pelayanan_saja(halaman, orang: Peserta, hasil: dict, jejak: list) -> None:
    """
    ALUR PELAYANAN murid: langsung di `/ckg-pelayanan-sekolah`, tanpa mendaftar.

    Urutannya persis seperti petugas mengerjakannya:
      1. pilih nama sekolah          4. ubah mode pencarian ke NIK
      2. pilih kelas                 5. ketik NIK lalu Enter
      3. tekan "Tampilkan Pencarian" 6. periksa tab Belum / Sedang / Selesai
      7. tekan "Mulai" bila ada      8. isi seluruh daftar layanan

    Karena tanpa pendaftaran tidak ada tiket, `mulai_lewat_pelayanan` otomatis
    mencari lewat NIK - itu satu-satunya beda dari alur pendaftaran.
    """
    if not mulai_lewat_pelayanan(halaman, orang, hasil, jejak):
        # Status yang sudah ditetapkan di dalam sana - "sudah_pelayanan" dan
        # "tidak_ditemukan" - dipertahankan; hanya sisanya yang jadi gagal.
        if hasil.get("status") not in ("sudah_pelayanan", "tidak_ditemukan",
                                       "daftar_kosong"):
            hasil["status"] = ("daftar_kosong" if hasil.get("daftar_kosong")
                               else "gagal_mulai")
        return
    if not layanan.mulai_pemeriksaan(halaman, orang, hasil, jejak):
        hasil["status"] = "gagal_mulai"
        return
    if "detail-pemeriksaan" not in halaman.url:
        hasil["keterangan"] += " | tidak sampai halaman daftar layanan"
        hasil["status"] = "gagal_detail"
        return
    layanan.petakan_layanan(halaman, hasil, jejak)
    layanan.sweep_layanan(halaman, orang, hasil, jejak)


def penuh(halaman, orang: Peserta, hasil: dict, jejak: list,
          muat_ulang: bool = False) -> None:
    """
    Daftar -> konfirmasi hadir -> mulai pemeriksaan -> isi semua form.

    `muat_ulang=True` dipakai alur "Pendaftaran -> Konfirmasi Hadir": di sana
    pendaftaran BARU SAJA ditolak dengan popup "sudah menerima layanan", jadi
    layarnya masih formulir dan harus dikembalikan ke daftar murid dulu. Tidak
    ada `regId` yang perlu diselamatkan pada jalur itu - muridnya memang tidak
    jadi didaftarkan.

    MURID YANG TIDAK ADA DI DAFTAR KONFIRMASI HADIR TIDAK LANGSUNG MENYERAH.
    Begitu pemeriksaannya dimulai, murid HILANG dari halaman pendaftaran dan
    hanya tersisa di halaman pelayanan - jadi "tidak ada di daftar konfirmasi"
    bukan bukti ia tidak ada, melainkan bisa berarti ia sudah lebih maju.
    Karena itu halaman pelayanan selalu ditengok dulu sebelum divonis; vonis
    `tidak_ditemukan` baru jatuh bila di sana pun tidak ada.
    """
    # Murid yang SUDAH hadir tidak punya tombol "Konfirmasi Hadir" lagi, dan
    # dulu itu berhenti sebagai gagal_konfirmasi. Padahal langkah berikutnya
    # tetap bisa dijalankan - konfirmasi hanya dilakukan bila memang tersedia.
    dikonfirmasi = False
    baris = cari_murid(halaman, orang, hasil, jejak, muat_ulang)
    if baris is not None:
        tombol = layanan._tombol_baris(baris)
        if any(re.search(r"konfirmasi|hadir", t, re.I) for t in tombol):
            if not layanan.konfirmasi_pada_baris(halaman, orang, hasil, jejak, baris):
                hasil["status"] = "gagal_konfirmasi"
                return
            dikonfirmasi = True
        else:
            hasil["keterangan"] += f" | sudah hadir (aksi: {tombol or '-'})"

    # Jalur utama = seperti petugas mengerjakannya: modal "Berhasil Hadir" ->
    # "Periksa Skrining Mandiri". Itu hanya bekerja bila `regId` masih ada di
    # memori aplikasi, yaitu untuk murid yang baru saja didaftarkan tanpa
    # halaman dimuat ulang. Untuk murid yang tinggal dilanjutkan, `regId`-nya
    # memang tidak ada, dan di situlah halaman pelayanan mengambil alih.
    if muat_ulang and not dikonfirmasi:
        # Di jalur ini halaman BARU SAJA dimuat ulang - `regId` pasti hilang -
        # dan tidak ada konfirmasi yang menerbitkannya kembali. Jadi langkah di
        # bawah TIDAK MUNGKIN berhasil; mencobanya hanya membayar tenggat
        # tombol lalu menyimpan satu tangkapan layar "gagal" per murid, untuk
        # kegagalan yang sudah pasti. Langsung saja lewat halaman pelayanan.
        hasil["keterangan"] += " | langsung lewat halaman pelayanan"
        sampai = False
    else:
        sampai = (layanan.mulai_pemeriksaan(halaman, orang, hasil, jejak)
                  and "detail-pemeriksaan" in halaman.url)
    if not sampai:
        if not mulai_lewat_pelayanan(halaman, orang, hasil, jejak):
            # KELAS DI CSV BELUM TENTU KELAS DI PORTAL.
            #
            # Sampai di sini muridnya tidak ada di daftar konfirmasi hadir
            # MAUPUN di ketiga tab halaman pelayanan - padahal portal sendiri
            # yang bilang pendaftarannya ada. Kedua daftar itu disaring
            # Sekolah + Kelas, jadi satu-satunya tempat yang belum dilihat
            # adalah kelas yang lain. Lihat `cari_di_kelas_lain`.
            #
            # KECUALI MURIDNYA SUDAH KETEMU. `mulai_lewat_pelayanan` juga pulang
            # False untuk murid yang ada di tab "Selesai Pemeriksaan" kelasnya
            # sendiri - statusnya sudah `sudah_pelayanan`, tidak ada yang perlu
            # dicari lagi. Dulu itu tetap disapu ke kelas lain: seorang
            # murid (SDN LAGOA 11, 15 Sep) ketemu di Kelas 5 tab Selesai,
            # lalu dicari di Semua kelas, Kelas 1, Kelas 2... dan divonis
            # `tidak_ditemukan`. Lihat juga pemulihan kelas di `cari_di_kelas_lain`.
            if (hasil.get("portal_akui") and not hasil.get("kelas_disapu")
                    and hasil.get("cari_konfirmasi_sah")
                    and hasil.get("status") != "sudah_pelayanan"):
                hasil["kelas_disapu"] = True
                if cari_di_kelas_lain(halaman, orang, hasil, jejak):
                    penuh(halaman, orang, hasil, jejak, muat_ulang=True)
                    return
            # Status yang sudah ditetapkan di dalam sana dipertahankan.
            if hasil.get("status") not in ("sudah_pelayanan", "tidak_ditemukan",
                                           "daftar_kosong"):
                hasil["status"] = ("daftar_kosong" if hasil.get("daftar_kosong")
                                   else "gagal_mulai")
            # "Tidak ada di daftar pelayanan" itu benar - murid yang BELUM
            # dikonfirmasi hadir memang belum ada di sana. Yang menentukan
            # justru daftar konfirmasi hadir, dan bila daftar ITU tidak pernah
            # tampil, tidak ada satu pun daftar yang benar-benar sudah dilihat.
            # Jadi ini kegagalan alat yang layak diulang, bukan vonis atas
            # muridnya.
            if (hasil.get("status") == "tidak_ditemukan"
                    and not hasil.get("cari_konfirmasi_sah")):
                hasil["keterangan"] += (" | daftar konfirmasi hadir TIDAK PERNAH"
                                        " tampil, jadi 'tidak ditemukan' bukan"
                                        " kesimpulan yang sah")
                hasil["status"] = ("daftar_kosong" if hasil.get("daftar_kosong")
                                   else "gagal_konfirmasi")
            # TIKET ITU BUKTI MURIDNYA ADA. Bila nomor tiket sudah terbit -
            # artinya portal BARU SAJA menerima pendaftarannya - lalu ia tetap
            # tak ketemu di kedua daftar, yang bermasalah pengindeksan portal,
            # bukan datanya. Divonis `tidak_ditemukan` ia tidak akan pernah
            # dicoba lagi; sebagai kegagalan sementara, percobaan berikutnya
            # datang beberapa detik kemudian dan biasanya sudah muncul.
            elif (hasil.get("status") == "tidak_ditemukan"
                    and (hasil.get("tiket") or "").strip()):
                hasil["keterangan"] += (f" | tiket {hasil['tiket']} sudah terbit,"
                                        " jadi muridnya ADA - portal belum"
                                        " mengindeksnya, layak dicoba lagi")
                hasil["status"] = "gagal_konfirmasi"
            # KETERANGAN PORTAL SENDIRI MENGALAHKAN "TIDAK KETEMU DI DAFTAR".
            #
            # Popup pendaftarannya berbunyi murid ini TELAH SELESAI DIPERIKSA -
            # menyebut puskesmas, sekolah, kelas, dan tanggalnya. Sesudah itu
            # ia tidak ketemu di daftar konfirmasi hadir maupun di ketiga tab
            # pelayanan, di kelasnya sendiri maupun di kelas lain. Yang lebih
            # masuk akal bukan "muridnya tidak ada" melainkan "daftarnya yang
            # tidak menampilkannya" - dan pemeriksaannya toh sudah terjadi.
            #
            # Sengaja diletakkan PALING BELAKANG: bila ada tanda alat yang
            # gagal - daftar tak pernah tampil, tabel masih memuat, tiket baru
            # terbit - vonis yang bisa diulang di atas yang menang lebih dulu.
            # Terjadi pada seorang murid (SD NEGERI LAGOA 09, 6 Sep):
            # divonis `tidak_ditemukan`, padahal barisnya ada di tab Selesai
            # Pemeriksaan dan portal sudah menyebut tanggal pemeriksaannya.
            elif (hasil.get("status") == "tidak_ditemukan"
                    and hasil.get("portal_dilayani")):
                hasil["keterangan"] += (" | TAPI portal sendiri menyebut murid ini"
                                        " sudah selesai diperiksa - keterangan itu"
                                        " yang dipakai, bukan 'tidak ketemu'")
                hasil["status"] = "sudah_pelayanan"
            return
        # Sampai di halaman detail belum berarti pemeriksaan sudah dimulai: di
        # sana masih ada tombol "Mulai Pemeriksaan", dan selama belum ditekan
        # seluruh form terkunci - daftar layanan terbaca, tapi tak satu pun
        # bisa diisi.
        if not layanan.mulai_pemeriksaan(halaman, orang, hasil, jejak):
            hasil["status"] = "gagal_mulai"
            return
    if "detail-pemeriksaan" not in halaman.url:
        hasil["keterangan"] += " | tidak sampai halaman daftar layanan"
        hasil["status"] = "gagal_detail"
        return
    layanan.petakan_layanan(halaman, hasil, jejak)
    layanan.sweep_layanan(halaman, orang, hasil, jejak)
