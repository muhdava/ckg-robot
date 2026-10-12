"""
Alur pendaftaran peserta (Dewasa/Lansia — pendaftaran individu).

Tahapan:
  1. buka halaman Cari/Daftarkan Individu
  2. klik "Daftar Baru"
  3. isi NIK -> "Cek NIK"
  4a. bila data sudah ada di sistem  -> klik "Gunakan Data"
  4b. bila belum ada                 -> isi manual: nama, tanggal lahir,
                                        jenis kelamin, nomor WhatsApp
  5. "Selanjutnya" -> halaman 2 (status nikah, pekerjaan, domisili)
  6. "Daftarkan"   -> modal "Berhasil Daftar" + nomor tiket

MODE UJI (config.MODE_UJI = True):
    semua langkah dijalankan KECUALI klik "Daftarkan".
    Jadi tidak ada data peserta yang benar-benar tercatat di portal.
"""
from __future__ import annotations

import json
import random
import re
from datetime import datetime

import config
import portal
from browser import simpan_gambar
from peserta import Peserta

# JS perekam struktur — dipakai untuk memetakan halaman yang belum dikenal
REKAM = """() => {
  const vis = e => e && e.offsetParent !== null;
  const rapi = s => (s || '').replace(/\\s+/g, ' ').trim();
  return {
    url: location.href,
    tombol: [...new Set([...document.querySelectorAll('button, input[type=button], input[type=submit], a[role=button]')]
              .filter(vis).map(b => rapi(b.innerText || b.value))
              .filter(t => t && t.length < 40))],
    tombol_mati: [...document.querySelectorAll('button[disabled], button[aria-disabled=true]')]
              .filter(vis).map(b => rapi(b.innerText)).filter(t => t && t.length < 40),
    isian: [...document.querySelectorAll('input,textarea')].filter(vis)
              .map(e => ({id: e.id||'', name: e.name||'', ph: e.placeholder||'', tipe: e.type||''})),
    dropdown: [...document.querySelectorAll('div')].filter(e => {
                const c = String(e.className||'');
                return vis(e) && c.includes('cursor-pointer') && c.includes('2.9rem');
              }).map(e => rapi(e.innerText).slice(0, 34)),
    checkbox: [...document.querySelectorAll('input[type=checkbox]')]
              .map(c => ({id: c.id||'', dicentang: c.checked})),
    label: [...document.querySelectorAll('label, p, span, div')].filter(vis)
              .filter(e => e.children.length === 0)
              .map(e => rapi(e.innerText)).filter(t => t && t.length < 45),
    teks: rapi(document.body.innerText).slice(0, 1500),
  };
}"""


class HasilDaftar(dict):
    """Hasil satu peserta: status, keterangan, nomor tiket, rekaman struktur."""


def _rekam(halaman, jejak: list, nama_tahap: str) -> None:
    data = halaman.evaluate(REKAM)
    data["tahap"] = nama_tahap
    jejak.append(data)


def _tombol_daftar(orang: Peserta) -> str:
    """
    Nama tombol kirim di halaman 3.

    Halaman 3 memakai DUA tombol berbeda, dan yang tampil tergantung jalur yang
    diambil di halaman 1. Pada jalur tanpa-NIK daftar individunya memang selalu
    kosong ("Data Individu Tidak Ditemukan") - tidak ada baris untuk dipilih,
    dan satu-satunya tombol yang hidup adalah "Daftarkan tanpa NIK".
    """
    return "Daftarkan tanpa NIK" if orang.tanpa_nik else "Daftarkan dengan NIK"


def _isi_identitas(halaman, orang: Peserta, hasil: dict) -> None:
    """
    Isi nama, tanggal lahir, dan jenis kelamin PESERTA di halaman 1.

    Dipakai dua jalur: peserta ber-NIK yang tidak ditemukan Dukcapil, dan bayi
    tanpa NIK yang memang tidak punya sumber lain selain berkasnya sendiri.

    `.first` bukan hiasan: begitu bagian Data Wali ikut terbuka, id
    "Nama Lengkap" ada DUA di halaman - milik peserta dan milik wali - dan
    tanpa `.first` Playwright menolak dengan galat "strict mode violation".
    """
    halaman.locator("#Nama\\ Lengkap").first.fill(orang.nama)

    lahir = orang.tanggal_lahir
    if lahir:
        galat = portal.isi_tanggal_lahir(halaman, lahir)
        if galat:
            hasil["keterangan"] += f" | tgl lahir GAGAL: {galat}"

    if orang.jenis_kelamin:
        if not portal.pilih_dropdown(halaman, "Jenis Kelamin", orang.jenis_kelamin):
            hasil["keterangan"] += " | jenis kelamin gagal dipilih"


def _buka_tanpa_nik(halaman, hasil: dict) -> str:
    """
    Centang "Tidak punya NIK" di halaman 1. Kembalikan "" bila beres.

    KEBERHASILANNYA DIBUKTIKAN DARI HALAMAN, bukan dari nilai balik centangnya.
    Begitu centang itu diterima, portal MENGHILANGKAN kolom #nik - itulah
    tandanya. Tanpa memeriksa itu, centang yang tercatat "berhasil" tapi tidak
    mengubah apa-apa akan meneruskan alurnya ke formulir ber-NIK dengan kolom
    NIK kosong, dan gejalanya baru muncul jauh di halaman 3 sebagai "tombol
    tak bisa diklik" - keluhan yang sama sekali tidak menunjuk sebabnya.
    """
    if not portal.centang(halaman, "tidak-punya-nik"):
        return "checkbox 'Tidak punya NIK' tidak bisa dicentang"
    if not portal.tunggu_siap(halaman, portal.js_tidak(portal.js_terlihat("#nik")),
                              config.TUNGGU_MUNCUL_MS, "kolom NIK menghilang"):
        return "sudah dicentang 'Tidak punya NIK' tapi kolom NIK masih ada"
    hasil["keterangan"] = "tanpa NIK: dicentang 'Tidak punya NIK'"
    return ""


