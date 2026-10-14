"""
Tahap sesudah pendaftaran: cari peserta -> konfirmasi hadir -> mulai pemeriksaan.

Alurnya mengikuti macro ALL DEWASA_LANSIA PARAMETER V4.5 blok
"Cari Hasil Pendaftaran", tapi elemennya dicari secara semantik. Macro memakai
xpath absolut (`/html/body/div[3]/...`) yang sudah berkali-kali patah begitu
tata letak portal bergeser sedikit saja.

Tiap langkah merekam struktur halaman ke `hasil/struktur_layanan.json`, supaya
bagian yang belum dikenal bisa diperbaiki dari bukti, bukan dari tebakan.
"""
from __future__ import annotations

import json
import re

import config
import form
import portal
from browser import simpan_gambar
from pendaftaran import REKAM
from peserta import Peserta


def _rekam(halaman, jejak: list, nama_tahap: str) -> None:
    data = halaman.evaluate(REKAM)
    data["tahap"] = nama_tahap
    jejak.append(data)


def _tombol_baris(baris) -> list[str]:
    """Tulisan semua tombol di dalam satu baris tabel."""
    tombol = baris.locator("button")
    keluar = []
    for i in range(min(tombol.count(), 8)):
        try:
            teks = (tombol.nth(i).inner_text() or "").strip()
            if teks:
                keluar.append(teks)
        except Exception:
            continue
    return keluar


def _kolom_cari(halaman):
    """
    Kolom pencarian di daftar peserta.

    Tidak dicari lewat id: begitu jenis pencarian diganti dari Nomor Tiket ke
    NIK, portal mengganti elemennya sehingga `#searchNik` yang lama tidak lagi
    bisa diisi. Yang dipakai adalah kolom teks TERLIHAT pertama, dengan
    prioritas pada yang keterangannya menyebut NIK.
    """
    kandidat = halaman.locator(
        "xpath=//input[not(@type='checkbox')][not(@type='radio')][not(@id='detail-domisili')]"
    )
    jumlah = min(kandidat.count(), 10)
    cadangan = None
    for i in range(jumlah):
        satu = kandidat.nth(i)
        try:
            if not (satu.is_visible() and satu.is_enabled()):
                continue
            petunjuk = " ".join(filter(None, [
                satu.get_attribute("placeholder"), satu.get_attribute("id"),
                satu.get_attribute("name"),
            ])).lower()
            if "nik" in petunjuk:
                return satu
            if cadangan is None:
                cadangan = satu
        except Exception:
            continue
    return cadangan


def cari_peserta(halaman, orang: Peserta, hasil: dict, jejak: list):
    """
    Cari peserta di daftar "Data Individu Terdaftar".

    Kolom pencarian bawaannya memakai Nomor Tiket, jadi jenis pencarian
    diganti dulu ke NIK � NIK selalu ada di CSV, nomor tiket belum tentu.
    Kembalikan locator baris peserta, atau None.
    """
    halaman.goto(config.HAL_PENDAFTARAN, wait_until="domcontentloaded")
    portal.tunggu_siap(halaman, portal.js_ada_tombol("Daftar Baru"), 2500,
                       "halaman pendaftaran termuat")

    mode, nilai = kunci_cari(orang, hasil)
    # Bayi tanpa NIK tanpa tiket tidak bisa dicari dengan apa pun. Dihentikan
    # DI SINI dengan sebab yang jelas - bukan dibiarkan mengetik string kosong
    # ke kolom pencarian, yang menampilkan SELURUH daftar dan berakhir memilih
    # baris milik orang lain.
    if not nilai:
        hasil["keterangan"] += f" | {mode} kosong: tak ada yang bisa dicari"
        return None

    _pilih_mode_cari(halaman, hasil, jejak, mode)
    # Portal mengganti elemen kolom pencarian saat modenya berpindah; menunggu
    # sekian milidetik lalu berharap pernah membuat NIK diketik ke kolom lama.
    portal.tunggu_siap(halaman,
                       portal.ADA_KOLOM_NIK if mode == "NIK" else portal.js_ada_kolom_cari(),
                       800, f"kolom {mode} siap")
    _rekam(halaman, jejak, "8a_setelah_ganti_jenis")

    kolom = _kolom_cari(halaman)
    if kolom is None:
        hasil["keterangan"] += " | kolom pencarian tidak ketemu"
        simpan_gambar(halaman, f"kolomcari_{orang.baris_csv}")
        return None
    try:
        _ketik_cari(halaman, kolom, nilai)
        kolom.press("Enter")
    except Exception as e:
        hasil["keterangan"] += f" | kolom cari gagal: {type(e).__name__}"
        simpan_gambar(halaman, f"kolomcari_{orang.baris_csv}")
        return None

    # Yang ditunggu ORANGNYA muncul, bukan "tabel berubah": tabel yang berubah
    # jadi kosong pun sudah dianggap berubah, dan itu membuat peserta yang baru
    # saja didaftarkan - yang tiketnya sudah terbit - dinyatakan tidak ketemu.
    #
    # Diulang dengan Enter lagi: peserta yang BARU didaftarkan belum langsung
    # terindeks portal, dan pencarian pertama benar-benar kosong. Terbukti dari
    # peserta ber-tiket AKQ-KBA, FVL-RB9, dan 89P-NLL yang gagal dicari padahal
    # pendaftarannya berhasil.
    portal.tunggu_siap(
        halaman, portal.js_atau(portal.js_ada_nama(orang.nama),
                                portal.js_ada_teks("Tidak ada data")),
        3000, "hasil pencarian NIK")
    habis = config.TUNGGU_MUNCUL_MS
    while habis > 0 and not halaman.evaluate(portal.js_ada_nama(orang.nama)):
        halaman.wait_for_timeout(1200)
        habis -= 1200
        try:
            kolom.press("Enter")
        except Exception:
            break
        if halaman.evaluate(portal.js_ada_nama(orang.nama)):
            hasil["keterangan"] += (" | muncul setelah "
                                    f"{(config.TUNGGU_MUNCUL_MS - habis) // 1000}s")
            break
    _rekam(halaman, jejak, "8_hasil_pencarian")

    # Tabel hasil tidak memuat kolom NIK, jadi baris dikenali lewat nama.
    # `:has-text` pada Playwright tidak peduli besar-kecil huruf, sehingga
    # "BUDI SANTOSO" di CSV tetap cocok dengan "Budi Santoso" di portal.
    baris = portal.baris_bernama(halaman, orang.nama)
    # Pencarian lewat NAMA bisa menyisakan lebih dari satu baris - orang bisa
    # bernama sama, NIK tidak. Yang diambil tetap yang pertama, tapi keadaannya
    # DICATAT: kalau suatu saat ada peserta yang salah orang, jejaknya ada di
    # berkas hasil dan bukan misteri.
    if mode == "Nama" and baris.count() > 1:
        hasil["keterangan"] += f" | PERHATIAN: {baris.count()} baris bernama sama"
        baris = _saring_baris_kembar(orang, hasil, baris)
    if not baris.count():
        # Tanda baca dan spasi ganda bisa berbeda antara CSV dan portal
        # ("M. ADI PUTRA PRATAMA" vs "M Adi Putra Pratama"), jadi pencocokan
        # diulang setelah keduanya disederhanakan jadi huruf dan angka saja.
        nomor = halaman.evaluate(
            """(nama) => {
                 const sederhana = s => (s || '').toLowerCase().replace(/[^a-z0-9]/g, '');
                 const mau = sederhana(nama);
                 const baris = [...document.querySelectorAll('tr')];
                 for (let i = 0; i < baris.length; i++) {
                   if (baris[i].querySelector('th') || baris[i].closest('thead')) continue;
                   if (sederhana(baris[i].innerText).includes(mau)) return i;
                 }
                 return -1;
               }""", orang.nama)
        if nomor >= 0:
            hasil["keterangan"] += " | baris ketemu setelah tanda baca diabaikan"
            baris = halaman.locator("tr").nth(nomor)
        else:
            # Nama di portal bisa BERBEDA dari nama di CSV, bukan sekadar beda
            # tanda baca: "M. ADI PUTRA PRATAMA" tercatat "Muhammad Adi".
            # Karena pencarian tadi memakai NIK, hasilnya sudah pasti orang
            # yang benar - jadi bila tersisa TEPAT SATU baris data, itu dia.
            #
            # Alasan itu TIDAK berlaku untuk pencarian lewat nama: kalau
            # namanya saja sudah tidak cocok, tak ada lagi yang menjamin baris
            # tunggal itu orang yang sama. Jadi jalan pintas ini ditutup di
            # sana - lebih baik "tidak ketemu" daripada salah orang.
            satu = halaman.evaluate(
                """() => {
                     const baris = [...document.querySelectorAll('tr')]
                       .map((t, i) => ({i, teks: (t.innerText || '').trim(),
                                        tombol: t.querySelectorAll('button').length}))
                       .filter(b => b.tombol > 0 && b.teks.length > 20);
                     return baris.length === 1 ? baris[0].i : -1;
                   }""")
            if satu >= 0 and mode == "NIK":
                hasil["keterangan"] += " | nama beda, dipakai satu-satunya baris hasil NIK"
                baris = halaman.locator("tr").nth(satu)
            else:
                hasil["keterangan"] += " | peserta tidak ketemu di daftar"
                simpan_gambar(halaman, f"cari_{orang.baris_csv}")
                _rekam(halaman, jejak, "8x_baris_tak_ketemu")
                return None
    jejak.append({"tahap": "8b_baris_peserta", "tombol": _tombol_baris(baris.first)})
    return baris.first


def _saring_baris_kembar(orang: Peserta, hasil: dict, baris):
    """
    Pilih baris yang TANGGAL LAHIRNYA cocok, saat satu nama dipakai beberapa baris.

    Mengambil baris pertama begitu saja aman untuk pencarian lewat NIK - NIK
    tidak kembar. Untuk pencarian lewat NAMA tidak, dan bayi tanpa NIK SELALU
    dicari lewat nama, sebab tak ada NIK yang bisa diketik.

    Terbukti 9 Sep pada "by ny CONTOH IBU": portal memuat dua baris
    bernama sama - satu bayi lahir 16 Jul 2024 (Perempuan) yang sudah "Sudah
    Hadir" dan tanpa tombol aksi, satu lagi bayi kita, lahir 11 Agt 2024
    (Laki-laki), yang tombol "Konfirmasi Hadir"-nya justru tersedia. Yang
    terambil baris pertama, lalu dilaporkan "tak ada tombol aksi di baris
    peserta" - keluhan yang menunjuk ke tempat yang salah.

    Nama ibu memang dipakai bersama oleh kakak-adik, jadi keadaan ini akan
    berulang. Tanggal lahir yang membedakannya, dan portal menampilkannya di
    kolom tabel ("11 Agt 2024"). Jenis kelamin dipakai sebagai pembeda kedua.

    Bila penyaringan tidak menyisakan tepat satu baris, yang dikembalikan
    kumpulan semula - biar perilakunya sama seperti sebelumnya, tidak menebak.
    """
    def _sisa(pola: re.Pattern) -> list:
        return [i for i in range(baris.count())
                if pola.search(" ".join((baris.nth(i).inner_text() or "").split()))]

    lahir = orang.tanggal_lahir
    if lahir is None:
        return baris
    # Hari ditulis portal dengan nol di depan ("01 Jun 2001"), jadi keduanya
    # diterima. `\b` di depan mencegah "1 Jun" ikut cocok dengan "21 Jun".
    pola = re.compile(r"\b0?%d\s+%s\s+%d\b"
                      % (lahir.day, portal.BULAN_ID[lahir.month], lahir.year))
    cocok = _sisa(pola)
    if len(cocok) > 1 and orang.jenis_kelamin:
        # Portal menulis "Laki-Laki"/"Perempuan"; huruf besar-kecilnya berbeda
        # dari CSV, jadi dicocokkan tanpa peduli besar-kecil.
        kelamin = re.compile(re.escape(orang.jenis_kelamin).replace(r"\-", "-"), re.I)
        lagi = [i for i in cocok
                if kelamin.search(" ".join((baris.nth(i).inner_text() or "").split()))]
        if len(lagi) == 1:
            cocok = lagi
    if len(cocok) != 1:
        hasil["keterangan"] += (f" | tanggal lahir cocok di {len(cocok)} baris - "
                                "dipakai baris pertama")
        return baris
    hasil["keterangan"] += f" | dipilih baris ke-{cocok[0] + 1} (tanggal lahir cocok)"
    return baris.nth(cocok[0])


def konfirmasi_hadir(halaman, orang: Peserta, hasil: dict, jejak: list) -> bool:
    """Konfirmasi kehadiran peserta lalu buka halaman pemeriksaannya."""
    baris = cari_peserta(halaman, orang, hasil, jejak)
    if baris is None:
        return False
    return konfirmasi_pada_baris(halaman, orang, hasil, jejak, baris)


