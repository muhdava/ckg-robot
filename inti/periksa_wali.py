"""
Petakan bagian "Data Wali" pada formulir pendaftaran balita. HANYA MEMBACA.

    python inti\\periksa_wali.py 3172035412230000 14/12/2023

Argumennya NIK dan tanggal lahir seorang balita dari berkas datamu. Skrip ini
membuka formulir, mengisi NIK dan tanggal lahir, lalu MENUNGGU bagian Data
Wali muncul - sebab bagian itu memang baru dirender setelah portal tahu
umurnya 0-6 tahun.

Yang dilakukan: mengetik NIK, menekan Cek NIK, mengisi tanggal lahir, membaca
struktur halaman. Yang TIDAK dilakukan: menekan Selanjutnya, Daftarkan, atau
tombol apa pun yang menyimpan data. Tidak ada peserta yang terdaftar.

SEBELUM MENJALANKAN: tutup dulu jendela browser milik aplikasi. Satu folder
profil tidak bisa dipakai dua browser sekaligus.

Hasilnya ditulis ke hasil/struktur_wali.json - kirimkan berkas itu.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config                                    # noqa: E402
import portal                                    # noqa: E402
from browser import buka_browser, simpan_gambar, sudah_login   # noqa: E402

# Semua kolom isian, pilihan, dan centang beserta LABEL TERDEKATNYA. Label
# dicari dengan naik beberapa tingkat lalu mengambil teks pendek di sekitarnya -
# cara yang sama dipakai alur sungguhan untuk mengenali kolom.
PENGUMPUL = r"""() => {
  const dekat = (el) => {
    let n = el, keluar = [];
    for (let i = 0; i < 5 && n; i++) {
      n = n.parentElement;
      if (!n) break;
      const teks = (n.innerText || '').replace(/\s+/g, ' ').trim();
      if (teks && teks.length < 160) { keluar = [teks]; break; }
    }
    return keluar[0] || '';
  };
  const medan = [...document.querySelectorAll('input, select, textarea')]
    .map(e => ({
      tag: e.tagName.toLowerCase(), jenis: e.type || '', id: e.id || '',
      name: e.getAttribute('name') || '', placeholder: e.placeholder || '',
      nilai: (e.value || '').slice(0, 40),
      terlihat: e.offsetParent !== null,
      wajib: e.required || e.getAttribute('aria-required') === 'true',
      label: dekat(e),
    }));
  const tombol = [...document.querySelectorAll('button')]
    .filter(b => b.offsetParent !== null)
    .map(b => ({teks: (b.innerText || '').replace(/\s+/g, ' ').trim(),
                id: b.id || '', mati: b.disabled}));
  // Dropdown portal ini bukan <select>, melainkan <div> ber-cursor-pointer.
  const pilihan = [...document.querySelectorAll('div')]
    .filter(d => d.offsetParent !== null &&
                 getComputedStyle(d).cursor === 'pointer' &&
                 (d.innerText || '').trim().length < 60 &&
                 /pilih/i.test(d.innerText || ''))
    .map(d => ({teks: (d.innerText || '').replace(/\s+/g, ' ').trim(), id: d.id || ''}));
  const badan = (document.body.innerText || '').replace(/\s+/g, ' ');
  const i = badan.search(/Data Wali/i);
  return {
    ada_bagian_wali: i >= 0,
    kutipan_wali: i >= 0 ? badan.slice(i, i + 400) : '',
    medan, tombol, pilihan,
  };
}"""


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        raise SystemExit(2)
    nik, tgl = sys.argv[1].strip(), sys.argv[2].strip()
    try:
        lahir = datetime.strptime(tgl, "%d/%m/%Y").date()
    except ValueError:
        print(f"Tanggal lahir harus dd/mm/yyyy, bukan {tgl!r}")
        raise SystemExit(2)

    # Profil yang PALING BARU DIPAKAI, bukan `.profil-browser` bawaan. Aplikasi
    # dengan beberapa pekerja login ke `.profil-browser-1`, `-2`, dan
    # seterusnya; membuka profil bawaan berarti bertemu halaman login lagi
    # padahal sesinya sudah ada di sebelah.
    kandidat = sorted(
        (p for p in config.PROFIL_BROWSER.parent.glob(f"{config.PROFIL_BROWSER.name}*")
         if p.is_dir() and (p / "Default").exists()),
        key=lambda p: (p / "Default").stat().st_mtime, reverse=True)
    profil = kandidat[0] if kandidat else config.PROFIL_BROWSER
    print(f"Memakai profil browser: {profil.name}")

    with buka_browser(profil=profil, tampilkan=True) as (_konteks, halaman):
        halaman.goto(config.HAL_PENDAFTARAN, wait_until="domcontentloaded")
        halaman.wait_for_timeout(2500)
        # DITUNGGU, bukan disuruh menjalankan ulang. Versi pertama skrip ini
        # langsung `return` ketika belum login - dan karena browsernya dibuka
        # lewat context manager, ia ikut tertutup saat itu juga. Jendela login
        # muncul sekejap lalu hilang, jadi login tidak pernah bisa dilakukan.
        if not sudah_login(halaman):
            print("\nBelum login. Silakan login di jendela browser yang terbuka.")
            print("Skrip ini menunggu sampai 5 menit dan lanjut sendiri "
                  "begitu kamu masuk.\n")
            sisa = 300_000
            while sisa > 0 and not sudah_login(halaman):
                halaman.wait_for_timeout(2000)
                sisa -= 2000
                if sisa % 30_000 == 0:
                    print(f"   masih menunggu login… ({sisa // 1000}s tersisa)")
            if not sudah_login(halaman):
                print("Tetap belum login sesudah 5 menit. Dihentikan.")
                return
            print("Login terdeteksi. Lanjut.\n")

        portal.tunggu_siap(halaman, portal.js_ada_tombol("Daftar Baru"), 4000,
                           "halaman pendaftaran termuat")
        portal.klik_tombol(halaman, "Daftar Baru")
        portal.tunggu_siap(halaman, portal.js_terlihat("#nik"), 3000, "formulir terbuka")

        sebelum = halaman.evaluate(PENGUMPUL)
        print(f"SEBELUM tanggal lahir diisi -> bagian Data Wali ada? "
              f"{sebelum['ada_bagian_wali']}")

        halaman.locator("#nik").fill(nik)
        portal.klik_tombol(halaman, "Cek NIK")
        portal.tunggu_siap(halaman, portal.js_atau(
            portal.js_ada_tombol("Gunakan Data"),
            portal.js_terisi(r"#Nama\ Lengkap"),
            portal.js_ada_teks("tidak valid"), portal.TIDAK_VALID_JS), 4000, "jawaban Cek NIK")
        portal.klik_tombol(halaman, "Gunakan Data", timeout=3_000)

        galat = portal.isi_tanggal_lahir(halaman, lahir)
        print(f"tanggal lahir diisi: {'GAGAL - ' + galat if galat else 'berhasil'}")

        # Inilah yang ingin dibuktikan: bagian wali muncul SESUDAH umur diketahui.
        muncul = portal.tunggu_siap(halaman, portal.js_ada_teks("Data Wali"),
                                    8000, "bagian Data Wali muncul")
        halaman.wait_for_timeout(1200)
        sesudah = halaman.evaluate(PENGUMPUL)

        tujuan = config.HASIL / "struktur_wali.json"
        tujuan.parent.mkdir(parents=True, exist_ok=True)
        tujuan.write_text(json.dumps(
            {"nik": nik, "tanggal_lahir": tgl,
             "sebelum": sebelum, "sesudah": sesudah, "muncul_setelah_tanggal": muncul},
            ensure_ascii=False, indent=2), encoding="utf-8")
        simpan_gambar(halaman, "wali_balita")

        print(f"\nSESUDAH tanggal lahir diisi -> bagian Data Wali ada? "
              f"{sesudah['ada_bagian_wali']}")
        if sesudah["kutipan_wali"]:
            print("  teks bagiannya: " + sesudah["kutipan_wali"][:220])

        baru = {m["id"] or m["name"] or m["placeholder"] for m in sesudah["medan"]}
        lama = {m["id"] or m["name"] or m["placeholder"] for m in sebelum["medan"]}
        print("\nKolom yang BARU muncul sesudah tanggal lahir diisi:")
        for m in sesudah["medan"]:
            kunci = m["id"] or m["name"] or m["placeholder"]
            if kunci in baru - lama:
                print(f"   {m['tag']}/{m['jenis']:<9} id={m['id']!r} name={m['name']!r} "
                      f"wajib={m['wajib']}  label={m['label'][:70]!r}")
        print(f"\nStruktur lengkap -> {tujuan}")
        print("Tangkapan layar  -> hasil/gagal/wali_balita.png")
        print("\nTidak ada tombol simpan yang ditekan; tidak ada peserta terdaftar.")
        # Menunggu Enter hanya bila ada orang di depan terminalnya. Bila skrip
        # dijalankan tanpa terminal, menunggu masukan berarti menggantung
        # selamanya - browsernya pun tidak pernah tertutup.
        if sys.stdin and sys.stdin.isatty():
            input("Tekan Enter untuk menutup browser…")
        else:
            halaman.wait_for_timeout(1500)


if __name__ == "__main__":
    main()