def _isi_wali(halaman, orang: Peserta, hasil: dict) -> None:
    """
    Urus bagian "Data Wali" untuk peserta di bawah 18 tahun.

    BAGIAN INI BARU DIRENDER SESUDAH TANGGAL LAHIR DIISI - portal harus tahu
    umurnya dulu. Terbukti pada seorang balita: sebelum tanggal lahir
    terisi bagian itu tidak ada sama sekali, sesudahnya ada. Karena itu ia
    DITUNGGU, bukan langsung dibaca.

    Portal juga MENGISINYA SENDIRI dari Kartu Keluarga bila peserta diambil
    lewat "Gunakan Data" - NIK, nama, tanggal lahir, dan jenis kelamin ibunya
    muncul tanpa satu ketikan pun, dan kolomnya berubah menjadi tampilan mati.
    Mengetik di atas data yang sudah benar hanya merusaknya, jadi keadaan itu
    dikenali lebih dulu dan dibiarkan.

    SUMBER DATANYA dari `orang.wali`, bukan langsung dari peserta: bayi tanpa
    NIK punya wali sungguhan di berkasnya, sedangkan balita biasa tidak - dan
    kedua kebiasaan itu dipisahkan di satu tempat, di kelas Peserta.
    """
    wali = orang.wali
    if not portal.tunggu_siap(halaman, portal.js_ada_teks("Data Wali"),
                              config.TUNGGU_MUNCUL_MS, "bagian Data Wali muncul"):
        hasil["keterangan"] += " | wali: bagiannya tidak muncul"
        return

    if halaman.evaluate(portal.JS_WALI_TERISI):
        hasil["keterangan"] += " | wali: sudah diisi portal dari KK"
        return

    medan = halaman.evaluate(portal.JS_MEDAN_WALI) or []
    if not medan:
        hasil["keterangan"] += " | wali: kolomnya tidak terbaca"
        return

    # Diarahkan lewat NOMOR URUT, bukan id. Kolom wali memakai id yang SAMA
    # dengan kolom peserta ("Nama Lengkap"), jadi memilih lewat id selalu
    # mengenai milik peserta - kolom wali tetap kosong sementara laporannya
    # mengaku berhasil. Persis itu yang terjadi pada dua balita.
    semua = halaman.locator("input, select, textarea")
    terisi, gagal = [], []
    for m in medan:
        if m["terkunci"] or m["jenis"] in ("checkbox", "radio") or (m["nilai"] or "").strip():
            continue
        petunjuk = f"{m['id']} {m['name']} {m['placeholder']}".lower()
        nilai = (wali["nik"] if "nik" in petunjuk
                 else wali["nama"] if "nama" in petunjuk
                 else orang.no_hp_bersih if ("whatsapp" in petunjuk or "hp" in petunjuk)
                 else "")
        if not nilai:
            continue
        try:
            semua.nth(m["urutan"]).fill(nilai)
            terisi.append(m["id"] or m["name"])
        except Exception as e:
            gagal.append(f"{m['id'] or m['name']}({type(e).__name__})")

    # Tanggal lahir dan jenis kelamin wali BUKAN kolom ketik, jadi tidak pernah
    # muncul di daftar di atas - dan dulu keduanya tak tersentuh sama sekali.
    # Pemicunya dibedakan dari milik peserta lewat BESAR-KECIL HURUF: portal
    # menulis "Pilih Tanggal Lahir" / "Pilih Jenis Kelamin" untuk wali, dan
    # huruf kecil untuk peserta.
    if wali["tanggal"]:
        galat = portal.isi_tanggal_lahir(halaman, wali["tanggal"],
                                         teks_pemicu="Pilih Tanggal Lahir")
        (terisi if not galat else gagal).append(
            "Tanggal Lahir Wali" if not galat else f"Tanggal Lahir Wali({galat})")
    if wali["kelamin"]:
        ok = portal.pilih_dropdown_persis(halaman, "Pilih Jenis Kelamin",
                                          wali["kelamin"], timeout=6_000)
        (terisi if ok else gagal).append("Jenis Kelamin Wali")

    for kandidat in ("phone-sama", "sama-dengan-peserta", "nomorSama"):
        if portal.centang(halaman, kandidat):
            terisi.append(kandidat)
            break

    halaman.wait_for_timeout(600)
    # Diperiksa ULANG, bukan dipercaya. Laporan "diisi dari data peserta" yang
    # ternyata tidak mengisi apa pun jauh lebih merugikan daripada laporan gagal.
    sisa = [m["id"] or m["name"] or m["placeholder"]
            for m in (halaman.evaluate(portal.JS_MEDAN_WALI) or [])
            if not m["terkunci"] and m["jenis"] not in ("checkbox", "radio")
            and not (m["nilai"] or "").strip()]
    hasil["keterangan"] += f" | wali: terisi {terisi}" if terisi else " | wali: tak ada yang terisi"
    if gagal:
        hasil["keterangan"] += f" | wali GAGAL: {gagal}"
    # Kalender dan dropdown BUKAN <input>, jadi tidak pernah terbaca oleh
    # pemeriksaan di atas. Selama teks ajakannya masih ada di halaman, keduanya
    # jelas belum terisi - dan itulah yang lolos pada dua balita.
    for ajakan in ("Pilih Tanggal Lahir", "Pilih Jenis Kelamin"):
        if halaman.evaluate(portal.js_ada_teks(ajakan)):
            sisa.append(ajakan)
    if sisa:
        hasil["keterangan"] += f" | wali MASIH KOSONG: {sisa}"


def _tandai_dilayani(halaman, hasil: dict, dari: str) -> None:
    """
    Tandai peserta yang ditolak karena SUDAH dilayani - beserta DI MANA.

    Popup "Individu sudah menerima layanan" menyebutkan sendiri seluruh
    rinciannya: puskesmas pemeriksa, sekolah, kelas, tanggal, dan layanannya.
    Tiga vonis yang bisa keluar dari situ, dan bedanya menentukan tindakan:

      ckg_sekolah        diperiksa lewat jalur CKG SEKOLAH, bukan CKG Umum.
                         Orangnya sudah selesai, hanya lewat pintu yang lain.
                         Diperiksa LEBIH DULU daripada puskesmasnya: jalur
                         layanan itulah yang menentukan penggolongannya.
      puskesmas_berbeda  diperiksa puskesmas LAIN lewat CKG Umum. Catatannya
                         milik mereka; tidak ada yang bisa dikerjakan di sini.
      sudah_pelayanan    selebihnya - sudah dilayani di puskesmas kita sendiri.

    KENAPA PERLU DIPISAH. Ketiganya dulu dilaporkan sama: `sudah_pelayanan`,
    tanpa satu pun keterangan tentang siapa yang memeriksanya. Peserta yang
    ternyata sudah diperiksa lewat CKG Sekolah atau oleh puskesmas lain jadi
    tidak bisa dipilah saat rekap, padahal justru merekalah yang perlu
    dikeluarkan dari hitungan sasaran. Keputusan pengguna, 7 Sep.

    Puskesmas pembandingnya dibaca dari kepala halaman portal. Bila salah satu
    namanya tidak terbaca, vonis `puskesmas_berbeda` TIDAK dijatuhkan - lihat
    `portal.puskesmas_lain`.
    """
    rincian = portal.rincian_popup(halaman)
    layanan = (rincian.get("layanan") or "").strip()
    pemeriksa = (rincian.get("puskesmas pemeriksa") or "").strip()

    lain = portal.puskesmas_lain(halaman, pemeriksa)
    # LAYANANNYA DULU, BARU PUSKESMASNYA. Peserta yang sudah diperiksa lewat
    # CKG Sekolah tetap `ckg_sekolah` walau yang memeriksanya puskesmas lain -
    # yang menentukan penggolongannya adalah JALUR layanannya, sebab dari situ
    # sasaran CKG Umum dihitung. Nama puskesmas pemeriksanya tidak hilang: ia
    # tetap tercetak di keterangan, dan diberi tanda tersendiri bila memang
    # bukan puskesmas kita. Keputusan pengguna, 7 Sep.
    if re.search(r"ckg\s*sekolah", layanan, re.I):
        status = "ckg_sekolah"
    elif lain:
        status = "puskesmas_berbeda"
    else:
        status = "sudah_pelayanan"

    urut = ("puskesmas pemeriksa", "sekolah", "kelas", "tanggal pemeriksaan", "layanan")
    isi = ", ".join(f"{k}: {rincian[k]}" for k in urut if rincian.get(k))
    if lain and status == "ckg_sekolah":
        isi += " - DIPERIKSA PUSKESMAS LAIN"
    hasil.update(status=status,
                 keterangan=(hasil["keterangan"] + f" | {dari}"
                             + (f" ({isi})" if isi else "")).lstrip(" |"))