def konfirmasi_pada_baris(halaman, orang: Peserta, hasil: dict, jejak: list,
                          baris) -> bool:
    """
    Konfirmasi hadir mulai dari BARIS peserta yang sudah ditemukan.

    Dipisah dari pencariannya karena cara menemukan baris berbeda antar alur �
    individu memakai pencarian NIK di halaman pendaftaran, sekolah memakai
    filter Sekolah+Kelas lebih dulu � sedangkan langkah sesudahnya (tombol aksi,
    checkbox verify, tombol Hadir) sama persis.
    """
    nama_tombol = _tombol_baris(baris)
    if not nama_tombol:
        # DIBACA SEKALI LAGI SESUDAH TABELNYA DIAM. Tombol aksi baru dipasang
        # portal beberapa ratus milidetik setelah barisnya tampil; dibaca tepat
        # di celah itu, barisnya ada tapi tombolnya belum. Menyerah di situ
        # menjatuhkan peserta yang sebenarnya siap dikonfirmasi.
        portal.tunggu_siap(halaman, portal.JS_TIDAK_MEMUAT, 3_000, "tabel tenang")
        halaman.wait_for_timeout(700)
        ulang = portal.baris_bernama(halaman, orang.nama)
        if ulang.count():
            baris = ulang.first
            nama_tombol = _tombol_baris(baris)
            if nama_tombol:
                hasil["keterangan"] += " | tombol aksi baru muncul setelah ditunggu"
    pilih = next((t for t in nama_tombol if re.search(r"konfirmasi|hadir|detail|periksa", t, re.I)),
                 nama_tombol[0] if nama_tombol else "")
    if not pilih:
        hasil["keterangan"] += " | tak ada tombol aksi di baris peserta"
        simpan_gambar(halaman, f"aksi_{orang.baris_csv}")
        return False
    try:
        baris.locator(f'button:has-text("{pilih}")').first.click(timeout=8_000)
    except Exception as e:
        hasil["keterangan"] += f" | tombol '{pilih}' gagal diklik: {type(e).__name__}"
        return False
    hasil["keterangan"] += f" | aksi baris: {pilih}"
    # HANYA #verify yang ditunggu. Dulu "Hadir" ikut dipakai sebagai tanda
    # modal terbuka, padahal `js_ada_tombol` mencocokkan sebagian teks dan
    # tombol di SETIAP baris tabel bernama "Konfirmasi Hadir" - syaratnya sudah
    # benar sebelum diklik, penantiannya pulang dalam 0,1 detik, dan modal yang
    # belum sempat terpasang terbaca sebagai "sudah dikonfirmasi hadir".
    # Akibatnya berantai: tak ada modal "Berhasil Hadir", tombol "Periksa
    # Skrining Mandiri" dicari sia-sia, lalu alurnya jatuh ke sapuan pelayanan.
    minta_konfirmasi = bool(re.search(r"konfirmasi|hadir", pilih, re.I))
    if minta_konfirmasi:
        portal.tunggu_siap(halaman, portal.js_terlihat("#verify"),
                           config.TUNGGU_MUNCUL_MS, "modal konfirmasi terbuka")
    _rekam(halaman, jejak, "9_setelah_aksi_baris")

    # Modal konfirmasi memakai checkbox kustom: <input id="verify"> transparan
    # bertumpuk dengan <div id="verify"> yang kelihatan. Yang harus diklik
    # adalah elemen yang TERLIHAT � pelajaran dari macro.
    # Peserta yang sudah dikonfirmasi tidak memunculkan modal ini lagi �
    # itu bukan kegagalan, cukup dilewati supaya tahap berikutnya tetap jalan.
    if not halaman.locator("#verify").count():
        # Dibedakan: yang memang sudah hadir (tombolnya bukan konfirmasi) dari
        # yang modalnya tidak mau terbuka. Dulu keduanya dilaporkan sama, dan
        # kegagalan sungguhan menyamar sebagai keadaan yang wajar.
        hasil["keterangan"] += (
            f" | modal konfirmasi tidak terbuka dalam "
            f"{config.TUNGGU_MUNCUL_MS // 1000}s"
            if minta_konfirmasi else " | sudah dikonfirmasi hadir sebelumnya")
        return True

    # MODAL YANG SUDAH MUNCUL BELUM TENTU SUDAH SIAP.
    #
    # Modal konfirmasi hadir memuat isinya sendiri sesudah terpasang, dan
    # selama itu ada lapisan "Memuat data.." menutupi seluruhnya. Elemen
    # #verify sudah ada di DOM sejak awal, jadi penantian di atas selesai
    # SEBELUM modalnya benar-benar siap: centangnya mendarat di lapisan
    # pemuat, tidak di checkbox. Terjadi pada seorang murid
    # (MIS ILHAM 1, FCD-2JL, 5 Sep) - tiga percobaan, tiga-tiganya begitu.
    portal.tunggu_siap(halaman, portal.JS_TIDAK_MEMUAT, config.TUNGGU_MUNCUL_MS,
                       "modal konfirmasi selesai memuat")

    # DICENTANG SAMPAI BENAR-BENAR TERCENTANG - jawabannya dibaca, bukan
    # dibuang. Tombol kirimnya baru lahir SESUDAH checkbox ini tercentang,
    # jadi centang yang meleset muncul di kemudian hari sebagai "tombol
    # konfirmasi hadir tak ditemukan" - keterangan yang menunjuk ke tempat
    # yang salah dan membuat kegagalannya dicari di tombol, bukan di sini.
    dicentang = False
    for _ in range(3):
        if portal.centang(halaman, "verify"):
            dicentang = True
            break
        halaman.wait_for_timeout(600)
        portal.tunggu_siap(halaman, portal.JS_TIDAK_MEMUAT, 3000,
                           "modal konfirmasi masih memuat")
    if not dicentang:
        hasil["keterangan"] += (" | checkbox persetujuan tidak bisa dicentang"
                                " (modal belum selesai memuat) - tombol kirim"
                                " memang tidak akan muncul")
        simpan_gambar(halaman, f"verify_{orang.baris_csv}")
        _rekam(halaman, jejak, "10_setelah_konfirmasi")
        return False

    # Persis "Hadir", bukan sekadar memuatnya - lihat alasannya di atas.
    portal.tunggu_siap(halaman, portal.js_tombol_persis("Hadir"), 6_000,
                       "tombol Hadir hidup", dasar_ms=150)

    # Nomor tiket tampil di modal ini � sumber yang paling bisa dipercaya,
    # karena melekat pada baris peserta yang bersangkutan.
    if not hasil.get("tiket"):
        m = re.search(r"Nomor\s*Tiket\s*:?\s*([A-Za-z0-9]+-[A-Za-z0-9]+)",
                      halaman.inner_text("body"), re.I)
        if m:
            hasil["tiket"] = m.group(1)

    # Tombol kirimnya "Hadir", dan baru muncul SESUDAH checkbox dicentang.
    # Ditanya SEKALI tombol mana yang ada, bukan dicoba satu per satu:
    # tiap nama yang tidak ada dulu memakan tenggatnya sendiri.
    dipakai = portal.klik_salah_satu(halaman, ("Hadir", "Konfirmasi", "Ya", "Simpan"), 4_000)
    terkirim = bool(dipakai)
    if terkirim:
        hasil["keterangan"] += f" | konfirmasi: {dipakai}"
    if not terkirim:
        hasil["keterangan"] += " | tombol konfirmasi hadir tak ditemukan"
        simpan_gambar(halaman, f"hadir_{orang.baris_csv}")
        _rekam(halaman, jejak, "10_setelah_konfirmasi")
        return False

    portal.tunggu_siap(halaman, portal.js_atau(
        portal.js_ada_teks("No. Tiket"),
        portal.js_ada_teks("Berhasil Hadir"),
        portal.js_ada_teks("Gagal memproses"),
        portal.js_ada_tombol("Periksa Skrining Mandiri")), 3000, "jawaban tombol Hadir")

    # Portal bisa membalas "Terjadi kesalahan - Gagal memproses data" tepat
    # sesudah Hadir ditekan. Popup itu menutupi modal, sehingga langkah
    # berikutnya gagal dengan gejala "tombol tidak ada". Tutup lalu tekan
    # Hadir sekali lagi.
    pesan = portal.tutup_popup_galat(halaman)
    if pesan:
        hasil["keterangan"] += f" | popup galat saat Hadir: {pesan}"
        if portal.klik_tombol_persis(halaman, "Hadir", timeout=4_000):
            hasil["keterangan"] += " | Hadir diulang"
            portal.tunggu_siap(halaman, portal.js_atau(
                portal.js_ada_teks("No. Tiket"),
                portal.js_ada_teks("Berhasil Hadir")), 3000, "jawaban Hadir ulang")

    _rekam(halaman, jejak, "10_setelah_konfirmasi")
    return True


# Satu-satunya penanda bahwa pemeriksaan BELUM dimulai: tombolnya masih ada.
TOMBOL_MULAI = portal.js_ada_tombol("Mulai Pemeriksaan")


def mulai_pemeriksaan(halaman, orang: Peserta, hasil: dict, jejak: list) -> bool:
    """
    Buka halaman detail pemeriksaan lalu tekan "Mulai Pemeriksaan".

    Tombolnya hanya ada selama status peserta masih "Belum Pemeriksaan";
    kalau sudah dimulai, tahap ini memang seharusnya dilewati � bukan gagal.
    """
    # Sesudah "Hadir" portal biasanya langsung membuka halaman pemeriksaan.
    # Tombol pembuka hanya dicoba bila ternyata belum pindah � kalau tidak,
    # tiap tebakan nama tombol memakan waktu tunggu sendiri-sendiri.
    if "detail-pemeriksaan" not in halaman.url:
        # Bersihkan dulu popup galat yang mungkin tertinggal dari langkah
        # Hadir - selama ia terbuka, tombol pembuka detail tidak bisa diklik.
        pesan = portal.tutup_popup_galat(halaman)
        if pesan:
            hasil["keterangan"] += f" | popup galat: {pesan}"
        nama = portal.klik_salah_satu(
            halaman, ("Periksa Skrining Mandiri", "Bantu Isi Skrining Mandiri", "Detail"), 4_000)
        if nama:
            hasil["keterangan"] += f" | buka detail via: {nama}"
            # Ditunggu sampai halamannya benar-benar berpindah, bukan sekadar
            # dijeda: klik yang diterima tanpa galat ternyata bisa tidak
            # berbuat apa-apa, dan jeda tetap membuat keduanya terlihat sama
            # saja di catatan.
            pindah = portal.tunggu_kondisi(
                halaman, "() => location.href.includes('detail-pemeriksaan')",
                batas_ms=8_000)
            if not pindah:
                hasil["keterangan"] += " (halaman tidak berpindah)"

    _rekam(halaman, jejak, "11_halaman_detail")
    if "detail-pemeriksaan" not in halaman.url:
        hasil["keterangan"] += f" | belum sampai halaman detail ({halaman.url.rsplit('/', 1)[-1]})"
        simpan_gambar(halaman, f"detail_{orang.baris_csv}")
        return False

    # "TOMBOL TIDAK KETEMU" BUKAN "SUDAH DIMULAI".
    #
    # Daftar layanan di halaman ini dirender BERTAHAP - catatan hasil sendiri
    # merekam "7 -> 14 baris" - dan selama itu tombolnya belum terpasang.
    # Versi lama menyimpulkan "sudah dimulai" begitu tenggat 6 detik habis,
    # lalu menyapu form yang MASIH TERKUNCI: nol form terisi, tidak ada yang
    # tercatat gagal, dan statusnya jadi "layanan_selesai" - yang berwarna
    # HIJAU - padahal pemeriksaannya belum pernah dimulai.
    #
    # Terbukti pada dua peserta (1 Sep):
    # jalan pertama mencatat "'Mulai Pemeriksaan' tidak ada (sudah dimulai)"
    # lalu "form terisi: 0"; jalan kedua menemukan keduanya di tab "Belum
    # Pemeriksaan" - jadi memang belum dimulai - dan mengisi 14 dan 7 form.
    #
    # Karena itu halamannya ditenangkan DULU, baru ditanya sekali.
    portal.tunggu_siap(halaman, portal.js_dan(portal.JS_TIDAK_MEMUAT,
                                              portal.ADA_BARIS_LAYANAN),
                       6_000, "daftar layanan siap sebelum Mulai Pemeriksaan")
    if not halaman.evaluate(TOMBOL_MULAI):
        # Peserta di tab "Sedang Pemeriksaan" memang sudah dimulai - tombolnya
        # tidak ada, dan yang tersisa hanya menyapu daftar layanannya.
        hasil["keterangan"] += " | 'Mulai Pemeriksaan' tidak ada (sudah dimulai)"
        return True
    if not portal.klik_tombol(halaman, "Mulai Pemeriksaan", timeout=6_000):
        hasil["keterangan"] += " | 'Mulai Pemeriksaan' ada tapi tak bisa diklik"
        simpan_gambar(halaman, f"mulai_{orang.baris_csv}")
        return False
    # ADA_BARIS_LAYANAN dulu ikut jadi syarat di sini, dan itu SELALU sudah
    # benar: di halaman detail daftar layanan memang sudah terbaca sebelum
    # "Mulai Pemeriksaan" ditekan - hanya terkunci, bukan tidak ada. Jadi
    # penantiannya pulang seketika dan kalender dibaca sebelum terpasang,
    # sehingga tanggal tidak terpilih dan pemeriksaan tidak pernah dimulai.
    portal.tunggu_siap(halaman, portal.js_atau(
        portal.ADA_KALENDER_KUOTA,
        "() => (document.body.innerText || '').includes('Konfirmasi Tanggal Pemeriksaan')"),
        6000, "kalender pemeriksaan muncul")

    # Sesudah "Mulai Pemeriksaan" muncul KALENDER, bukan sekadar tombol setuju:
    # tanggalnya harus dipilih dulu, kalau tidak tombol konfirmasinya mati dan
    # pemeriksaan tidak pernah benar-benar dimulai.
    tgl = portal.pilih_tanggal_pemeriksaan(halaman)
    if tgl:
        hasil["keterangan"] += f" | tanggal pemeriksaan: {tgl}"
        halaman.wait_for_timeout(300)
    else:
        # Dulu diam. Tanpa catatan ini, "konfirmasi tanggal: Simpan" di hasil
        # terlihat seperti langkah yang beres, padahal tanggalnya kosong.
        hasil["keterangan"] += " | TANGGAL PEMERIKSAAN TIDAK TERPILIH (kalender tak terbaca)"
        simpan_gambar(halaman, f"kalender_{orang.baris_csv}")

    # Tombolnya ternyata "Simpan" - pilihan ketiga dalam antrean lama, sehingga
    # tiap peserta membuang 3 detik menunggu "Konfirmasi" lalu 3 detik menunggu
    # "Ya". Terukur pada 90 peserta di riwayat hasil.
    dipakai = portal.klik_salah_satu(halaman, ("Konfirmasi", "Ya", "Simpan", "Mulai"), 3_000)
    if dipakai:
        hasil["keterangan"] += f" | konfirmasi tanggal: {dipakai}"
    # Kuota 0 tetap boleh dipakai; portal cuma minta persetujuan sekali lagi.
    if portal.lewati_popup_kuota(halaman):
        hasil["keterangan"] += " | popup kuota habis: Lanjut"
    portal.tunggu_siap(halaman, portal.ADA_BARIS_LAYANAN, 2500, "daftar layanan siap")
    _rekam(halaman, jejak, "12_pemeriksaan_dimulai")
    # DIPERIKSA, BUKAN DIANDAIKAN. Tombolnya harus HILANG kalau pemeriksaan
    # benar-benar jadi dimulai. Selama ia masih ada, form tetap terkunci dan
    # menyapunya hanya menghasilkan laporan "beres" yang palsu.
    #
    # HILANGNYA HARUS MENETAP. Selagi popup tertutup dan halaman memuat ulang,
    # tombolnya sempat tidak terlihat sesaat - dan pemeriksaan sekali jalan
    # menganggap itu "sudah dimulai". Rekaman Lagoa 07 (29 Sep) menunjukkan
    # tombol "Mulai Pemeriksaan" masih ada sesudah langkah ini, tanpa catatan
    # "MASIH ADA" di hasilnya. Jadi dilihat sekali lagi sesudah jeda singkat.
    hilang = portal.tunggu_kondisi(halaman, portal.js_tidak(TOMBOL_MULAI), 5_000)
    if hilang:
        portal.tunggu_siap(halaman, portal.JS_TIDAK_MEMUAT, 4_000, "halaman tenang")
        halaman.wait_for_timeout(1_200)
        hilang = not halaman.evaluate(TOMBOL_MULAI)
    if not hilang:
        hasil["keterangan"] += " | 'Mulai Pemeriksaan' MASIH ADA - pemeriksaan tidak jadi dimulai"
        simpan_gambar(halaman, f"mulai_{orang.baris_csv}")
        return False
    return True


# Pemetaan daftar layanan. Id barisnya mengikuti pola `rowfrm...` (mandiri)
# dan `row-FRM...` (Nakes) � sama seperti yang dipakai macro. Bila polanya
# meleset, baris tabel yang memuat "Input Data" dipakai sebagai cadangan.
PETA_LAYANAN = """() => {
  const rapi = s => (s || '').replace(/\\s+/g, ' ').trim();
  const bagian = [...document.querySelectorAll('*')].filter(e =>
      e.children.length === 0 && /\\((\\d+)\\/(\\d+)\\)/.test(e.innerText || ''))
      .map(e => rapi(e.innerText)).filter(t => t.length < 60);
  let baris = [...document.querySelectorAll('[id^="rowfrm"], [id^="row-FRM"], [id^="rowFRM"]')]
      .map(e => ({id: e.id, teks: rapi(e.innerText).slice(0, 140)}));
  if (!baris.length) {
    baris = [...document.querySelectorAll('tr')]
      .filter(r => /Input Data/i.test(r.innerText || ''))
      .map(r => ({id: r.id || '', teks: rapi(r.innerText).slice(0, 140)}));
  }
  return {ringkasan: [...new Set(bagian)], jumlah: baris.length, baris};
}"""


def petakan_layanan(halaman, hasil: dict, jejak: list) -> dict:
    """Catat seluruh baris daftar layanan beserta id dan statusnya."""
    peta = halaman.evaluate(PETA_LAYANAN)
    peta["tahap"] = "13_daftar_layanan"
    jejak.append(peta)
    config.siapkan_folder()
    (config.HASIL / "daftar_layanan.json").write_text(
        json.dumps(peta, ensure_ascii=False, indent=2), encoding="utf-8")
    hasil["keterangan"] += f" | daftar layanan: {peta['jumlah']} baris"
    return peta


def intip_form(halaman, jejak: list, hasil: dict) -> None:
    """
    Buka satu form pertama lalu rekam strukturnya � tanpa mengisi apa pun.

    Form skrining ada di domain lain (form.kemkes.go.id) dan dibangun dengan
    SurveyJS, jadi strukturnya perlu dilihat langsung sebelum pengisiannya
    bisa dibangun.
    """
    alamat_awal = halaman.url
    tombol = halaman.locator('button:has-text("Input Data")').first
    if not tombol.count():
        hasil["keterangan"] += " | tombol 'Input Data' tidak ada"
        return
    try:
        tombol.click(timeout=8_000)
    except Exception as e:
        hasil["keterangan"] += f" | 'Input Data' gagal diklik: {type(e).__name__}"
        return
    halaman.wait_for_timeout(6000)
    _rekam(halaman, jejak, "14_form_pertama")
    hasil["keterangan"] += (" | form terbuka" if halaman.url != alamat_awal
                            else " | form tidak berpindah halaman")


def _ketik_cari(halaman, kolom, nilai: str) -> bool:
    """
    Isi kolom pencarian dengan ketikan sungguhan, bukan `fill()`.

    `fill()` menaruh nilai sekaligus; komponen Vue di portal ini menyimpan
    nilainya sendiri lewat kejadian ketik, sehingga kolom terlihat sudah berisi
    16 digit tapi validasinya tetap berkata "NIK hanya bisa angka" karena yang
    dibacanya masih kosong. Ini persoalan yang sama yang dulu memaksa macro
    memakai XType, bukan pengisian langsung.

    DIBACA ULANG SESUDAHNYA - kembalikan True hanya bila kolomnya BENAR-BENAR
    berisi nilai itu. Kolom NIK portal BERTOPENG; isinya ditampilkan sebagai
    "3212-1059-0815-0001", dan ketikan yang meleset atau pembersihan yang tidak
    jadi menyisakan nilai yang salah TANPA satu pun galat. Pencariannya lalu
    tidak menemukan apa-apa, dan muridnya divonis "tidak ada" padahal barisnya
    jelas ada di portal - terjadi pada seorang peserta (3 Sep), yang
    barisnya lengkap dengan tombol "Konfirmasi Hadir".

    Karena bertopeng, yang dibandingkan HURUF DAN ANGKANYA saja - tanda
    hubung dari topeng NIK dan dari nomor tiket sama-sama diabaikan.
    """
    mau = re.sub(r"[^0-9A-Za-z]", "", nilai or "").upper()
    for _ in range(2):
        kolom.click()
        kolom.press("Control+a")
        kolom.press("Backspace")
        halaman.wait_for_timeout(250)
        ketik = getattr(kolom, "press_sequentially", None) or kolom.type
        ketik(nilai, delay=60)
        halaman.wait_for_timeout(600)
        try:
            terisi = re.sub(r"[^0-9A-Za-z]", "", kolom.input_value() or "").upper()
        except Exception:
            return True          # tak bisa dibaca - jangan menghakimi
        if not mau or terisi == mau:
            return True
    return False


def kunci_cari(orang: Peserta, hasil: dict) -> tuple[str, str]:
    """
    Dengan APA peserta ini dicari di daftar portal: ("NIK"|"Nama", nilainya).

    Peserta ber-NIK dicari lewat NIK - selalu ada di berkas dan tidak pernah
    kembar. Bayi tanpa NIK dicari lewat NAMANYA ("Bayi Nyonya ..."), baik saat
    konfirmasi hadir di halaman pendaftaran maupun di halaman pelayanan.

    Nomor tiket sempat dipakai di sini dan DIGANTI. Kedua halaman ternyata
    menyediakan mode Nama - diperiksa langsung di portal 3 Sep: halaman
    pendaftaran maupun pelayanan sama-sama menawarkan Nomor Tiket, NIK, dan
    Nama. Nama lebih baik daripada tiket karena tidak bergantung pada
    pendaftaran yang baru saja terjadi: tahap "pelayanan" yang dijalankan
    terpisah tidak memegang tiket apa pun, dan dengan tiket peserta itu tak
    akan pernah ketemu.
    """
    if orang.tanpa_nik:
        return "Nama", orang.nama
    return "NIK", orang.nik


def _cocok(opsi: str, mau: str) -> bool:
    """Apakah pilihan dropdown ini yang dimaksud."""
    o = (opsi or "").strip().lower()
    if mau == "NIK":
        return o == "nik"
    if mau == "Nama":
        return o == "nama"
    return "tiket" in o


def _pilih_mode_cari(halaman, hasil: dict, jejak: list, mau: str = "NIK") -> bool:
    """
    Ubah mode pencarian menjadi "NIK", "Nama", atau "Nomor Tiket" - ketiga
    pilihan yang memang disediakan portal.

    Nilai bawaannya berbeda antar halaman h "Nomor Tiket" di halaman
    pendaftaran, "Nama" di halaman pelayanan h jadi pemicunya dicari dari
    beberapa kemungkinan, bukan satu nama saja.

    Mode Nama dipakai bayi tanpa NIK. Kedua halaman menyediakannya - halaman
    pendaftaran dan halaman pelayanan sama-sama menawarkan "Nomor Tiket",
    "NIK", dan "Nama" (dibaca langsung dari portal, 3 Sep).
    """
    for kandidat in ("NIK", "Nama", "Nomor Tiket", "No. Tiket"):
        if _cocok(kandidat, mau) and portal.ada_pemicu(halaman, kandidat):
            hasil["keterangan"] += f" | cari via: {mau} (sudah)"
            return True
    for awal in ("Nama", "NIK", "Nomor Tiket", "No. Tiket"):
        if _cocok(awal, mau) or not portal.ada_pemicu(halaman, awal):
            continue
        opsi = portal.buka_dan_rekam(halaman, awal)
        jejak.append({"tahap": "8_opsi_jenis_pencarian", "dari": awal, "opsi": opsi})
        pilih = next((o for o in opsi if _cocok(o, mau)), "")
        if pilih and portal.klik_opsi_baru(halaman, pilih):
            hasil["keterangan"] += f" | cari via: {mau} (dari {awal})"
            halaman.wait_for_timeout(600)
            return True
        portal.tutup_dropdown(halaman)
    hasil["keterangan"] += f" | mode pencarian {mau} gagal dipilih"
    return False


def _pilih_mode_nik(halaman, hasil: dict, jejak: list) -> bool:
    """Nama lama, tetap dipakai pemanggil yang memang selalu mencari via NIK."""
    return _pilih_mode_cari(halaman, hasil, jejak, "NIK")


# Form yang boleh DITIMPA saat mode sapu, walau portal sudah menandainya
# selesai. Dicocokkan dari JUDUL barisnya, bukan id: judulnya sama di semua
# kategori, sedangkan id-nya berbeda-beda.
#
# Sengaja cuma satu: form ini pernah terisi salah oleh robot sendiri (5,5 lalu
# 30,30 - lihat form.py). Menimpa form yang sudah diisi PETUGAS adalah hal
# terakhir yang boleh dilakukan sembarangan, jadi daftarnya ditulis satu per
# satu dan hanya berlaku pada alur "Pelayanan - Selesai (sapu)".
def boleh_ditimpa(judul: str) -> bool:
    """
    Apakah baris ini termasuk yang boleh diisi ulang saat mode sapu.

    Daftarnya datang dari pengaturan `timpa form`, BUKAN dari kode - lihat
    `config.TIMPA_FORM`. Dulu daftarnya tetap dan memuat dua form sekaligus,
    sehingga jalan perbaikan Kesehatan Jiwa ikut menimpa jawaban Tingkat
    Aktivitas Fisik yang sudah benar.
    """
    mau = [x.strip() for x in (config.TIMPA_FORM or "").split(",") if x.strip()]
    return any(re.search(pola, judul or "", re.I) for pola in mau)


def mode_sapu() -> bool:
    """Alur "Pelayanan - Selesai (sapu)": peserta di tab Selesai ikut dibuka."""
    return config.TAHAP.strip().lower() == "pelayanan_sapu"


# Satu-satunya baris data di tabel - dipakai bila namanya tidak cocok.
SATU_BARIS_JS = r"""() => {
  const b = [...document.querySelectorAll('tr')]
    .map((t, i) => ({i, teks: (t.innerText || '').trim(),
                     tombol: t.querySelectorAll('button').length}))
    .filter(x => x.tombol > 0 && x.teks.length > 20);
  return b.length === 1 ? b[0].i : -1;
}"""


def cari_baris(halaman, orang: Peserta, hasil: dict):
    """
    Baris peserta di tabel yang SEDANG tampil, atau None.

    NAMA BUKAN KUNCI YANG BISA DIPERCAYA. Portal menuliskan nama menurut
    Dukcapil, dan itu kerap berbeda dari CSV - beda huruf besar-kecil, beda
    gelar, "M. ADI" lawan "Muhammad Adi". Mencocokkan `tr:has-text(nama)`
    saja membuat peserta yang barisnya JELAS ADA di layar dinyatakan tidak ada;
    pada jalan skrining TBC 7 Sep itu menimpa beberapa peserta sekaligus
    - padahal langkah pendaftaran mereka sendiri sudah mencatat
    "nama beda, dipakai satu-satunya baris hasil NIK".

    Karena itu ada jalan kedua: bila tabel ini SUDAH DISARING lewat NIK -
    dibuktikan dengan membaca isi kotak pencariannya, bukan diandaikan - maka
    satu-satunya baris data yang tersisa memang orangnya. Kalau kotak
    pencariannya ternyata kosong (mis. tersapu bersih waktu ganti tab), jalan
    kedua ini TIDAK dipakai: baris tunggal di daftar yang tak tersaring bisa
    milik siapa saja.
    """
    calon = portal.baris_bernama(halaman, orang.nama)
    if calon.count():
        return calon.first

    kolom = _kolom_cari(halaman)
    isi_kotak = ""
    try:
        if kolom is not None:
            isi_kotak = re.sub(r"[^0-9]", "", kolom.input_value() or "")
    except Exception:
        isi_kotak = ""
    if isi_kotak != (orang.nik or "").strip():
        return None

    try:
        satu = halaman.evaluate(SATU_BARIS_JS)
    except Exception:
        return None
    if satu < 0:
        return None
    hasil["keterangan"] += " | nama beda, dipakai satu-satunya baris hasil NIK"
    return halaman.locator("tr").nth(satu)