def daftar_peserta(halaman, orang: Peserta, jejak: list | None = None) -> HasilDaftar:
    """Daftarkan satu peserta. Kembalikan HasilDaftar."""
    jejak = jejak if jejak is not None else []
    hasil = HasilDaftar(nama=orang.nama, nik=orang.nik, baris=orang.baris_csv,
                        status="belum", keterangan="", tiket="")

    # ---------------------------------------------------------------- 1 & 2
    halaman.goto(config.HAL_PENDAFTARAN, wait_until="domcontentloaded")
    portal.tunggu_siap(halaman, portal.js_ada_tombol("Daftar Baru"), 2000, "buka halaman daftar")

    if not portal.klik_tombol(halaman, "Daftar Baru"):
        hasil.update(status="gagal", keterangan="tombol 'Daftar Baru' tidak ditemukan")
        return hasil
    portal.tunggu_siap(halaman, portal.js_terlihat("#nik"), 1500, "formulir terbuka")

    # ---------------------------------------------------------------- 3. NIK
    # Bayi tanpa NIK punya jalannya sendiri: tidak ada yang bisa dicek ke
    # Dukcapil, jadi tidak ada "Cek NIK" dan tidak ada "Gunakan Data" -
    # identitasnya HANYA berasal dari berkas.
    if orang.tanpa_nik:
        galat = _buka_tanpa_nik(halaman, hasil)
        if galat:
            hasil.update(status="gagal", keterangan=galat)
            simpan_gambar(halaman, f"tanpanik_{orang.baris_csv}")
            return hasil
        _isi_identitas(halaman, orang, hasil)
        _rekam(halaman, jejak, "3_tanpa_nik")
    else:
        try:
            halaman.locator("#nik").fill(orang.nik)
        except Exception as e:
            hasil.update(status="gagal", keterangan=f"kolom NIK tidak bisa diisi: {type(e).__name__}")
            return hasil

        portal.klik_tombol(halaman, "Cek NIK")
        # Cek NIK berakhir pada salah satu dari tiga keadaan; menunggu ketiganya
        # sekaligus jauh lebih cepat daripada menunggu selebar yang paling lambat.
        portal.tunggu_siap(halaman, portal.js_atau(
            portal.js_ada_tombol("Gunakan Data"),
            portal.js_terisi(r"#Nama\ Lengkap"),
            portal.js_ada_teks("tidak valid"),
            # Keadaan KEEMPAT, yang dulu tidak ikut ditunggu: peserta sudah
            # dilayani. Tanpa ini penantiannya selalu habis penuh lebih dulu,
            # padahal jawabannya sudah ada di layar sejak detik pertama.
            portal.SUDAH_DILAYANI_JS), 2500, "jawaban Cek NIK")
        _rekam(halaman, jejak, "3_setelah_cek_nik")

        # data tidak valid -> lewati peserta ini
        # DUA popup bisa muncul TEPAT DI SINI, dan keduanya menutupi seluruh
        # formulir. Tanpa ditengok di sini, langkah berikutnya menabraknya dan
        # gejalanya menyesatkan: datepicker "tak bisa diklik", lalu Selanjutnya
        # "tidak bisa diklik" - dua keluhan berbeda untuk satu sebab.
        #
        # 1. "Terjadi kesalahan - Belum bisa memproses data. Silakan coba lagi."
        #    Portal sendiri menyuruh mengulang, jadi Cek NIK diulang sekali.
        pesan = portal.tutup_popup_galat(halaman)
        if pesan:
            hasil["keterangan"] += f" | popup galat sesudah Cek NIK: {pesan}"
            portal.klik_tombol(halaman, "Cek NIK", timeout=4_000)
            portal.tunggu_siap(halaman, portal.js_atau(
                portal.js_ada_tombol("Gunakan Data"),
                portal.js_terisi(r"#Nama\ Lengkap"),
                portal.js_ada_teks("tidak valid")), 2500, "jawaban Cek NIK (ulang)")
            pesan2 = portal.tutup_popup_galat(halaman)
            if pesan2:
                hasil.update(status="gagal",
                             keterangan=hasil["keterangan"] + f" | masih galat sesudah diulang: {pesan2}")
                simpan_gambar(halaman, f"galat_ceknik_{orang.baris_csv}")
                return hasil

        # 2. Peserta memang sudah dilayani.
        if portal.sudah_dilayani(halaman):
            _tandai_dilayani(halaman, hasil, "ditolak sesudah Cek NIK: sudah dilayani")
            return hasil

        if portal.teks_ada(halaman, "tidak valid"):
            hasil.update(status="tidak_valid", keterangan="NIK/data dinyatakan tidak valid")
            return hasil

        # ---------------------------------------------------------------- 4. identitas
        if portal.klik_tombol(halaman, "Gunakan Data", timeout=4_000):
            hasil["keterangan"] = "data sudah ada di sistem (Gunakan Data)"
            portal.tunggu_siap(halaman, portal.js_terisi(r"#Nama\ Lengkap"), 1500,
                               "data Dukcapil termuat")
        else:
            hasil["keterangan"] = "isi manual"
            _isi_identitas(halaman, orang, hasil)

    # Nomor WhatsApp: pastikan isinya benar-benar angka.
    # Bukan sekadar "isi bila kosong" — kolom ini pernah tercemar ketikan
    # tanggal lahir, dan nilai salah itu tidak akan tergantikan bila hanya
    # dicek kosong/tidaknya.
    try:
        kolom_hp = halaman.locator("#No\\ Whatsapp")
        if kolom_hp.count():
            sekarang = (kolom_hp.input_value() or "").strip()
            if not sekarang.isdigit():
                kolom_hp.fill("")
                kolom_hp.fill(orang.no_hp_bersih)
    except Exception:
        pass

    _rekam(halaman, jejak, "4_identitas_terisi")

    # ------------------------------------------------------ 4c. data wali
    # Portal: "Pengisian data wali wajib bagi peserta balita dan yang tidak
    # memiliki NIK, serta DIANJURKAN bagi peserta lansia."
    #
    # Untuk lansia bagian wali ikut muncul, dan selama ia kosong tombol
    # "Selanjutnya" tetap mati — gejalanya menyerupai "tombol tidak ada".
    # Karena data walinya tidak kita punya, dipakai jalan resmi portal:
    # centang "Daftarkan tanpa data wali".
    if (not orang.tanpa_nik and (orang.usia or 99) >= 18
            and halaman.locator("#noWali").count()):
        if portal.centang(halaman, "noWali"):
            hasil["keterangan"] += " | wali: daftarkan tanpa data wali"
        else:
            hasil["keterangan"] += " | GAGAL centang 'tanpa data wali'"
        halaman.wait_for_timeout(500)

    # Peserta di bawah 18 tahun WAJIB mengisi data wali. Balita 0-6 selalu.
    # `orang.usia or 99` TIDAK BOLEH dipakai: umur 0 itu falsy, jadi bayi nol
    # tahun akan dianggap 99 dan bagian walinya dilewati sama sekali.
    umur = 99 if orang.usia is None else orang.usia
    # Tanpa NIK, data wali WAJIB berapa pun umurnya - itu satu-satunya
    # identitas yang dipegang portal atas peserta ini.
    if umur < 18 or orang.tanpa_nik:
        _isi_wali(halaman, orang, hasil)
        _rekam(halaman, jejak, "4c_data_wali")

    # ------------------------------------------------ 4b. tanggal pemeriksaan
    # Tanpa ini tombol "Selanjutnya" tetap non-aktif.
    # Kalender memakai tombol "<tanggal> <sisa kuota>"; kuota 0 (biasanya
    # Sabtu/Minggu) tidak bisa dipilih, jadi diambil hari terdekat yang ada kuotanya.
    hari = portal.pilih_tanggal_pemeriksaan(halaman)
    if hari is None:
        hasil.update(status="gagal",
                     keterangan=hasil["keterangan"] + " | tidak ada tanggal pemeriksaan berkuota")
        simpan_gambar(halaman, f"tgl_periksa_{orang.baris_csv}")
        return hasil
    hasil["keterangan"] += f" | tgl periksa: {hari}"
    _rekam(halaman, jejak, "4b_tanggal_pemeriksaan_dipilih")

    # ---------------------------------------------------------------- 5. halaman 2
    if not portal.klik_tombol(halaman, "Selanjutnya", timeout=8_000):
        # Sebelum menyerah: popup galat portal menutupi halaman dan membuat
        # tombol tidak bisa diklik, jadi gejalanya menyerupai "tombol tak ada".
        pesan = portal.tutup_popup_galat(halaman)
        if pesan:
            hasil["keterangan"] += f" | popup galat: {pesan}"
        if not (pesan and portal.klik_tombol(halaman, "Selanjutnya", timeout=8_000)):
            # Sebelum divonis gagal: portal mungkin menolak karena pesertanya
            # memang sudah dilayani, dan popupnya yang menutupi tombol.
            if portal.sudah_dilayani(halaman):
                _tandai_dilayani(halaman, hasil, "sudah dilayani (popup menutupi halaman 1)")
                return hasil
            # Simpan bukti: tanpa ini kegagalan di sini tidak meninggalkan jejak
            # apa pun, dan justru inilah yang paling perlu diperiksa.
            _rekam(halaman, jejak, "5x_selanjutnya_gagal")
            # Portal menolak isi namanya. Tombolnya tidak akan pernah hidup,
            # jadi ini bukan kegagalan yang layak diulang - berkasnya yang
            # harus diperbaiki. Statusnya pun harus jujur: tidak_valid.
            if portal.teks_ada(halaman, "Nama hanya dapat menggunakan huruf"):
                hasil.update(status="tidak_valid",
                             keterangan=hasil["keterangan"]
                             + f" | nama ditolak portal: {orang.nama!r}")
                simpan_gambar(halaman, f"nama_{orang.baris_csv}")
                return hasil
            gambar = simpan_gambar(halaman, f"selanjutnya_{orang.baris_csv}")
            # Tombol MATI bergejala sama persis dengan tombol TIDAK ADA, jadi
            # yang dilaporkan adalah calon penyebabnya: isian wajib yang masih
            # kosong. Sudah dua kali penyebabnya beda — tanggal pemeriksaan,
            # lalu checkbox "Daftarkan tanpa data wali" pada peserta lansia.
            belum = halaman.evaluate(
                """() => {
                  const rapi = s => (s || '').replace(/\\s+/g, ' ').trim();
                  const vis = e => e && e.offsetParent !== null;
                  const dropdown = [...document.querySelectorAll('div')]
                    .filter(e => { const c = String(e.className || '');
                       return vis(e) && c.includes('cursor-pointer')
                           && c.includes('2.9rem') && /^Pilih /i.test(rapi(e.innerText)); })
                    .map(e => rapi(e.innerText).slice(0, 30));
                  const centang = [...document.querySelectorAll('input[type=checkbox]')]
                    .filter(c => vis(c) && !c.checked)
                    .map(c => {
                      const wadah = c.closest('label, div');
                      const teks = rapi(wadah && wadah.innerText).slice(0, 40);
                      return (c.id || c.getAttribute('name') || '?') + (teks ? ` (${teks})` : '');
                    });
                  const isian = [...document.querySelectorAll('input')]
                    .filter(e => vis(e) && e.type !== 'checkbox' && !e.value.trim()
                                 && e.id !== 'searchNik')
                    .map(e => e.id || e.getAttribute('name') || '?');
                  return {dropdown, centang, isian};
                }"""
            )
            rincian = " | ".join(
                f"{nama} belum terisi: {nilai}"
                for nama, nilai in (("dropdown", belum["dropdown"]),
                                    ("checkbox", belum["centang"]),
                                    ("kolom", belum["isian"])) if nilai)
            hasil.update(status="gagal",
                         keterangan=hasil["keterangan"] + " | 'Selanjutnya' tidak bisa diklik"
                         + (f" | {rincian}" if rincian else ""))
            print(f"        bukti -> {gambar}")
            return hasil
    portal.tunggu_siap(halaman, portal.js_atau(
        portal.js_ada_teks("Kuota Pemeriksaan Habis"),
        portal.js_ada_tombol("Lanjutkan"),
        portal.TIDAK_VALID_JS,
        portal.js_ada_teks("Pilih status pernikahan")), 2500, "jawaban halaman 1")

    # Popup "Kuota Pemeriksaan Habis" -> Lanjut.
    # Muncul lebih dulu bila tanggal yang dipilih kuotanya 0. Harus ditangani
    # sebelum popup berikutnya, kalau tidak alurnya mentok di sini.
    if portal.lewati_popup_kuota(halaman):
        hasil["keterangan"] += " | kuota habis: Lanjut"
        portal.tunggu_siap(halaman, portal.js_atau(
            portal.js_ada_tombol("Lanjutkan"),
            portal.TIDAK_VALID_JS), 2000, "sesudah popup kuota")

    # popup "Data peserta valid" -> Lanjutkan
    portal.klik_tombol(halaman, "Lanjutkan", timeout=5_000)
    portal.tunggu_siap(halaman, portal.js_atau(
        portal.js_ada_teks("Pilih status pernikahan"),
        portal.SUDAH_DILAYANI_JS,
        portal.TIDAK_VALID_JS), 1500, "halaman 2 terbuka")

    if portal.sudah_dilayani(halaman):
        _tandai_dilayani(halaman, hasil, "portal: sudah menerima (pe)layanan")
        return hasil
    if portal.data_tidak_valid(halaman):
        # Keterangan yang sudah terkumpul JANGAN ditimpa. Dulu barisnya
        # `keterangan="ditolak setelah Selanjutnya"`, dan hasilnya baris 1
        # berkas balita tanpa NIK (9 Sep) melaporkan HANYA kalimat itu -
        # tanpa jejak centang tanpa-NIK, tanpa daftar kolom wali yang terisi,
        # tanpa tanggal periksa. Yang paling dibutuhkan waktu menelusuri justru
        # yang terhapus. Layarnya ikut disimpan, sebab pesan penolakannya hanya
        # ada di popup dan tidak pernah masuk rekaman struktur halaman.
        pesan = portal.pesan_penolakan(halaman)
        simpan_gambar(halaman, f"ditolak_{orang.baris_csv}")
        hasil.update(status="tidak_valid",
                     keterangan=hasil["keterangan"] + " | ditolak setelah Selanjutnya"
                     + (f" - portal bilang: {pesan!r}" if pesan else ""))
        return hasil

    _rekam(halaman, jejak, "5_halaman_2")

    # ------------------------------------------------------- 5b. isi halaman 2
    isi_halaman2(halaman, orang, hasil, jejak)

    # ------------------------------------------------- 6. lanjut dari halaman 2
    # DUA BENTUK FORMULIR, dan keduanya dilayani.
    #
    #   lama : halaman 2 bertombol "Selanjutnya" -> halaman 3 "List Data
    #          Individu" dengan "Pilih" lalu "Daftarkan dengan NIK".
    #   baru : halaman 3 DIHAPUS. Halaman 2 langsung bertombol "Daftarkan",
    #          dan menekannya itulah yang mendaftarkan. Bilah kemajuannya pun
    #          tinggal dua ruas. Terlihat pertama kali 29 Sep 2026: macro terus
    #          menunggu "Selanjutnya" yang tak pernah ada, lalu melaporkan
    #          "'Selanjutnya' halaman 2 tidak aktif" tiga kali berturut.
    #
    # Yang tampil DITANYA dulu, bukan ditebak lewat tenggat: "Daftarkan"
    # dicocokkan PERSIS, sebab pencocokan longgar juga mengenai "Daftarkan
    # dengan NIK" di halaman 3 bentuk lama.
    portal.tunggu_siap(halaman, portal.js_atau(
        portal.js_ada_tombol("Selanjutnya"), _JS_TOMBOL_DAFTARKAN), 10_000,
        "tombol kirim halaman 2")
    if (halaman.evaluate(_JS_TOMBOL_DAFTARKAN)
            and not halaman.evaluate(portal.js_ada_tombol("Selanjutnya"))):
        hasil["keterangan"] += " | formulir 2 halaman: langsung Daftarkan"
        _rekam(halaman, jejak, "6_halaman2_langsung_daftarkan")
        if config.MODE_UJI:
            hasil.update(status="uji",
                         keterangan=hasil["keterangan"] + " | MODE UJI: berhenti sebelum 'Daftarkan'")
            simpan_gambar(halaman, f"uji_{orang.baris_csv}_{orang.nama[:18]}")
            return hasil
        daftarkan(halaman, orang, hasil, jejak, langsung=True)
        return hasil

    if portal.klik_tombol(halaman, "Selanjutnya", timeout=10_000):
        portal.tunggu_siap(halaman, portal.js_atau(
            portal.js_ada_tombol("Lanjutkan"),
            portal.js_ada_tombol(_tombol_daftar(orang)),
            portal.SUDAH_DILAYANI_JS), 2500, "jawaban halaman 2")
        # Jawaban portal atas halaman 2 bisa BUKAN halaman 3, melainkan popup
        # "Individu sudah menerima layanan" (tombolnya "Kembali"/"Cari
        # Individu"). Tanpa pemeriksaan di sini alurnya jalan terus ke
        # `daftarkan()`, tombolnya tertutup popup, dan peserta yang sebenarnya
        # sudah beres dilaporkan gagal di halaman 3 - persis kasus h3_*.
        if portal.sudah_dilayani(halaman):
            _tandai_dilayani(halaman, hasil, "sudah dilayani (jawaban halaman 2)")
            return hasil
        portal.klik_tombol(halaman, "Lanjutkan", timeout=4_000)
        portal.tunggu_siap(halaman, portal.js_ada_tombol(_tombol_daftar(orang)),
                           1200, "halaman 3 terbuka")
        if portal.sudah_dilayani(halaman):
            _tandai_dilayani(halaman, hasil, "sudah dilayani (sebelum halaman 3)")
            return hasil
        _rekam(halaman, jejak, "6_setelah_halaman2")
    else:
        # BERHENTI di sini. Dulu alurnya diteruskan ke `daftarkan()`, padahal
        # halaman 3 belum terbuka � akibatnya kegagalan dilaporkan sebagai
        # "tombol Daftarkan dengan NIK tak bisa diklik", yang menyesatkan.
        if portal.sudah_dilayani(halaman):
            _tandai_dilayani(halaman, hasil, "sudah dilayani (popup menutupi halaman 2)")
            return hasil
        # Popup galat juga menutupi tombolnya; ditutup lalu dicoba sekali lagi.
        pesan = portal.tutup_popup_galat(halaman)
        if pesan:
            hasil["keterangan"] += f" | popup galat halaman 2: {pesan}"
            if portal.klik_tombol(halaman, "Selanjutnya", timeout=8_000):
                portal.tunggu_siap(halaman, portal.js_ada_tombol(_tombol_daftar(orang)),
                                   2500, "halaman 3 sesudah popup ditutup")
                _rekam(halaman, jejak, "6_setelah_halaman2")
                if not config.MODE_UJI:
                    daftarkan(halaman, orang, hasil, jejak)
                return hasil
        _rekam(halaman, jejak, "6x_halaman2_gagal")
        simpan_gambar(halaman, f"halaman2_{orang.baris_csv}")
        hasil.update(status="gagal",
                     keterangan=hasil["keterangan"] + " | 'Selanjutnya' halaman 2 tidak aktif")
        return hasil

    # ---------------------------------------------------------------- 7. daftarkan
    # Berhenti di sini saat MODE UJI: dua tombol pada halaman 3 ("Pilih" dan
    # "Daftarkan dengan NIK") sama-sama mencatat peserta sungguhan.
    if config.MODE_UJI:
        hasil.update(status="uji", keterangan=hasil["keterangan"] + " | MODE UJI: berhenti sebelum 'Daftarkan'")
        simpan_gambar(halaman, f"uji_{orang.baris_csv}_{orang.nama[:18]}")
        return hasil

    daftarkan(halaman, orang, hasil, jejak)
    return hasil


# Tombol "Daftarkan" SAJA - bukan "Daftarkan dengan NIK"/"tanpa NIK".
_JS_TOMBOL_DAFTARKAN = ("() => [...document.querySelectorAll('button')].some(b => "
                        "b.offsetParent !== null && "
                        "(b.innerText || '').replace(/\\s+/g, ' ').trim() === 'Daftarkan')")


def daftarkan(halaman, orang: Peserta, hasil: dict, jejak: list,
              langsung: bool = False) -> None:
    """
    Halaman 3 "List Data Individu" -> pendaftaran sungguhan.

    Portal menampilkan individu yang cocok berdasarkan nama, tanggal lahir,
    dan jenis kelamin. Yang dipilih HARUS baris ber-NIK sama persis � nama dan
    tanggal lahir bisa kembar antar orang, NIK tidak. Bila tak ada yang cocok,
    barulah dipakai "Daftarkan dengan NIK".

    Pada jalur TANPA NIK tidak ada satu pun dari itu: daftarnya selalu kosong
    dan tombolnya "Daftarkan tanpa NIK".
    """
    # `langsung=True`: formulir bentuk baru - halaman 3 sudah tidak ada, jadi
    # tidak ada baris untuk "Pilih", dan tombol kirimnya "Daftarkan" saja.
    kirim = "Daftarkan" if langsung else _tombol_daftar(orang)

    # Langkah 1: tandai baris yang NIK-nya sama persis.
    # "Pilih" dan "Daftarkan dengan NIK" itu BERURUTAN, bukan dua pilihan:
    # sesudah ditekan, tombol baris berubah jadi "Dipilih" dan tombol kirim
    # tetap menunggu di bawah.
    #
    # DILEWATI SAMA SEKALI pada jalur tanpa-NIK. Yang dicari di sini adalah
    # baris ber-NIK sama persis, dan peserta ini tidak punya NIK - jadi
    # pencariannya dijamin nihil, dan melaporkannya "tidak ada" hanya menaruh
    # keterangan menakutkan pada peserta yang sebenarnya baik-baik saja.
    baris = halaman.locator(f"xpath=//tr[td[normalize-space(.)={orang.nik!r}]]")
    terpilih = False
    if orang.tanpa_nik or langsung:
        pass
    elif baris.count():
        tombol = baris.first.locator(
            "xpath=.//button[normalize-space(.)='Pilih' or normalize-space(.)='Dipilih']"
        )
        if tombol.count():
            try:
                if (tombol.first.inner_text() or "").strip() != "Dipilih":
                    tombol.first.click(timeout=8_000)
                    # Tombolnya berubah jadi "Dipilih" begitu portal menerima —
                    # itu tandanya, bukan lewatnya sekian detik.
                    portal.tunggu_siap(halaman, portal.js_ada_tombol("Dipilih"),
                                       1200, "peserta dipilih")
                terpilih = True
            except Exception:
                pass
    if not orang.tanpa_nik and not langsung:
        hasil["keterangan"] += " | baris NIK: " + ("dipilih" if terpilih else "tidak ada")

    # Langkah 2: kirim. Ini yang benar-benar mendaftarkan.
    if not portal.klik_tombol_persis(halaman, kirim, timeout=8_000):
        # Klik yang gagal di sini hampir selalu berarti ada popup di atasnya,
        # bukan tombolnya yang hilang. Dua yang sudah terbukti:
        #   "Data peserta tidak valid"  -> data ditolak portal, peserta dilewati
        #   "Terjadi kesalahan"         -> galat sesaat, layak dicoba lagi
        if portal.data_tidak_valid(halaman):
            portal.klik_tombol_persis(halaman, "Periksa Kembali", timeout=3_000)
            hasil.update(status="tidak_valid",
                         keterangan=hasil["keterangan"] + " | ditolak saat mendaftarkan")
            return
        #   "Individu sudah menerima layanan" -> bukan gagal sama sekali;
        #   peserta memang sudah beres. Tombolnya "Kembali"/"Cari Individu",
        #   jadi `tutup_popup_galat` tidak mengenalinya - harus ditanya sendiri.
        if portal.sudah_dilayani(halaman):
            _tandai_dilayani(halaman, hasil, "sudah dilayani (popup menutupi halaman 3)")
            return
        pesan = portal.tutup_popup_galat(halaman)
        if pesan:
            hasil["keterangan"] += f" | popup galat: {pesan}"
        if not (pesan and portal.klik_tombol_persis(halaman, kirim, timeout=8_000)):
            hasil.update(status="gagal",
                         keterangan=hasil["keterangan"] + f" | tombol {kirim!r} tak bisa diklik")
            simpan_gambar(halaman, f"h3_{orang.baris_csv}")
            return

    # Sesudah Daftarkan: entah tiket terbit, entah popup persetujuan, entah
    # penolakan. Ketiganya ditunggu bersamaan.
    portal.tunggu_siap(halaman, portal.js_atau(
        portal.js_ada_teks("No. Tiket"),
        portal.js_ada_tombol("Lanjutkan"),
        portal.js_ada_tombol("Oke"),
        portal.SUDAH_DILAYANI_JS,
        portal.TIDAK_VALID_JS), 3000, "jawaban Daftarkan")
    # Setelah "Pilih"/"Daftarkan dengan NIK" masih mungkin ada konfirmasi.
    # Dicocokkan PERSIS � "Daftarkan" secara longgar juga cocok dengan
    # "Daftarkan dengan NIK", yaitu tombol yang barusan ditekan.
    # Pada bentuk baru "Daftarkan" adalah tombol yang BARU SAJA ditekan. Bila
    # portalnya lambat dan formulirnya masih tampil, mencocokkannya lagi di
    # sini berarti mengirim pendaftaran dua kali - jadi dikeluarkan dari daftar.
    for lanjut in (("Ya", "Lanjutkan") if langsung else ("Daftarkan", "Ya", "Lanjutkan")):
        if portal.klik_tombol_persis(halaman, lanjut, timeout=3_000):
            hasil["keterangan"] += f" | konfirmasi: {lanjut}"
            portal.tunggu_siap(halaman, portal.js_atau(
                portal.js_ada_teks("No. Tiket"),
                portal.SUDAH_DILAYANI_JS), 2500, "tiket terbit")
            break
    _rekam(halaman, jejak, "7_setelah_daftarkan")

    if portal.sudah_dilayani(halaman):
        _tandai_dilayani(halaman, hasil, "ditolak: sudah dilayani")
        return
    if portal.sudah_terdaftar(halaman):
        hasil.update(status="sudah_terdaftar",
                     keterangan=hasil["keterangan"] + " | portal: individu sudah terdaftar")
        return

    # Nomor tiket dibaca dari label "No. Tiket:" pada popup berhasil � bukan
    # dari kata "tiket" mana pun, sebab halaman ini juga memuat "Nomor Tiket"
    # (jenis pencarian) dan "tiket CKG" pada kalimat petunjuk.
    #
    # Dibaca BERULANG: modal berhasil-daftar kadang terlambat muncul, dan
    # pembacaan sekali jalan membuat peserta yang sebenarnya terdaftar
    # tercatat sebagai "tanpa tiket".
    pola = re.compile(r"No\.?\s*Tiket\s*:?\s*([A-Za-z0-9]+-[A-Za-z0-9]+)", re.I)
    sisa = config.TUNGGU_TIKET_MS
    isi = ""
    while sisa > 0:
        isi = halaman.inner_text("body")
        gagal_simpan = portal.pendaftaran_gagal(halaman)
        if gagal_simpan:
            simpan_gambar(halaman, f"daftar_gagal_{orang.baris_csv}")
            portal.klik_tombol_persis(halaman, "Tutup", timeout=3_000)
            # `gagal`, bukan `tanpa_tiket`: portal SENDIRI yang bilang simpannya
            # gagal dan minta dicoba lagi - keduanya sama-sama diulang, tapi
            # hanya yang ini menyebut sebab yang sebenarnya.
            hasil.update(status="gagal",
                         keterangan=hasil["keterangan"] + f" | portal: {gagal_simpan}")
            return
        m = pola.search(isi)
        if m:
            hasil["tiket"] = m.group(1)
            if sisa < config.TUNGGU_TIKET_MS - 3000:      # terbitnya memang lama
                hasil["keterangan"] += (" | tiket terbit setelah "
                                        f"{(config.TUNGGU_TIKET_MS - sisa) // 1000}s")
            break
        if portal.sudah_dilayani(halaman):
            _tandai_dilayani(halaman, hasil, "ditolak: sudah dilayani")
            return
        # Lihat catatan yang sama di `sekolah.daftar_murid`: terdaftar bukan
        # gagal, dan menunggunya sampai habis hanya menghasilkan "tanpa_tiket".
        if portal.sudah_terdaftar(halaman):
            hasil.update(status="sudah_terdaftar",
                         keterangan=hasil["keterangan"] + " | portal: individu sudah terdaftar")
            return
        # Anjuran memutakhirkan data ke Dukcapil muncul menutupi modal tiket.
        # Pendaftarannya sendiri berhasil, jadi cukup ditutup lalu lanjut baca.
        info = portal.tutup_popup_info(halaman)
        if info:
            hasil["keterangan"] += f" | pemberitahuan dilewati: {info}"
            simpan_gambar(halaman, f"info_{orang.baris_csv}")
        halaman.wait_for_timeout(400)
        sisa -= 400
    if not hasil["tiket"]:
        # Tanpa nomor tiket, peserta tidak bisa dilanjutkan ke tahap layanan.
        hasil.update(status="tanpa_tiket",
                     keterangan=hasil["keterangan"]
                     + f" | tiket tidak terbaca dalam {config.TUNGGU_TIKET_MS // 1000}s")
        simpan_gambar(halaman, f"tiket_{orang.baris_csv}")
        return

    portal.klik_tombol(halaman, "Tutup", timeout=5_000)
    hasil.update(status="terdaftar")