def buka_dari_pelayanan(halaman, orang: Peserta, hasil: dict, jejak: list,
                        alamat: str = "", siapkan=None) -> bool:
    """
    Buka halaman pemeriksaan peserta lewat halaman PELAYANAN.

    Begitu pemeriksaan dimulai, peserta hilang dari halaman pendaftaran, jadi
    jalur masuknya berbeda: ganti mode pencarian ke NIK -> ketik NIK -> Enter
    -> pilih tab "Sedang Pemeriksaan" -> tekan "Mulai" pada barisnya.

    `alamat` dan `siapkan` ada untuk murid: halaman pelayanannya berbeda
    (`/ckg-pelayanan-sekolah`) dan daftarnya kosong sampai filter Sekolah +
    Kelas dipasang. Selain dua hal itu, langkahnya persis sama - jadi tidak
    dibuatkan salinan alur tersendiri.
    """
    halaman.goto(alamat or config.HAL_PELAYANAN, wait_until="domcontentloaded")
    portal.tunggu_siap(halaman, portal.js_dan(
        portal.JS_TIDAK_MEMUAT,
        portal.js_atau("() => document.querySelectorAll('tr').length > 1",
                       portal.js_ada_teks("Belum Pemeriksaan"),
                       portal.js_ada_teks("filter sekolah"))),
        config.TUNGGU_MUNCUL_MS, "halaman pelayanan termuat")
    if siapkan is not None and not siapkan(halaman, hasil):
        return False
    _rekam(halaman, jejak, "8_halaman_pelayanan")

    mode, nilai = kunci_cari(orang, hasil)
    if not nilai:
        hasil["keterangan"] += f" | {mode} kosong: tak ada yang bisa dicari"
        return False

    _pilih_mode_cari(halaman, hasil, jejak, mode)
    portal.tunggu_siap(halaman,
                       portal.ADA_KOLOM_NIK if mode == "NIK" else portal.js_ada_kolom_cari(),
                       800, f"kolom {mode} siap")

    kolom = _kolom_cari(halaman)
    if kolom is None:
        hasil["keterangan"] += " | kolom pencarian tidak ketemu"
        simpan_gambar(halaman, f"pelayanan_{orang.baris_csv}")
        return False
    try:
        _ketik_cari(halaman, kolom, nilai)
        kolom.press("Enter")
    except Exception as e:
        hasil["keterangan"] += f" | kolom cari gagal: {type(e).__name__}"
        return False
    portal.tunggu_siap(
        halaman, portal.js_atau(portal.js_ada_nama(orang.nama),
                                portal.js_ada_teks("Tidak ada data")),
        3000, "hasil pencarian pelayanan")

    # Tab status bukan <button>, jadi diklik lewat teksnya. Status peserta
    # tidak selalu "Sedang Pemeriksaan" — bisa masih "Belum" bila pemeriksaan
    # gagal dimulai, jadi tabnya dicoba berurutan sampai barisnya muncul.
    baris = None
    tak_terklik = []

    # TAB YANG SUDAH TERBUKA DILIHAT LEBIH DULU - sebelum satu pun tab diklik.
    #
    # Halaman ini terbuka pada "Belum Pemeriksaan", dan di situlah peserta yang
    # baru saja dikonfirmasi hadir berada; pencarian NIK barusan pun sudah
    # menyaring tabelnya ke satu baris. Jadi begitu halaman tampil, BARISNYA
    # SUDAH ADA DI LAYAR - lengkap dengan tombol "Mulai".
    #
    # Yang dilakukan versi lama justru mengklik "Sedang Pemeriksaan" lebih
    # dulu, yaitu MENINGGALKAN baris yang sudah di tangan. Dan tab "Belum"
    # tidak bisa dikunjungi kembali karena labelnya berangka ("Belum
    # Pemeriksaan 936") - lihat `portal.klik_tab`. Hasilnya: macro berhenti di
    # halaman daftar pelayanan tanpa pernah menekan "Mulai", persis yang
    # terlihat pada jalan skrining TBC 7 Sep.
    #
    # Status pesertanya dibaca dari BARISNYA SENDIRI, bukan dari tab mana yang
    # sedang menyala: tiap baris menuliskan statusnya di salah satu kolomnya
    # ("... Puskesmas Koja Belum lengkap Belum Pemeriksaan Mulai Lihat"). Itu
    # sumber yang lebih pasti, dan tetap membuat aturan "yang di tab Selesai
    # dilewati" bekerja seperti biasa.
    def catat_tab(baris_ketemu, dari: str):
        try:
            teks = " ".join((baris_ketemu.inner_text() or "").split())
        except Exception:
            teks = ""
        tab_baris = next((s for s in ("Selesai Pemeriksaan", "Sedang Pemeriksaan",
                                      "Belum Pemeriksaan") if s in teks), "")
        hasil["tab_pelayanan"] = tab_baris
        hasil["keterangan"] += f" | tab ({dari}): {tab_baris or 'tak terbaca'}"

    baris = cari_baris(halaman, orang, hasil)
    if baris is not None:
        catat_tab(baris, "sudah terbuka")

    # URUTANNYA BELUM -> SEDANG -> SELESAI, mengikuti perjalanan peserta.
    #
    # Dulu "Sedang Pemeriksaan" didahulukan, dan itu keliru dua kali: peserta
    # yang baru dikonfirmasi hadir SELALU ada di "Belum", dan tab itulah yang
    # sudah terbuka saat halaman tampil - jadi langkah pertama macro justru
    # meninggalkan baris yang sudah di layar. Diamati pengguna, 7 Sep:
    # "macro cek Sedang, kemudian balik ke Belum, kemudian ke Selesai".
    urutan = () if baris is not None else ("Belum Pemeriksaan", "Sedang Pemeriksaan",
                                           "Selesai Pemeriksaan")
    for tab in urutan:
        tanda_tab = portal.tanda_tabel(halaman)
        # `klik_tab`, bukan `klik_teks`: label tabnya berubah jadi "Belum
        # Pemeriksaan 1" begitu ada antreannya. Lihat `portal.klik_tab`.
        #
        # Tab yang GAGAL diklik dicatat. Dulu cuma `continue` tanpa jejak, jadi
        # "tak ada di ketiga tab" tidak bisa dibedakan dari "dua tab dilihat,
        # satu tak pernah terbuka" - dan justru yang tak terbuka itu tempat
        # orangnya.
        if not portal.klik_tab(halaman, tab):
            tak_terklik.append(tab)
            continue
        portal.tunggu_siap(halaman, portal.js_ada_nama(orang.nama), 1200,
                           f"tab {tab}", dasar_ms=200)
        portal.tunggu_beda(halaman, tanda_tab, 1300, f"tab {tab} berubah", dasar_ms=0)
        # Tabel yang BERUBAH belum tentu tabel yang SUDAH TERISI: baris rangka
        # abu-abu juga mengubahnya. Tanpa ini baris dibaca saat masih kosong
        # dan pesertanya dinyatakan tak ada di tab ini.
        portal.tunggu_siap(halaman, portal.JS_TIDAK_MEMUAT, 6000,
                           f"tab {tab} selesai memuat")
        baris = cari_baris(halaman, orang, hasil)
        if baris is not None:
            hasil["keterangan"] += f" | tab: {tab}"
            hasil["tab_pelayanan"] = tab
            break

    # Peserta di tab "Selesai Pemeriksaan" SUDAH diinput. Berhenti di sini:
    # tidak ada tombol Mulai di barisnya, dan membuka halaman detailnya hanya
    # membuang waktu untuk menemukan daftar layanan yang memang sudah penuh.
    # Peserta di tab "Selesai Pemeriksaan" SUDAH diinput menurut portal - tapi
    # "selesai" itu keputusan portal tentang ORANGNYA, bukan jaminan tiap
    # formnya terisi. Keduanya memang tidak saling bicara: seorang balita pernah berada
    # di tab Selesai dengan 7 dari 10 form kosong.
    #
    #   alur biasa  -> dilewati, cepat, tidak dibuka sama sekali
    #   mode sapu   -> tetap dibuka, lalu form yang masih kosong diisi
    if hasil.get("tab_pelayanan", "").startswith("Selesai") and not mode_sapu():
        hasil["keterangan"] += " | sudah diinput sebelumnya — dilewati"
        hasil["status"] = "sudah_pelayanan"
        _rekam(halaman, jejak, "8b_sudah_selesai")
        return False
    if baris is None:
        hasil["keterangan"] += " | peserta tak ada di ketiga tab"
        if tak_terklik:
            hasil["keterangan"] += (" (tab TIDAK TERBUKA: " + ", ".join(tak_terklik)
                                    + " - jadi belum semua tab benar-benar dilihat)")
    _rekam(halaman, jejak, "8b_hasil_pencarian_pelayanan")

    if baris is None:
        # Jaring terakhir: baris tunggal di tab yang SEDANG tampil, tanpa
        # syarat kotak pencarian. Ketiga tab sudah disisir `cari_baris` dengan
        # syarat yang lebih ketat, jadi yang sampai sini memang sisa-sisanya.
        try:
            satu = halaman.evaluate(SATU_BARIS_JS)
        except Exception:
            satu = -1
        if satu < 0:
            hasil["keterangan"] += " | peserta tidak ketemu di daftar pelayanan"
            # Dibedakan dari kegagalan lain: peserta yang tidak ada di daftar
            # bukan soal alat yang gagal, melainkan datanya yang perlu dicek
            # (NIK salah, belum terdaftar, atau salah sekolah/kelas).
            #
            # KECUALI bila ada tab yang tidak pernah terbuka. Tab yang belum
            # dilihat belum menjawab apa pun, jadi "tidak ada" bukan kesimpulan
            # yang sah melainkan kegagalan alat - dan `tidak_ditemukan` membuat
            # pesertanya tidak pernah dicoba lagi.
            hasil["status"] = "gagal_mulai" if tak_terklik else "tidak_ditemukan"
            # TIKET ITU BUKTI PESERTANYA ADA - aturan yang sudah berlaku di
            # alur sekolah, sekarang berlaku juga di sini. Nomor tiket baru
            # saja diterbitkan portal atas pendaftaran ini; kalau sesudah itu
            # ia tidak ketemu di ketiga tab, yang bermasalah pengindeksan
            # portal, bukan datanya. Pada 18 Sep enam peserta skrining TBC
            # divonis `tidak_ditemukan` padahal tiketnya sudah terbit - dan
            # vonis itu membuat mereka tidak pernah dicoba lagi.
            if hasil["status"] == "tidak_ditemukan" and (hasil.get("tiket") or "").strip():
                hasil["keterangan"] += (f" | tiket {hasil['tiket']} sudah terbit, jadi"
                                        " pesertanya ADA - portal belum mengindeksnya,"
                                        " layak dicoba lagi")
                hasil["status"] = "gagal_konfirmasi"
            simpan_gambar(halaman, f"pelayanan_{orang.baris_csv}")
            return False
        hasil["keterangan"] += " | nama beda, dipakai satu-satunya baris hasil NIK"
        baris = halaman.locator("tr").nth(satu)
    jejak.append({"tahap": "8c_baris_pelayanan", "tombol": _tombol_baris(baris)})

    # "Mulai" dicocokkan persis lebih dulu: pencocokan longgar juga mengenai
    # "Mulai Pemeriksaan", yang belum tentu tombol yang sama.
    diklik = False
    for cara, nama in ((portal.klik_tombol_persis, "Mulai"),
                       (portal.klik_tombol, "Mulai")):
        try:
            if cara(halaman, nama, timeout=5_000):
                diklik = True
                break
        except Exception:
            continue
    if not diklik and hasil.get("tab_pelayanan", "").startswith("Selesai"):
        # TERBUKTI 18 Agustus 2026: baris di tab "Selesai" TETAP memakai tombol
        # "Mulai", jadi cabang ini hampir tidak pernah terpakai - tiga peserta
        # pertama (tiga peserta) semuanya terbuka lewat
        # "Mulai" biasa di atas.
        #
        # Tetap dipertahankan sebagai jaring: bila suatu saat portal mengganti
        # tombolnya, yang terjadi bukan kegagalan diam-diam melainkan laporan
        # berisi tombol yang BENAR-BENAR ADA di barisnya - cukup sekali jalan
        # untuk tahu nama barunya, tanpa menebak.
        ada = _tombol_baris(baris)
        for nama in ("Detail", "Lihat", "Lihat Detail", "Periksa", "Input Data",
                     "Hasil", "Lihat Hasil"):
            if nama in ada and portal.klik_tombol_persis(halaman, nama, timeout=4_000):
                hasil["keterangan"] += f" | dibuka lewat: {nama}"
                diklik = True
                break
        if not diklik:
            hasil["keterangan"] += (" | tab Selesai: tak ada tombol pembuka yang "
                                    f"dikenal. Tombol di barisnya: {ada}")
            simpan_gambar(halaman, f"sapu_selesai_{orang.baris_csv}")
            return False
    if not diklik:
        hasil["keterangan"] += " | tombol 'Mulai' tak ditemukan"
        simpan_gambar(halaman, f"mulai_{orang.baris_csv}")
        return False
    hasil["keterangan"] += " | tombol Mulai diklik"
    halaman.wait_for_timeout(4000)
    _rekam(halaman, jejak, "9_setelah_mulai")
    return True