def simpan_jejak(jejak: list, tanda: str = "") -> str:
    """
    Tulis rekaman struktur ke berkas agar bisa dipelajari.

    `tanda` memisahkan rekaman antar pekerja saat berjalan paralel; tanpa itu
    pekerja yang selesai belakangan menimpa rekaman pekerja lainnya.
    """
    config.siapkan_folder()
    tujuan = config.HASIL / f"struktur_pendaftaran{tanda}.json"
    tujuan.write_text(json.dumps(jejak, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(tujuan)


def _cocokkan(opsi: list[str], diinginkan: str) -> str:
    """
    Pilih opsi yang paling mendekati `diinginkan` dari daftar yang direkam.

    Kata-kata di CSV tidak selalu persis sama dengan tulisan di portal
    (mis. "Belum Kawin" vs "Belum Menikah"), jadi pencocokan dibuat bertingkat:
    persis -> saling mengandung -> ada kata yang sama.
    """
    d = (diinginkan or "").strip().lower()
    if not d or not opsi:
        return ""
    for o in opsi:
        if o.strip().lower() == d:
            return o
    # Aturan "saling mengandung" hanya berlaku untuk teks yang cukup panjang.
    # Tanpa batas ini, header abjad 'A' pada daftar wilayah dianggap cocok
    # dengan "Lagoa" � dan yang terklik adalah label abjadnya, bukan opsi.
    for o in opsi:
        ol = o.strip().lower()
        if len(ol) >= 4 and len(d) >= 4 and (d in ol or ol in d):
            return o
    kata = {k for k in re.split(r"[^\w]+", d) if len(k) > 3}
    for o in opsi:
        if kata & {k for k in re.split(r"[^\w]+", o.lower()) if len(k) > 3}:
            return o
    return ""


# Aturan cadangan saat kolom CSV kosong � disalin apa adanya dari macro
# ALL DEWASA_LANSIA PARAMETER V4.5 agar hasilnya sama persis, bukan tebakan baru.
_KERJA_DEWASA = ["Belum/Tidak Bekerja", "ASN (Kantor Pemerintah)", "Pegawai Swasta",
                 "Wirausaha/Pekerja Mandiri", "Pengusaha", "Petani / Pekebun",
                 "Guru", "Peternak", "Pekerja Pabrik / Buruh"]
_KERJA_LANSIA = ["Lainnya", "Belum/Tidak Bekerja", "Pensiunan", "Wirausaha/Pekerja Mandiri"]


def status_nikah_untuk(orang: Peserta) -> str:
    """Status pernikahan dari CSV; bila kosong, ditentukan dari usia."""
    if (orang.status_nikah or "").strip():
        return orang.status_nikah.strip()
    usia = orang.usia or 30
    if usia > 65:
        return "Cerai Mati"
    if usia >= 25:
        return "Menikah"
    return "Belum Menikah"


def pekerjaan_untuk(orang: Peserta) -> str:
    """Pekerjaan dari CSV; bila kosong, dipilih sesuai kelompok usia."""
    if (orang.pekerjaan or "").strip():
        return orang.pekerjaan.strip()
    usia = orang.usia or 30
    if usia >= 60:
        return random.choice(_KERJA_LANSIA)
    if usia >= 25:
        return random.choice(_KERJA_DEWASA)
    if usia > 17:
        return "Mahasiswa"
    if usia >= 7:
        return "Pelajar"
    return "Belum/Tidak Bekerja"


def _kata_cari(nilai: str) -> str:
    """
    Sederhanakan nama wilayah untuk kotak pencarian.

    CSV menulis "Kota Adm. Jakarta Utara", sedangkan portal bisa menuliskannya
    dengan awalan lain. Awalan jenis wilayah dibuang supaya yang dicari tinggal
    nama intinya.
    """
    bersih = re.sub(r"^(kota\s+adm\.?|kabupaten|kota|kab\.?)\s+", "",
                    (nilai or "").strip(), flags=re.I)
    return bersih.strip() or (nilai or "").strip()


def _isi_dropdown_h2(halaman, teks_pemicu: str, diinginkan: str,
                     nama: str, hasil: dict, jejak: list) -> str:
    """Rekam pilihan sebuah dropdown halaman 2, lalu pilih yang paling cocok."""
    # Lewat jalur "Gunakan Data", halaman 2 datang sudah terisi. Teks pemicunya
    # jadi berupa nilainya, bukan "Pilih ..." � jadi hilangnya pemicu di sini
    # berarti kolomnya SUDAH terisi, bukan gagal.
    if not portal.ada_pemicu(halaman, teks_pemicu):
        hasil["keterangan"] += f" | {nama}: sudah terisi"
        return ""
    opsi = portal.buka_dan_rekam(halaman, teks_pemicu)
    jejak.append({"tahap": f"5b_opsi_{nama}", "diinginkan": diinginkan, "opsi": opsi})
    if not opsi:
        hasil["keterangan"] += f" | {nama}: dropdown tak terbuka"
        return ""
    pilihan = _cocokkan(opsi, diinginkan)
    if not pilihan:
        portal.tutup_dropdown(halaman)
        hasil["keterangan"] += f" | {nama}: '{diinginkan}' tak ada di daftar"
        return ""
    if not portal.klik_opsi_baru(halaman, pilihan):
        portal.tutup_dropdown(halaman)
        hasil["keterangan"] += f" | {nama} GAGAL dipilih ({pilihan})"
        return ""
    hasil["keterangan"] += f" | {nama}: {pilihan}"
    return pilihan


def isi_halaman2(halaman, orang: Peserta, hasil: dict, jejak: list) -> None:
    """
    Isi halaman 2: status pernikahan, pekerjaan, alamat domisili, detail alamat.

    Dropdown di sini dicari lewat TEKS pemicunya, bukan lewat label: halaman 2
    tidak punya `#nik` sehingga `wadah_form()` tak bisa dipakai.
    Disabilitas dibiarkan apa adanya � bawaannya sudah "Tidak memiliki disabilitas".
    Isi tiap dropdown direkam lebih dulu karena tulisan resminya di portal
    belum tentu sama dengan yang tertulis di CSV.
    """
    _isi_dropdown_h2(halaman, "Pilih status pernikahan",
                     status_nikah_untuk(orang), "status nikah", hasil, jejak)

    _isi_dropdown_h2(halaman, "Pilih pekerjaan",
                     pekerjaan_untuk(orang), "pekerjaan", hasil, jejak)

    # Alamat domisili: di macro lama berupa empat kolom ketik
    # (provinsi/kota/kecamatan/kelurahan), di portal sekarang satu dropdown.
    # Dicocokkan dari yang paling sempit ke paling luas.
    if not portal.ada_pemicu(halaman, "Pilih alamat domisili"):
        hasil["keterangan"] += " | alamat: sudah terisi"
        halaman.wait_for_timeout(500)
        _rekam(halaman, jejak, "5c_halaman2_terisi")
        return

    tingkat = [("provinsi", orang.provinsi), ("kota", orang.kota),
               ("kecamatan", orang.kecamatan), ("kelurahan", orang.kelurahan)]
    pilih_domisili(halaman, tingkat, hasil, jejak)

    # --- detail alamat ---
    try:
        kolom = halaman.locator("#detail-domisili")
        if kolom.count() and not (kolom.input_value() or "").strip():
            kolom.fill(orang.alamat or orang.kelurahan or "-")
    except Exception as e:
        hasil["keterangan"] += f" | detail alamat GAGAL: {type(e).__name__}"

    halaman.wait_for_timeout(800)
    _rekam(halaman, jejak, "5c_halaman2_terisi")


def pilih_domisili(halaman, tingkat: list, hasil: dict, jejak: list) -> bool:
    """
    Pilih alamat domisili bertingkat (provinsi > kota > kecamatan > kelurahan).

    Dipakai alur dewasa/lansia dan - sebagai cadangan - alur sekolah, bila
    "sama dengan alamat sekolah" tidak menyalin apa pun.
    """
    portal.buka_dan_rekam(halaman, "Pilih alamat domisili")
    sampai = []
    for nama_tingkat, nilai in tingkat:
        if not nilai:
            break
        kunci = _kata_cari(nilai)
        portal.cari_lokasi(halaman, kunci)
        opsi = portal.opsi_lokasi(halaman)

        # Daftar opsi tiap tingkat MASIH memuat jejak tingkat sebelumnya
        # (provinsi, kota, kecamatan yang sudah dipilih). Kalau nama kelurahan
        # kebetulan sama dengan kecamatannya - "Koja" di kecamatan "Koja" -
        # yang terklik adalah jejaknya, bukan kelurahannya, sehingga alamat
        # tidak pernah lengkap dan tombol Selanjutnya tetap mati.
        # Jejak dibuang SATU kemunculan saja, supaya nama yang sah tetap ada.
        tersisa = list(opsi)
        for sudah in sampai:
            if sudah in tersisa:
                tersisa.remove(sudah)

        jejak.append({"tahap": f"5b_lokasi_{nama_tingkat}", "diinginkan": nilai,
                      "dicari": kunci, "opsi": opsi[:60], "setelah_buang_jejak": tersisa[:60]})
        cocok = _cocokkan(tersisa, nilai) or _cocokkan(tersisa, kunci)
        # Lewati sebanyak jejak yang tulisannya sama, supaya yang terklik
        # benar-benar pilihan tingkat ini � bukan jejak tingkat sebelumnya.
        if not cocok or not portal.klik_lokasi(halaman, cocok, lewati=sampai.count(cocok)):
            hasil["keterangan"] += f" | alamat berhenti di {nama_tingkat} ({nilai})"
            portal.tutup_dropdown(halaman)
            return False
        sampai.append(cocok)
    hasil["keterangan"] += " | alamat: " + " > ".join(sampai)
    return True