# Status per baris layanan. Sinyalnya BERBEDA antara dua tabel di halaman ini:
#   Pemeriksaan Mandiri -> ikon `icon-success.svg` (berwarna) = selesai,
#                          `icon-success-gray.svg` = belum;
#   Pelayanan oleh Nakes -> teks "selesai diperiksa" / "dalam pemeriksaan",
#                          dan sejak akhir Sep 2026 "Selesai Pemeriksaan" /
#                          "Belum Pemeriksaan" / "Sedang Pemeriksaan".
#
# TULISAN BARU ITU MEMBUAT SWEEP BERPUTAR TANPA AKHIR. Portal mengganti kata
# statusnya tanpa mengubah apa pun yang lain; pola lama tidak mengenainya,
# jadi status baris Nakes terbaca `null` - "tidak tahu" - dan `_belum_selesai`
# memperlakukan "tidak tahu" sebagai "belum". Rekaman 29 Sep (CKG Sekolah)
# memperlihatkan Gizi, Kusta, Skabies, Gigi sudah bertuliskan "Selesai
# Pemeriksaan" di putaran 2 dan 3, tapi tetap masuk daftar kerja - sehingga
# form yang sudah terisi dibuka dan diisi lagi di setiap putaran.
#
# Pola lama TIDAK dibuang: bila portal kembali ke tulisan semula, atau
# sebagian halaman masih memakainya, keduanya tetap terbaca.
# Tombol aksinya SELALU berteks "Input Data", jadi tombol bukan penanda selesai.
STATUS_BARIS = """() => {
  const SEMUA_BARIS = '[id^="rowfrm"], [id^="row-FRM"]';
  const keluar = [];
  document.querySelectorAll(SEMUA_BARIS).forEach(row => {
    let n = row, wadah = row;
    for (let i = 0; i < 7 && n; i++) {
      n = n.parentElement;
      if (!n) break;
      if (n.querySelectorAll(SEMUA_BARIS).length > 1) break;
      wadah = n;
    }
    const teks = (wadah.innerText || '').toLowerCase();
    const gbr = [...wadah.querySelectorAll('img')].map(g => g.getAttribute('src') || '').join(' ');
    let selesai = null;
    if (/selesai diperiksa|selesai pemeriksaan/.test(teks)) selesai = true;
    else if (/dalam pemeriksaan|belum pemeriksaan|sedang pemeriksaan/.test(teks)) selesai = false;
    else if (/icon-success-gray/.test(gbr)) selesai = false;
    else if (/icon-success\\.svg/.test(gbr)) selesai = true;
    keluar.push({id: row.id, selesai, judul: (wadah.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 70)});
  });
  return keluar;
}"""


# Baris layanan yang BOLEH dikerjakan � disalin dari daftar `T` pada penghitung
# sisa (Remaining) macro V4.5. Daftar layanan peserta memuat baris lain yang
# memang tidak diisi (mis. Kadar CO, RDT Malaria, Hepatitis); mengisi semua yang
# terlihat berarti mencatat pemeriksaan yang tidak dilakukan.
FORM_TARGET = frozenset([
    "rowfrm000006", "rowfrm000007", "rowfrm000008", "rowfrm000027", "rowfrm000028",
    "rowfrm000029", "rowfrm000032", "rowfrm000034", "rowfrm000038", "rowfrm000040",
    "rowfrm000042", "rowfrm000051", "rowfrm000055", "rowfrm000056", "rowfrm000059",
    "rowfrm000060", "rowfrm000064", "rowfrm000067", "rowfrm000088", "rowfrm000093",
    "rowfrm000099", "rowfrm000101", "rowfrm000138", "rowfrm000169", "rowfrm000172",
    "rowfrm000180", "rowfrm000182", "rowfrm000184", "rowfrm000198", "rowfrm000199",
    "rowfrm000201", "rowfrm000256", "rowfrm000265",
])


# Nama layanan + bagiannya ("Pemeriksaan Mandiri" / "Pelayanan oleh Nakes"),
# supaya catatan pengerjaan menyebut form apa yang diisi, bukan sekadar id.
INFO_BARIS = """() => {
  const SEMUA_BARIS = '[id^="rowfrm"], [id^="row-FRM"]';
  const rapi = s => (s || '').replace(/\\s+/g, ' ').trim();
  // Judul bagian = elemen daun bertulisan persis salah satu dari dua ini.
  const judul = [...document.querySelectorAll('*')].filter(e =>
      e.children.length === 0 &&
      /^(Pemeriksaan Mandiri|Pelayanan oleh Nakes)$/i.test(rapi(e.innerText)));
  const keluar = {};
  document.querySelectorAll(SEMUA_BARIS).forEach(row => {
    // Bagian = judul TERAKHIR yang letaknya sebelum baris ini di urutan DOM.
    let bagian = '';
    judul.forEach(j => {
      if (j.compareDocumentPosition(row) & Node.DOCUMENT_POSITION_FOLLOWING) {
        bagian = rapi(j.innerText);
      }
    });
    // Nama layanan = teks pembungkus baris, dibuang kata status dan tombolnya.
    let n = row, w = row;
    for (let i = 0; i < 7 && n; i++) {
      n = n.parentElement;
      if (!n) break;
      if (n.querySelectorAll(SEMUA_BARIS).length > 1) break;
      w = n;
    }
    const nama = rapi(w.innerText)
      .replace(/\\b(Ya|Tidak)\\b/g, ' ')
      .replace(/Selesai diperiksa|Dalam Pemeriksaan|Belum Pemeriksaan|Input Data|Lihat/gi, ' ')
      .replace(/\\s+/g, ' ').trim();
    keluar[row.id] = {bagian, nama: nama.slice(0, 70)};
  });
  return keluar;
}"""


# Form CKG SEKOLAH — nomornya sama sekali berbeda dari dewasa/lansia (tidak
# satu pun beririsan), jadi memakai `FORM_TARGET` di alur sekolah membuat
# SELURUH baris dilewati dan peserta ditutup tanpa satu form pun terisi.
#
# Disalin dari `CKG Sekolah/KATALOG LAYANAN PER KELAS.md`, gabungan SD sampai
# SMA. Kelas menentukan mana yang muncul, jadi gabungan aman: yang tidak
# muncul tidak akan dikerjakan.
#
# Tiga yang SENGAJA tidak masuk daftar (keputusan yang sudah diambil dulu):
# Kadar CO 000186, RDT Malaria 000117, Pemeriksaan Hepatitis 000257.
NOMOR_SEKOLAH = frozenset("""
    000097 000109 000110 000112 000113 000114 000115 000118 000121 000122
    000123 000124 000125 000126 000129 000130 000176 000181
    000119 000127 000128 000131 000137 000195 000197 000199 000201 000262
    000263 000266
""".split())

_NOMOR = re.compile(r"(\d{6})\s*$")


def _dari_sekolah(orang) -> bool:
    """Sama aturannya dengan `pekerjaan.kategori_sekolah`, tanpa impor melingkar."""
    pilihan = config.KATEGORI.strip().lower()
    if pilihan == "sekolah":
        return True
    # Balita memakai alur pendaftaran dewasa - bukan alur murid yang mencari
    # lewat Sekolah+Kelas. Dinyatakan tegas supaya tidak menumpang nilai bawaan.
    if pilihan in ("dewasa", "balita"):
        return False
    return bool(getattr(orang, "dari_sekolah", False))


# Daftar form BALITA (0-6 th) - disalin dari "Balita/KATALOG FORM BALITA.md",
# yang dibaca langsung dari portal pada 2026-08-03 dari dua pasien nyata,
# lengkap dengan keputusan pengguna. Bukan turunan dari satu kali jalan.
#
# ATURANNYA DAFTAR LEWAT, BUKAN DAFTAR TARGET. Katalog itu menetapkan:
# "Kerjakan setiap baris rowfrm yang muncul, KECUALI yang ada di daftar lewat."
# Bedanya menentukan: set form balita BERUBAH TOTAL antara 11 dan 12 bulan, dan
# masih bergeser tiap tahun sesudahnya. Daftar-putih akan diam-diam melewatkan
# form umur yang belum pernah kita lihat - persis yang menimpa seorang balita, yang
# ditutup `tuntas` dengan 7 dari 10 formnya kosong.
#
# Daftar lewat isinya tetap: 7 skrining bayi baru lahir + 2 Talasemia + M-CHAT 2.
LEWAT_BALITA = frozenset([
    "rowfrm000011",   # Penyakit Jantung Bawaan       - skrining bayi baru lahir
    "rowfrm000082",   # Pengambilan Darah Tumit       - skrining bayi baru lahir
    "rowfrm000012",   # Hasil SHK, G6PD, HAK          - skrining bayi baru lahir
    "rowfrm000083",   # Tes Konfirmasi SHK, G6PD, HAK - skrining bayi baru lahir
    "rowfrm000079",   # Edukasi Warna Kulit & Tinja   - skrining bayi baru lahir
    "rowfrm000240",   # Hasil Kramer Bayi Kuning      - skrining bayi baru lahir
    "rowfrm000252",   # Skrining Bayi Kuning 14-28 hr - skrining bayi baru lahir
    "rowfrm000105",   # Skrining Talasemia            - keputusan pengguna
    "rowfrm000024",   # Skrining Lanjutan Talasemia   - keputusan pengguna
    "rowfrm000019",   # M-CHAT 2 Lanjutan             - keputusan pengguna
])

# Ke-21 form yang SUDAH dikenal katalog. Tidak dipakai untuk menyaring - hanya
# supaya form yang muncul di luar keduanya bisa dilaporkan sebagai hal baru.
FORM_BALITA = frozenset([
    "rowfrm000010", "rowfrm000016", "rowfrm000017", "rowfrm000018",
    "rowfrm000021", "rowfrm000085", "rowfrm000086", "rowfrm000095",
    "rowfrm000096", "rowfrm000106", "rowfrm000110", "rowfrm000119",
    "rowfrm000131", "rowfrm000171", "rowfrm000175", "rowfrm000178",
    "rowfrm000195", "rowfrm000198", "rowfrm000199", "rowfrm000201",
    "rowfrm000260",
])


def _dari_balita(orang) -> bool:
    """Balita memakai alur pendaftaran dewasa, tapi daftar formnya sendiri."""
    if config.KATEGORI.strip().lower() == "balita":
        return True
    return bool(getattr(orang, "dari_balita", False))


def _target(id_baris: str, sekolahan: bool, balita: bool = False) -> bool:
    """Apakah baris ini boleh dikerjakan."""
    if balita:
        return id_baris not in LEWAT_BALITA
    if not sekolahan:
        return id_baris in FORM_TARGET
    # Mandiri memakai `rowfrm000XXX`, Nakes `row-FRM000XXX` — nomornya yang
    # menentukan, bukan awalannya.
    m = _NOMOR.search(id_baris)
    return bool(m and m.group(1) in NOMOR_SEKOLAH)


def _belum_selesai(status: list[dict], sekolahan: bool = False,
                   balita: bool = False) -> list[str]:
    """Id baris target yang belum selesai. Baris di luar daftar target diabaikan."""
    return [s["id"] for s in status
            if _target(s["id"], sekolahan, balita) and s["selesai"] is not True]


def _url_balik(halaman, cadangan: str) -> str:
    """
    URL daftar layanan yang benar.

    Jebakan yang sudah terbukti di macro: URL form memuat query
    `redirectUrl=...detail-pemeriksaan...`, sehingga pemeriksaan berbasis
    potongan teks menganggap URL form itu sendiri sebagai URL daftar layanan.
    Karena itu host dan pathname harus diurai betulan.
    """
    return halaman.evaluate(
        """(cadangan) => {
             const sah = u => { try { const x = new URL(u);
                 return /sehatindonesiaku/i.test(x.host) && /detail-pemeriksaan/i.test(x.pathname);
             } catch (e) { return false; } };
             if (sah(location.href)) return location.href;
             try {
               const r = new URL(location.href).searchParams.get('redirectUrl');
               if (r && sah(r)) return r;
             } catch (e) {}
             return cadangan;
           }""", cadangan)


# HALAMAN APA YANG SEDANG TERBUKA - dibaca dari host & path yang DIURAI, bukan
# dari potongan teks URL: alamat form.kemkes.go.id memuat "detail-pemeriksaan"
# di dalam redirectUrl-nya, dan pemeriksaan `"detail-pemeriksaan" in url`
# membuat macro mengira sudah kembali ke daftar padahal masih di form.
KEADAAN_HALAMAN = r"""() => {
  const h = location.host, p = location.pathname;
  // Layar galat server: halaman kosong berisi satu baris saja, mis.
  // "429 Too Many Requests" (judul tab "429") - terlihat di browser pengguna
  // 6 Okt 2026, di form.kemkes.go.id, saat 4 browser bekerja bersamaan.
  const isi = ((document.body && document.body.innerText) || '').trim();
  if (/^(429|502|503|504)$/.test((document.title || '').trim())
      || (isi.length < 300 && /too many requests|service unavailable|bad gateway|gateway time-?out/i.test(isi))) {
    return 'dibatasi';
  }
  if (/sehatindonesiaku/i.test(h) && /detail-pemeriksaan/i.test(p)) {
    return document.querySelectorAll('[id^="rowfrm"], [id^="row-FRM"]').length
      ? 'daftar' : 'daftar_memuat';
  }
  if (/form\.kemkes/i.test(h)) {
    if (document.querySelectorAll('.sd-question').length) return 'form';
    const t = (document.body.innerText || '').trim();
    if (/memuat|loading|mohon tunggu/i.test(t)) return 'memuat';
    return 'tertahan';
  }
  return 'lain';
}"""

# Soal yang belum terjawab di form yang sedang terbuka (yang terlihat saja).
SOAL_KOSONG = r"""() => {
  let n = 0;
  document.querySelectorAll('.sd-question').forEach(q => {
    if (q.offsetParent === null) return;
    const r = q.querySelectorAll('input[type=radio]');
    if (r.length) { if (![...r].some(x => x.checked)) n++; return; }
    const dd = q.querySelector('.sd-dropdown');
    if (dd) { if (/sd-dropdown--empty/.test(String(dd.className || ''))) n++; return; }
    const isian = [...q.querySelectorAll('input.sd-input, textarea')]
      .filter(e => e.offsetParent !== null);
    if (isian.length && isian.some(e => !String(e.value || '').trim())) n++;
  });
  return n;
}"""

# Pesan galat SurveyJS yang terlihat (mis. angka di luar rentang yang diizinkan).
PESAN_GALAT_FORM = r"""() => [...document.querySelectorAll(
    '.sd-question__erbox, .sd-error, .sv-string-viewer--error, [role=alert]')]
  .filter(e => e.offsetParent !== null)
  .map(e => (e.innerText || '').replace(/\s+/g, ' ').trim())
  .filter(Boolean).slice(0, 3).join(' / ')"""

TUNGGU_KEADAAN_JELAS = ("() => { const k = (" + KEADAAN_HALAMAN + ")(); "
                        "return k === 'daftar' || k === 'form' || k === 'tertahan' "
                        "|| k === 'dibatasi'; }")


JEDA_DIBATASI = (15, 30, 45, 60, 90)      # detik, makin lama makin panjang


def tunggu_dibatasi(halaman, ke: int, catat) -> None:
    """
    Portal membalas "429 Too Many Requests": TUNGGU dulu, baru muat ulang.

    429 berarti portal sengaja menolak karena permintaan terlalu rapat. Memuat
    ulang seketika menambah permintaan dan memperpanjang pembatasannya - jadi
    jedanya bertingkat, dan ditunggu sepotong-sepotong supaya halaman tetap
    "hidup" bagi Playwright.
    """
    jeda = JEDA_DIBATASI[min(ke, len(JEDA_DIBATASI) - 1)]
    catat(f"portal membatasi permintaan (429/galat server) - tunggu {jeda} detik lalu muat ulang")
    for _ in range(jeda):
        halaman.wait_for_timeout(1_000)
    try:
        halaman.reload(wait_until="domcontentloaded")
    except Exception:
        pass


def pulihkan_sesudah_kirim(halaman, orang, url_daftar: str, timpa: bool = False,
                           catat=None) -> None:
    """
    Pastikan halaman kembali ke daftar layanan sesudah sebuah form dikirim.

    Sesudah Kirim portal KADANG tertahan di layar kosong bertombol "Kembali
    ke Halaman Utama". Dimuat ulang, layar itu bisa jadi tiga hal (pengamatan
    pengguna, 6 Okt 2026):
      - form yang sama, SUDAH terisi  -> cukup Kirim lagi;
      - form yang sama, BELUM terisi  -> isi, lalu Kirim;
      - daftar layanan                -> selesai di sini; sweep membaca status
                                         tiap baris dan melanjutkan yang belum.
    Dulu macro mengira layar itu sudah daftar layanan (lihat KEADAAN_HALAMAN)
    lalu diam di sana sampai divonis "daftar layanan kosong".
    """
    catat = catat or (lambda _s: None)
    muat_ulang = 0
    kirim_ulang = 0
    dibatasi = 0
    for _ in range(16):
        portal.tunggu_kondisi(halaman, TUNGGU_KEADAAN_JELAS, 8_000)
        try:
            k = halaman.evaluate(KEADAAN_HALAMAN)
        except Exception:
            k = "lain"
        if k in ("daftar", "daftar_memuat"):
            return
        if k == "dibatasi":
            # Tidak memakan jatah muat ulang biasa: setelah jeda, halamannya
            # bisa kembali sebagai form (terisi/belum) atau daftar layanan,
            # dan masing-masing ditangani di putaran berikutnya.
            if dibatasi >= len(JEDA_DIBATASI):
                break
            tunggu_dibatasi(halaman, dibatasi, catat)
            dibatasi += 1
            continue
        if k == "form" and kirim_ulang < 3:
            kirim_ulang += 1
            kosong = halaman.evaluate(SOAL_KOSONG)
            if kosong == 0:
                # Sudah terisi tapi tampil lagi untuk KEDUA kalinya: portal
                # menolak isiannya, bukan sekadar tertahan. seorang murid
                # (7 Okt, gula darah 68) dikirim sembilan kali tanpa pernah
                # tersimpan. Pesan penolakannya dibaca dan dicatat, tangkapan
                # layar disimpan, dan pengiriman dihentikan.
                if kirim_ulang >= 2:
                    pesan = halaman.evaluate(PESAN_GALAT_FORM)
                    catat("portal menolak isian form" + (f": {pesan}" if pesan else
                          " (tanpa pesan terlihat)") + " - pengiriman dihentikan, cek manual")
                    simpan_gambar(halaman, f"form_ditolak_{getattr(orang, 'baris_csv', '')}")
                    break
                catat("form tampil lagi & sudah terisi - langsung Kirim")
                form.kirim(halaman)
            else:
                catat(f"form tampil lagi, {kosong} soal kosong - diisi lalu Kirim")
                galat = form.isi_satu_form(halaman, orang, timpa)
                if galat:
                    catat(f"pengisian ulang: {galat}")
            portal.tutup_popup_galat(halaman)
            continue
        if muat_ulang >= 3:
            break
        muat_ulang += 1
        catat(f"tertahan sesudah Kirim ({k}) - muat ulang ke-{muat_ulang}")
        try:
            halaman.reload(wait_until="domcontentloaded")
        except Exception:
            break
    # Tetap tidak lepas: kembali ke daftar layanan lewat alamatnya. Verifikasi
    # status baris di pemanggil menentukan apakah form ini perlu diulang.
    catat("tidak pulih dengan muat ulang - kembali ke daftar layanan")
    try:
        halaman.goto(_url_balik(halaman, url_daftar), wait_until="domcontentloaded")
    except Exception:
        pass


def kerjakan_form(halaman, orang: Peserta, id_baris: str, url_daftar: str,
                  timpa: bool = False, catat=None) -> str:
    """Buka satu baris layanan, isi formnya, lalu kembali ke daftar layanan."""
    baris = halaman.locator(f'[id="{id_baris}"]')
    if not baris.count() and buka_kelompok(halaman):
        halaman.wait_for_timeout(400)
    if not baris.count():
        # Daftar layanan kadang ter-render bertahap: baris lain sudah ada,
        # yang ini menyusul. Ditunggu dulu sebentar sebelum divonis hilang.
        portal.tunggu_kondisi(
            halaman, f"() => !!document.getElementById('{id_baris}')", 6_000)
        if not baris.count():
            return "baris tidak ada"
    tombol = baris.locator('button:has-text("Input Data")')
    sasaran = tombol.first if tombol.count() else baris.first
    try:
        sasaran.scroll_into_view_if_needed(timeout=3_000)
        sasaran.click(timeout=8_000)
    except Exception as e:
        # Klik yang gagal biasanya bukan karena tombolnya hilang, melainkan
        # karena popup galat portal menutupi halaman. Tutup lalu coba sekali
        # lagi sebelum menyerah.
        pesan = portal.tutup_popup_galat(halaman)
        if not pesan:
            return f"gagal membuka: {type(e).__name__}"
        try:
            sasaran.click(timeout=8_000)
        except Exception as e2:
            return f"gagal membuka setelah popup '{pesan}': {type(e2).__name__}"
    # Tunggu form benar-benar ter-render, bukan menunggu sekian detik dan
    # berharap. `isi_satu_form` toh punya penantiannya sendiri, jadi kalau
    # waktu habis di sini prosesnya tetap lanjut seperti dulu.
    portal.tunggu_kondisi(halaman, portal.ADA_SOAL, 12_000)

    galat = form.isi_satu_form(halaman, orang, timpa)

    # Popup galat bisa muncul saat Kirim. Kalau dibiarkan, ia akan
    # menghalangi pembukaan form berikutnya, bukan hanya form ini.
    pesan = portal.tutup_popup_galat(halaman)
    if pesan:
        galat = (galat + " | " if galat else "") + f"popup galat: {pesan}"

    # Kembali ke daftar layanan, apa pun hasilnya - termasuk bila portal
    # tertahan di layar "Kembali ke Halaman Utama" (lihat pulihkan_sesudah_kirim).
    portal.tunggu_kondisi(
        halaman, "() => /detail-pemeriksaan/.test(location.pathname)", 6_000)
    pulihkan_sesudah_kirim(halaman, orang, url_daftar, timpa, catat)
    portal.tunggu_kondisi(halaman, portal.ADA_BARIS_LAYANAN, 12_000)
    if galat:
        return galat

    # Verifikasi ke daftar layanan, bukan sekadar percaya bahwa tombol Kirim
    # terklik: form yang ditolak validasi tetap "terkirim" dari sisi klik,
    # sehingga tanpa pengecekan ini laporannya bisa menyebut berhasil padahal
    # baris itu masih kosong.
    for _ in range(6):
        baris_ini = next((s for s in halaman.evaluate(STATUS_BARIS)
                          if s["id"] == id_baris), None)
        if baris_ini is None or baris_ini["selesai"] is True:
            return ""
        halaman.wait_for_timeout(700)
    return "terkirim tapi baris belum tercatat selesai"


# KELOMPOK LAYANAN YANG TERLIPAT MENGHILANGKAN BARISNYA DARI HALAMAN.
#
# Sejak akhir Sep 2026 daftar layanan dikelompokkan: "Skrining Gizi, Tekanan
# Darah, dan Gula Darah ...", "Tuberkulosis - Skrining Nakes ...", dan bagian
# Mandiri sendiri di bawah "Jumlah Pemeriksaan (x/y)". Tiap kelompok punya
# tombol lipat. Diuji langsung di halaman dewasa 29 Sep: melipat kelompok Gizi
# MEMBUANG ketiga barisnya dari DOM (36 -> 33 baris), bukan cuma
# menyembunyikannya. Macro yang membaca halaman itu tidak akan pernah tahu
# form Gizi, Tekanan Darah, dan Gula Darah ada.
#
# Bawaannya semua kelompok terbuka, jadi ini penjaga, bukan perbaikan atas
# kejadian nyata. Tanpanya pun peserta tidak akan ditutup keliru - penjaga
# "baris hilang" di `selesaikan_layanan` menahannya - tapi form di kelompok
# terlipat tidak akan pernah diisi.
#
# Tombol lipat dikenali dari bentuknya: tombol lebar (`w-full p-4`) berikon,
# di luar baris layanan. Tombol menu samping bentuknya lain (`pl-3 pr-4
# py-2`), jadi tidak ikut. Kelompok dianggap terlipat bila induk tombolnya
# tidak memuat satu baris layanan pun.
_JS_BUKA_KELOMPOK = r"""() => {
  const BARIS = '[id^="rowfrm"], [id^="row-FRM"]';
  let dibuka = 0;
  document.querySelectorAll('button').forEach(b => {
    if (!b.classList.contains('p-4') || !b.classList.contains('w-full')) return;
    if (!b.querySelector('svg') || b.closest(BARIS)) return;
    if (b.dataset.kelompokKosong) return;
    const induk = b.parentElement;
    if (induk && induk.querySelectorAll(BARIS).length === 0) {
      b.dataset.dibukaMacro = '1';
      b.click();
      dibuka++;
    }
  });
  return dibuka;
}"""

# Kelompok yang SUDAH terbuka tapi memang tidak berisi baris ikut terklik di
# atas - dan klik itu justru melipatnya. Dikembalikan, lalu ditandai supaya
# tidak disentuh lagi pada pembacaan berikutnya.
_JS_KEMBALIKAN_KOSONG = r"""() => {
  const BARIS = '[id^="rowfrm"], [id^="row-FRM"]';
  let dikembalikan = 0;
  document.querySelectorAll('button[data-dibuka-macro]').forEach(b => {
    delete b.dataset.dibukaMacro;
    const induk = b.parentElement;
    if (induk && induk.querySelectorAll(BARIS).length === 0) {
      b.click();
      b.dataset.kelompokKosong = '1';
      dikembalikan++;
    }
  });
  return dikembalikan;
}"""


def buka_kelompok(halaman) -> int:
    """Buka setiap kelompok layanan yang terlipat. Kembalikan jumlah yang dibuka."""
    try:
        dibuka = halaman.evaluate(_JS_BUKA_KELOMPOK)
    except Exception:
        return 0
    if dibuka:
        halaman.wait_for_timeout(700)
        try:
            dibuka -= halaman.evaluate(_JS_KEMBALIKAN_KOSONG)
        except Exception:
            pass
    return max(0, dibuka)


def _jumlah_baris(halaman) -> int:
    """Berapa baris layanan yang benar-benar terbaca sekarang."""
    try:
        return len(halaman.evaluate(STATUS_BARIS))
    except Exception:
        return 0


def tunggu_daftar_tenang(halaman, batas_ms: int = 8_000,
                         diam_ms: int = 1_500) -> int:
    """
    Tunggu sampai jumlah baris daftar layanan BERHENTI BERTAMBAH.

    KENAPA "ADA BARIS" TIDAK CUKUP. Portal merender daftar ini bertahap, dan
    setiap penantian di jalur ini - `ADA_BARIS_LAYANAN` sesudah Mulai
    Pemeriksaan, dan sesudah kembali dari sebuah form - puas begitu baris
    PERTAMA muncul. Rekaman sweep membuktikannya: putaran 1 membaca 17 baris,
    putaran 2 membaca 24; di kesempatan lain 34 lalu 43. Baris yang belum
    sempat ada saat daftar dibaca akan dicoba diklik dan dilaporkan "baris
    tidak ada" - 96 kegagalan form di seluruh riwayat, semuanya berbunyi itu.

    Yang ditunggu bukan angka tertentu (jumlah baris berbeda tiap peserta),
    melainkan angka yang TIDAK BERUBAH lagi selama `diam_ms`. Bila memang sudah
    tenang sejak awal, ongkosnya hanya satu periode diam.
    """
    jeda = max(150, diam_ms // 2)
    sisa = batas_ms
    jumlah = _jumlah_baris(halaman)
    tenang = 0
    while sisa > 0:
        halaman.wait_for_timeout(jeda)
        sisa -= jeda
        kini = _jumlah_baris(halaman)
        # Selama tirai "Memuat data" masih ada, diamnya tidak berarti apa-apa.
        if not halaman.evaluate(portal.JS_TIDAK_MEMUAT):
            tenang, jumlah = 0, kini
            continue
        if kini == jumlah and kini > 0:
            tenang += jeda
            if tenang >= diam_ms:
                break
        else:
            tenang = 0
        jumlah = kini
    return jumlah


def pastikan_daftar(halaman, hasil: dict, jejak: list, orang=None) -> bool:
    """
    Pastikan daftar layanan ter-render; muat ulang halaman bila kosong.

    DAFTAR KOSONG TIDAK BOLEH DIANGGAP "SEMUA SUDAH SELESAI". Tanpa penjaga
    ini, nol baris membuat sweep berhenti pada putaran pertama, status menjadi
    "layanan_selesai" dengan nol form terisi, dan penjaga "Selesaikan Layanan"
    pun ikut lolos karena ia juga membaca nol sisa - peserta ditutup tanpa satu
    form pun terisi, statusnya jadi `tuntas`, dan sejak itu ia DILEWATI
    SELAMANYA pada tiap jalan ulang. Kerusakan yang tidak bisa dibatalkan.

    Refresh hanya dijalankan bila memang kosong, jadi peserta normal tidak
    kehilangan waktu sedetik pun.
    """
    batas = max(1, config.REFRESH_DAFTAR)
    for percobaan in range(1, batas + 1):
        # Percobaan awal diberi waktu singkat: pemanggilnya sudah menunggu
        # daftar ini sebelum masuk sini, jadi kalau masih kosong, refresh jauh
        # lebih cepat menolong daripada menunggu lebih lama. Percobaan terakhir
        # diberi ruang paling besar sebelum benar-benar menyerah.
        sabar = 6_000 if percobaan == batas else 2_500
        portal.tunggu_kondisi(halaman, portal.ADA_BARIS_LAYANAN, sabar, 200)
        jumlah = _jumlah_baris(halaman)
        if jumlah:
            # Ada baris != daftarnya lengkap. Ditunggu tenang dulu, kalau tidak
            # sweep menyusun daftar kerjanya dari tabel yang masih separuh.
            penuh_ = tunggu_daftar_tenang(halaman)
            if penuh_ > jumlah:
                hasil["keterangan"] += f" | daftar layanan lengkap: {jumlah} -> {penuh_} baris"
                jumlah = penuh_
            if percobaan > 1:
                hasil["keterangan"] += (f" | daftar layanan muncul setelah "
                                        f"{percobaan - 1}x muat ulang")
            return True
        if percobaan < batas:
            # MASIH DI HALAMAN FORM, BUKAN DAFTAR LAYANAN.
            #
            # Rekaman SMPN 136 (6 Okt 2026, 4 browser sekaligus): 127 kejadian
            # "daftar kosong", dan pada SEMUANYA layar menampilkan sebuah form
            # (Kebugaran Jasmani, Gigi, Gula Darah, Kusta, ...) yang belum
            # terjawab - form.kemkes.go.id lambat, formnya baru muncul setelah
            # macro berhenti menunggu. Memuat ulang di sini hanya memuat ulang
            # FORM itu lagi, dua kali, lalu peserta divonis layanan_sebagian.
            # Jadi: isi form yang sudah terbuka itu, lalu kembali lewat
            # redirectUrl-nya ke daftar layanan.
            try:
                k = halaman.evaluate(KEADAAN_HALAMAN)
            except Exception:
                k = "lain"
            if orang is not None and k in ("dibatasi", "form", "tertahan", "memuat"):
                # Layar 429, form yang terbuka, atau layar tertahan: ditangani
                # handler yang sama dengan sesudah Kirim - tunggu/muat ulang,
                # isi form bila belum terisi, Kirim bila sudah, lalu kembali ke
                # daftar layanan. Sweep melanjutkan dari status tiap baris.
                pulihkan_sesudah_kirim(
                    halaman, orang, _url_balik(halaman, halaman.url),
                    catat=lambda s: hasil.__setitem__("keterangan", hasil["keterangan"] + f" | {s}"))
                continue
            try:
                di_form = ("form.kemkes.go.id" in halaman.url
                           or bool(halaman.evaluate(portal.ADA_SOAL)))
            except Exception:
                di_form = False
            if di_form:
                balik = _url_balik(halaman, "")
                if orang is not None:
                    galat = form.isi_satu_form(halaman, orang)
                    hasil["keterangan"] += (" | tertahan di halaman form - "
                                            + (f"gagal diisi ({galat})" if galat else "diisi"))
                    portal.tutup_popup_galat(halaman)
                # Diurai betul, bukan dicari potongan teksnya: URL form memuat
                # "detail-pemeriksaan" di dalam redirectUrl-nya (lihat _url_balik).
                from urllib.parse import urlparse
                u = urlparse(halaman.url)
                sudah_kembali = "sehatindonesiaku" in u.netloc and "detail-pemeriksaan" in u.path
                try:
                    if balik and not sudah_kembali:
                        halaman.goto(balik, wait_until="domcontentloaded")
                    elif not balik:
                        halaman.reload(wait_until="domcontentloaded")
                except Exception:
                    break
                continue
            try:
                halaman.reload(wait_until="domcontentloaded")
            except Exception:
                break

    hasil["keterangan"] += (f" | daftar layanan KOSONG setelah {batas - 1}x muat ulang "
                            "- peserta tidak ditutup, akan dicoba lagi")
    if orang is not None:
        simpan_gambar(halaman, f"daftar_kosong_{orang.baris_csv}")
    _rekam(halaman, jejak, "14x_daftar_kosong")
    return False


def sweep_layanan(halaman, orang: Peserta, hasil: dict, jejak: list) -> None:
    """
    Kerjakan semua baris layanan yang belum selesai, berulang sampai tuntas.

    Diulang beberapa putaran karena portal ini tidak stabil: satu form bisa
    gagal ter-render sekali lalu berhasil pada percobaan berikutnya.
    """
    url_daftar = _url_balik(halaman, halaman.url)
    sekolahan = _dari_sekolah(orang)
    balita = _dari_balita(orang)
    selesai, gagal = [], {}
    # FORM YANG MERUSAK HALAMAN DICATAT, BUKAN DITABRAK TERUS.
    #
    # Ada form yang sesudah dikirim membuat daftar layanan kembali KOSONG dan
    # tidak pulih walau dimuat ulang - pada seorang peserta (18 Sep) itu "Tekanan
    # Darah". Karena daftar kerjanya selalu disusun ulang dengan urutan yang
    # sama, tiap percobaan berikutnya menabrak form yang sama lagi, dan
    # sembilan form lain yang sebenarnya sehat tidak pernah tersentuh.
    #
    #   perusak  - sudah sekali merusak; dikerjakan PALING BELAKANG.
    #   beracun  - merusak untuk KEDUA kalinya; tidak dicoba lagi peserta ini.
    perusak: dict = {}
    beracun: set = set()
    beracun_label: dict = {}
    sudah_ditimpa: set = set()
    target_awal: set = set()
    galat_popup = 0

    # Daftar yang tidak ter-render harus dibereskan DULU. Kalau tetap kosong,
    # peserta ini ditinggalkan apa adanya - jangan sekali-kali ditutup.
    if not pastikan_daftar(halaman, hasil, jejak, orang):
        hasil["status"] = "gagal_detail"
        return
    for putaran in range(1, config.SWEEP_PUTARAN + 1):
        # Popup galat yang tertinggal dari form sebelumnya akan memblokir
        # SELURUH sisa sweep, jadi dibersihkan di awal tiap putaran.
        pesan = portal.tutup_popup_galat(halaman)
        if pesan:
            galat_popup += 1
            hasil["keterangan"] += f" | popup galat ditutup: {pesan}"
        # Tiap putaran menyusun ULANG daftar kerjanya, jadi tiap putaran juga
        # harus membaca tabel yang sudah tenang - bukan hanya putaran pertama.
        tunggu_daftar_tenang(halaman)
        terbuka = buka_kelompok(halaman)
        if terbuka:
            hasil["keterangan"] += f" | {terbuka} kelompok layanan terlipat dibuka"
            tunggu_daftar_tenang(halaman)
        status = halaman.evaluate(STATUS_BARIS)
        if not status and not pastikan_daftar(halaman, hasil, jejak, orang):
            # Kosong di tengah sweep: yang sudah terisi tetap tercatat, tapi
            # peserta ini tidak boleh ditutup.
            hasil["keterangan"] += f" | form terisi: {len(selesai)}"
            hasil["status"] = "layanan_sebagian"
            return
        if not status:
            status = halaman.evaluate(STATUS_BARIS)
        sisa = _belum_selesai(status, sekolahan, balita)
        # Mode sapu: form tertentu diisi ULANG walau portal menandainya selesai.
        # Hanya sekali per peserta - kalau tidak, tiap putaran akan mengisinya
        # lagi karena portal terus menandainya selesai, dan sweep berputar sia-sia.
        if mode_sapu():
            timpa = [s["id"] for s in status
                     if s["selesai"] is True and s["id"] not in sudah_ditimpa
                     and _target(s["id"], sekolahan, balita)
                     and boleh_ditimpa(s.get("judul", ""))]
            if timpa:
                sudah_ditimpa.update(timpa)
                sisa = list(dict.fromkeys(list(sisa) + timpa))
                # NAMANYA DISEBUT, bukan cuma jumlahnya. Menimpa jawaban yang
                # sudah ada tidak bisa dibatalkan, jadi berkas hasil harus
                # menjawab "yang mana?" tanpa perlu membuka portal. Waktu
                # keterangannya hanya berbunyi "2 form", satu form yang ikut
                # tertimpa tanpa diminta baru ketahuan dari layar - bukan dari
                # laporan (7 Sep).
                nama_timpa = [b.get("judul", "")[:38] for b in status
                              if b["id"] in timpa]
                hasil["keterangan"] += (f" | DITIMPA (mode sapu) {len(timpa)} form: "
                                        + "; ".join(nama_timpa))
        # Yang pernah merusak halaman ditaruh di ujung, yang sudah dua kali
        # merusak tidak ikut sama sekali - supaya form yang sehat kebagian
        # dikerjakan lebih dulu, bukan ikut mati di belakang satu form rusak.
        if perusak or beracun:
            sehat = [i for i in sisa if i not in perusak and i not in beracun]
            akhir = [i for i in sisa if i in perusak and i not in beracun]
            dilewati_racun = [i for i in sisa if i in beracun]
            sisa = sehat + akhir
            if dilewati_racun and putaran > 1:
                nama = "; ".join(beracun_label.get(i, i)[:38] for i in dilewati_racun)
                hasil["keterangan"] += (f" | {len(dilewati_racun)} form dilewati karena"
                                        f" dua kali merusak daftar: {nama}")
        diabaikan = [s["id"] for s in status if not _target(s["id"], sekolahan, balita)]
        jejak.append({"tahap": f"15_sweep_{putaran}", "sisa": len(sisa),
                      "diabaikan": diabaikan, "status": status})
        if putaran == 1 and diabaikan:
            hasil["keterangan"] += f" | dilewati (bukan target): {len(diabaikan)}"
        # AUDIT: form apa saja yang MASIH KOSONG saat peserta ini dibuka.
        #
        # Angka "form terisi: N" saja tidak menjawab pertanyaan "yang mana?".
        # Judulnya dicatat sekali, di putaran pertama, sebelum satu pun form
        # dikerjakan - sesudah itu daftarnya berubah dan potretnya tidak lagi
        # menggambarkan keadaan awal. Yang ditimpa sengaja tidak ikut: form itu
        # memang sudah terisi, hanya isinya yang dibetulkan.
        if putaran == 1:
            kosong = [b.get("judul", "") for b in status
                      if b["id"] in sisa and b["id"] not in sudah_ditimpa]
            if kosong:
                daftar = "; ".join(k[:38] for k in kosong[:12])
                lanjut = " ..." if len(kosong) > 12 else ""
                hasil["keterangan"] += f" | AUDIT {len(kosong)} form kosong: {daftar}{lanjut}"
            else:
                hasil["keterangan"] += " | AUDIT: semua form sudah terisi"
        # Daftar target DIKUMPULKAN dari semua putaran, bukan dipotret sekali di
        # putaran pertama. Portal merender daftar ini bertahap - rekaman sweep
        # menunjukkan 17 baris di putaran 1 lalu 24 di putaran 2 (dan 34 lalu
        # 43 di peserta lain). Potret putaran pertama karenanya bisa kekurangan
        # baris, dan penjaga "Selesaikan Layanan" yang memakainya akan menutup
        # peserta yang formnya belum lengkap - lalu ia dilewati SELAMANYA pada
        # tiap jalan ulang. Himpunan yang hanya bertambah tidak bisa tertipu
        # begitu: baris yang terlambat muncul tetap masuk hitungan.
        sebelum_target = len(target_awal)
        target_awal |= {s["id"] for s in status if _target(s["id"], sekolahan, balita)}
        if putaran > 1 and len(target_awal) > sebelum_target:
            hasil["keterangan"] += (f" | daftar bertambah di putaran {putaran}: "
                                    f"{sebelum_target} -> {len(target_awal)} target")
        if not sisa:
            break
        # Nama & bagian tiap baris dibaca sekali per putaran, selagi daftar
        # layanan masih terbuka � sesudah masuk form, halamannya berganti.
        try:
            info = halaman.evaluate(INFO_BARIS)
        except Exception:
            info = {}

        for id_baris in sisa:
            if config.MAKS_FORM and len(selesai) >= config.MAKS_FORM:
                break
            galat = kerjakan_form(halaman, orang, id_baris, url_daftar,
                                  timpa=id_baris in sudah_ditimpa,
                                  catat=lambda s, _id=id_baris: hasil.__setitem__(
                                      "keterangan", hasil["keterangan"] + f" | {_id}: {s}"))
            ket = info.get(id_baris, {})
            label = " - ".join(x for x in (ket.get("bagian"), ket.get("nama")) if x) or id_baris
            if galat:
                gagal[label] = galat
                # "baris tidak ada" berarti halamannya yang bermasalah, bukan
                # formnya. Dimuat ulang sekarang supaya putaran berikutnya
                # bekerja pada daftar yang utuh.
                if "baris tidak ada" in galat:
                    # DAFTAR YANG TIDAK PULIH TIDAK DIGEDOR BERULANG-ULANG.
                    #
                    # Sesudah satu form tertentu, halaman detail kadang kembali
                    # KOSONG dan tidak pulih walau dimuat ulang. Versi lama
                    # tetap meneruskan ke baris berikutnya, jadi tiap baris
                    # sisa membayar dua kali muat ulang untuk daftar yang sama
                    # kosongnya - pada seorang peserta (18 Sep) sepuluh kali berturut
                    # dengan pesan yang sama persis, lalu diulang tiga kali
                    # sebagai satu peserta penuh.
                    #
                    # Nama formnya DICATAT. Tanpa itu, catatan hasil tidak
                    # pernah menyebut form mana yang merusak halamannya -
                    # padahal itu satu-satunya keterangan yang berguna.
                    if not pastikan_daftar(halaman, hasil, jejak, orang):
                        # Sebelum menyerah: BUKA ULANG alamat daftar layanan.
                        # Memuat ulang halaman form yang rusak memang tidak
                        # menolong - yang dibutuhkan kembali ke daftarnya.
                        try:
                            halaman.goto(url_daftar, wait_until="domcontentloaded")
                            portal.tunggu_kondisi(halaman, portal.ADA_BARIS_LAYANAN, 8_000)
                        except Exception:
                            pass
                        pulih = _jumlah_baris(halaman) > 0
                        beracun_label[id_baris] = label
                        if id_baris in perusak:
                            beracun.add(id_baris)
                        else:
                            perusak[id_baris] = label
                        hasil["keterangan"] += (
                            f" | daftar layanan kosong sesudah form {label!r}"
                            + (" - pulih setelah dibuka ulang, form lain diteruskan"
                               if pulih else " dan tidak pulih - putaran ini dihentikan"))
                        if not pulih:
                            break
                        continue
            else:
                selesai.append(id_baris)
                gagal.pop(label, None)
            print(f"        {label}: {galat or 'terisi'}")
        if config.MAKS_FORM and len(selesai) >= config.MAKS_FORM:
            hasil["keterangan"] += f" | berhenti di batas MAKS_FORM={config.MAKS_FORM}"
            break

    hasil["keterangan"] += f" | form terisi: {len(selesai)}"
    if gagal:
        hasil["keterangan"] += f" | gagal: {gagal}"
    hasil["status"] = "layanan_selesai" if not gagal else "layanan_sebagian"

    if config.SELESAIKAN_LAYANAN:
        selesaikan_layanan(halaman, hasil, jejak, sekolahan, target_awal, balita)


def selesaikan_layanan(halaman, hasil: dict, jejak: list,
                       sekolahan: bool = False, wajib: set | None = None,
                       balita: bool = False) -> None:
    """
    Tekan "Selesaikan Layanan" � hanya bila semua baris memang sudah selesai.

    Tombol ini SELALU aktif walau masih ada pemeriksaan yang kosong, jadi
    keaktifannya bukan tanda bahwa semuanya tuntas. Yang dipakai sebagai
    penentu adalah pembacaan status tiap baris.
    """
    # Yang dihitung hanya baris target: baris di luar daftar memang tidak
    # pernah diisi, jadi kalau ikut dihitung layanan tak akan pernah bisa ditutup.
    #
    # `sekolahan` WAJIB diteruskan. Daftar target murid dan dewasa tidak punya
    # satu pun nomor yang sama, jadi memeriksa murid dengan daftar dewasa
    # membuat semua barisnya dianggap "bukan target": sisa kosong, penjaga
    # lolos, dan layanan ditutup padahal belum satu form pun terisi.
    buka_kelompok(halaman)
    semua_baris = halaman.evaluate(STATUS_BARIS)

    # Baris yang HILANG dari halaman bukan baris yang selesai. Daftar layanan
    # portal ini kadang ter-render sebagian, dan penjaga yang hanya membaca
    # keadaan SEKARANG akan menyimpulkan "tidak ada sisa" lalu menutup peserta.
    # Terbukti pada 6 peserta 2026-08-11: seorang peserta ditutup `tuntas` dengan
    # 1 dari 24 baris terisi karena 17 barisnya lenyap di tengah sweep.
    if wajib:
        ada = {s["id"] for s in semua_baris}
        hilang = sorted(wajib - ada)
        if hilang:
            hasil["keterangan"] += (f" | tidak ditutup: {len(hilang)} baris hilang "
                                    f"dari daftar ({', '.join(hilang[:4])})")
            hasil["status"] = "layanan_sebagian"
            _rekam(halaman, jejak, "16x_baris_hilang")
            return

    if not semua_baris:
        # Nol baris berarti daftarnya tidak ter-render, BUKAN berarti tuntas.
        # Statusnya ikut diturunkan: "layanan_selesai" pada peserta yang
        # daftarnya tak terbaca adalah keterangan yang menyesatkan, dan status
        # itu membuatnya tidak dicoba lagi.
        hasil["keterangan"] += " | tidak ditutup: daftar layanan tidak terbaca"
        hasil["status"] = "layanan_sebagian"
        return
    # Kategorinya harus ikut, kalau tidak penjaga ini membaca daftar form
    # kategori LAIN: balita yang tujuh formnya kosong terbaca 'nol sisa'
    # lalu ditutup - dan sejak itu dilewati selamanya.
    sisa = _belum_selesai(semua_baris, sekolahan, balita)
    if sisa:
        hasil["keterangan"] += f" | belum diselesaikan: {len(sisa)} baris masih kosong"
        return
    if not portal.klik_tombol(halaman, "Selesaikan Layanan", timeout=6_000):
        # Sama seperti tombol lain: popup galat yang menutupi halaman membuat
        # tombol tampak "tidak ada". Tutup dulu, baru menyerah.
        pesan = portal.tutup_popup_galat(halaman)
        if pesan:
            hasil["keterangan"] += f" | popup galat: {pesan}"
        if not (pesan and portal.klik_tombol(halaman, "Selesaikan Layanan", timeout=6_000)):
            # ADA-TAPI-MATI berbeda dari TIDAK ADA, dan `klik_tombol`
            # mengembalikan False untuk keduanya. Dibedakan di sini karena
            # tombol yang MATI justru penanda kuat bahwa pemeriksaannya sudah
            # ditutup portal - dugaan pengguna, dan cocok dengan seorang murid
            # yang muridnya memang duduk di tab "Selesai Pemeriksaan".
            mati = halaman.evaluate(
                """() => [...document.querySelectorAll('button')].some(b =>
                     b.offsetParent !== null
                     && /selesaikan layanan/i.test(b.innerText || '')
                     && (b.disabled || b.getAttribute('aria-disabled') === 'true'))"""
            )
            hasil["keterangan"] += (" | tombol 'Selesaikan Layanan' "
                                    + ("ADA tapi MATI" if mati else "tidak ada"))
            simpan_gambar(halaman, f"selesaikan_{hasil.get('baris', '?')}")
            _rekam(halaman, jejak, "16x_selesaikan_gagal")
            # TOMBOLNYA HILANG KARENA DUA SEBAB YANG BERLAWANAN, dan halaman
            # ini bisa ditanya yang mana:
            #
            #   ada "Mulai Pemeriksaan"  -> pemeriksaannya BELUM dimulai. Form
            #       yang barusan diisi tidak tersimpan sebagai pemeriksaan,
            #       jadi ini memang belum beres dan layak diulang.
            #   tidak ada                -> seluruh form sudah terisi dan
            #       portal sudah menutup pemeriksaannya sendiri; muridnya
            #       duduk di tab "Selesai Pemeriksaan". Meninggalkannya sebagai
            #       "layanan_selesai" membuatnya terlihat seperti pekerjaan
            #       yang menggantung, padahal sudah selesai - dan status itu
            #       tidak pernah diulang sehingga tak pernah terkoreksi.
            #       Terjadi pada seorang murid (4 Sep).
            # Tombol yang MATI sudah cukup jadi jawabannya: portal hanya
            # mematikannya sesudah pemeriksaan ditutup. Yang masih perlu
            # ditanya adalah keadaan tombol TIDAK ADA.
            if not mati and halaman.evaluate(portal.js_ada_tombol("Mulai Pemeriksaan")):
                hasil["keterangan"] += (" | pemeriksaan BELUM dimulai"
                                        " (tombolnya masih 'Mulai Pemeriksaan')")
                hasil["status"] = "layanan_sebagian"
            else:
                hasil["keterangan"] += (" | seluruh form terisi dan tidak ada lagi"
                                        " yang perlu ditutup - sudah selesai")
                hasil["status"] = "sudah_pelayanan"
            return
    halaman.wait_for_timeout(1500)
    dipakai = portal.klik_salah_satu(halaman, ("Ya", "Selesai", "Konfirmasi", "Simpan"), 3_000)
    if dipakai:
        hasil["keterangan"] += f" | selesaikan: {dipakai}"
    halaman.wait_for_timeout(3000)
    _rekam(halaman, jejak, "16_selesaikan_layanan")
    hasil["status"] = "tuntas"


def buka_dan_petakan(halaman, orang: Peserta, hasil: dict, jejak: list) -> None:
    """Buka halaman pemeriksaan peserta lalu petakan daftar layanannya."""
    if not buka_dari_pelayanan(halaman, orang, hasil, jejak):
        hasil["status"] = "gagal_buka_pelayanan"
        return
    if "detail-pemeriksaan" not in halaman.url:
        hasil["status"] = "gagal_detail"
        return
    if config.TAHAP == "isi":
        # Form hanya bisa diisi sesudah pemeriksaannya DIMULAI - lihat alasan
        # lengkapnya di `penuh`. Mode "layanan" tidak ikut menekannya: ia cuma
        # membaca daftar layanan, dan menekan tombol itu mengubah keadaan
        # peserta di portal tanpa diminta.
        if not mulai_pemeriksaan(halaman, orang, hasil, jejak):
            hasil["status"] = "gagal_mulai"
            return
        petakan_layanan(halaman, hasil, jejak)
        sweep_layanan(halaman, orang, hasil, jejak)
        return
    petakan_layanan(halaman, hasil, jejak)
    intip_form(halaman, jejak, hasil)
    hasil["status"] = "dipetakan"


def jalankan(halaman, orang: Peserta, hasil: dict, jejak: list) -> None:
    """Konfirmasi hadir + mulai pemeriksaan untuk satu peserta."""
    if not konfirmasi_hadir(halaman, orang, hasil, jejak):
        hasil["status"] = "gagal_konfirmasi"
        return
    if not mulai_pemeriksaan(halaman, orang, hasil, jejak):
        hasil["status"] = "gagal_mulai"
        return
    hasil["status"] = "siap_layanan"


def penuh(halaman, orang: Peserta, hasil: dict, jejak: list) -> None:
    """
    Lanjutan sesudah pendaftaran: konfirmasi hadir -> mulai pemeriksaan ->
    isi semua form target -> (bila dinyalakan) selesaikan layanan.

    Dipakai untuk peserta baru, yang masih ada di halaman pendaftaran. Peserta
    yang pemeriksaannya sudah berjalan harus lewat `buka_dan_petakan`, sebab
    mereka tidak lagi muncul di halaman itu.
    """
    jalankan(halaman, orang, hasil, jejak)
    if hasil["status"] != "siap_layanan":
        # Peserta yang pemeriksaannya sudah berjalan HILANG dari halaman
        # pendaftaran, jadi jalur di atas selalu gagal untuknya. Jalur
        # pelayanan (cari NIK -> tab status -> Mulai) adalah satu-satunya
        # cara masuk, dan itu justru keadaan normal saat batch diulang.
        hasil["keterangan"] += " | coba lewat halaman pelayanan"
        if not buka_dari_pelayanan(halaman, orang, hasil, jejak):
            return
        # TOMBOL "Mulai" DI BARIS BUKAN "Mulai Pemeriksaan" DI HALAMAN DETAIL.
        #
        # Yang pertama cuma MEMBUKA halaman detail; yang kedua yang benar-benar
        # memulai pemeriksaan. Peserta yang masih di tab "Belum Pemeriksaan"
        # tiba di halaman detail dengan tombol "Mulai Pemeriksaan" MASIH ADA
        # dan seluruh formnya terkunci - dan jalur ini dulu langsung menyapu
        # form, jadi macro berhenti di halaman itu tanpa satu pun form terisi.
        # Terlihat pada seorang peserta (PP6-XNH, skrining TBC 7 Sep): rekamannya
        # berbunyi "Belum Pemeriksaan ... Jumlah Pemeriksaan (0/8)" dengan
        # tombolnya utuh di layar.
        #
        # `pelayanan_saja` sudah lama melakukannya, begitu pula alur sekolah;
        # hanya jalur ini yang terlewat.
        if not mulai_pemeriksaan(halaman, orang, hasil, jejak):
            hasil["status"] = "gagal_mulai"
            return
        hasil["status"] = "siap_layanan"
    if "detail-pemeriksaan" not in halaman.url:
        hasil["keterangan"] += " | tidak sampai halaman daftar layanan"
        hasil["status"] = "gagal_detail"
        return
    petakan_layanan(halaman, hasil, jejak)
    sweep_layanan(halaman, orang, hasil, jejak)


def pelayanan_saja(halaman, orang: Peserta, hasil: dict, jejak: list) -> None:
    """
    ALUR PELAYANAN: cari NIK langsung di halaman pelayanan, tanpa mendaftar.

    Untuk peserta yang sudah terdaftar dan tinggal dilayani. Bedanya dengan
    `penuh` cuma satu: tidak ada pendaftaran maupun konfirmasi hadir sama
    sekali - jadi tidak ada tiket, dan barisnya dicari lewat NIK.

    Peserta yang ternyata sudah berada di tab "Selesai Pemeriksaan" tidak punya
    tombol Mulai; itu bukan kegagalan, dan dilaporkan apa adanya supaya batch
    tidak terlihat rusak hanya karena pekerjaannya memang sudah beres.
    """
    if not buka_dari_pelayanan(halaman, orang, hasil, jejak):
        # "sudah_pelayanan" dan "tidak_ditemukan" sudah ditetapkan di dalam
        # sana; hanya sisanya yang benar-benar kegagalan langkah.
        if hasil.get("status") not in ("sudah_pelayanan", "tidak_ditemukan"):
            hasil["status"] = "gagal_mulai"
        return
    if not mulai_pemeriksaan(halaman, orang, hasil, jejak):
        hasil["status"] = "gagal_mulai"
        return
    if "detail-pemeriksaan" not in halaman.url:
        hasil["keterangan"] += " | tidak sampai halaman daftar layanan"
        hasil["status"] = "gagal_detail"
        return
    petakan_layanan(halaman, hasil, jejak)
    sweep_layanan(halaman, orang, hasil, jejak)


def simpan_jejak(jejak: list, tanda: str = "") -> str:
    """
    Tulis rekaman struktur ke berkas agar bisa dipelajari.

    `tanda` memisahkan rekaman antar pekerja saat berjalan paralel; tanpa itu
    pekerja yang selesai belakangan menimpa rekaman pekerja lainnya.
    """
    config.siapkan_folder()
    tujuan = config.HASIL / f"struktur_layanan{tanda}.json"
    tujuan.write_text(json.dumps(jejak, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(tujuan)
