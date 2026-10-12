"""
Pemeriksa struktur halaman — dijalankan sekali untuk memetakan portal.

Kenapa perlu: sesi login portal tidak bertahan antar-proses, jadi struktur
halaman ber-login harus direkam saat kamu login. Hasilnya disimpan ke
hasil/struktur_halaman.json untuk dipakai menyusun alur otomatis.

Skrip ini HANYA MEMBACA. Tidak mengklik tombol simpan/daftar, tidak
mengubah data apa pun di portal.

Cara pakai:
    python periksa_halaman.py
"""
from __future__ import annotations

import json

import config
from browser import buka_browser, simpan_gambar, sudah_login

# JS pengumpul struktur — dijalankan di dalam halaman
PENGUMPUL = """() => {
  const vis = e => e && e.offsetParent !== null;
  const rapi = s => (s || '').replace(/\\s+/g, ' ').trim();

  const tombol = [...document.querySelectorAll('button, input[type=button], input[type=submit], a[role=button]')]
    .filter(vis)
    .map(b => rapi(b.innerText || b.value))
    .filter(t => t && t.length < 40);

  const isian = [...document.querySelectorAll('input, textarea')]
    .filter(vis)
    .map(e => ({ id: e.id || '', name: e.name || '', placeholder: e.placeholder || '',
                 tipe: e.type || e.tagName.toLowerCase(), readonly: !!e.readOnly }));

  // dropdown khas portal ini: div ber-class cursor-pointer + tinggi 2.9rem
  const dropdown = [...document.querySelectorAll('div')]
    .filter(e => { const c = String(e.className || '');
                   return vis(e) && c.includes('cursor-pointer') && c.includes('2.9rem'); })
    .map(e => {
      let label = '';
      let p = e;
      for (let i = 0; i < 6 && p; i++) {
        p = p.parentElement;
        if (!p) break;
        const kandidat = [...p.querySelectorAll('div,label,span')]
          .map(x => rapi(x.innerText))
          .find(t => t && t.length < 40 && t !== rapi(e.innerText));
        if (kandidat) { label = kandidat; break; }
      }
      return { label, nilai: rapi(e.innerText).slice(0, 30) };
    });

  const checkbox = [...document.querySelectorAll('input[type=checkbox]')]
    .map(c => ({ id: c.id || '', tersembunyi: getComputedStyle(c).opacity === '0',
                 dicentang: c.checked }));

  const tabel = [...document.querySelectorAll('table')].filter(vis).map(t => ({
    kolom: [...t.querySelectorAll('thead th, thead td')].map(th => rapi(th.innerText)).slice(0, 12),
    jml_baris: t.querySelectorAll('tbody tr').length,
  }));

  return { url: location.href, judul: document.title,
           tombol: [...new Set(tombol)], isian, dropdown, checkbox, tabel,
           cuplikan_teks: rapi(document.body.innerText).slice(0, 400) };
}"""


def rekam(halaman, nama: str, alamat: str | None = None) -> dict:
    if alamat:
        halaman.goto(alamat, wait_until="domcontentloaded")
    halaman.wait_for_timeout(3500)
    data = halaman.evaluate(PENGUMPUL)
    data["tahap"] = nama
    print(f"\n--- {nama} ---")
    print("   url    :", data["url"][:78])
    print("   tombol :", ", ".join(data["tombol"][:10]) or "-")
    print("   isian  :", len(data["isian"]), "| dropdown:", len(data["dropdown"]),
          "| checkbox:", len(data["checkbox"]), "| tabel:", len(data["tabel"]))
    return data


def main() -> int:
    hasil: list[dict] = []
    with buka_browser(tampilkan=True) as (konteks, halaman):
        halaman.goto(config.PORTAL, wait_until="domcontentloaded")
        halaman.wait_for_timeout(2500)

        if not sudah_login(halaman):
            print("\n>> Silakan LOGIN manual di jendela browser yang terbuka.")
            print(">> Setelah sampai halaman utama, tekan Enter di sini.")
            input()
            halaman.wait_for_timeout(1500)

        if not sudah_login(halaman):
            print("\n[BERHENTI] masih belum login.")
            return 2
        print("\nLogin terdeteksi. Mulai merekam struktur halaman...")

        # 1. halaman daftar/cari individu
        hasil.append(rekam(halaman, "1_cari_daftar_individu", config.HAL_PENDAFTARAN))

        # 2. form pendaftaran halaman 1 (klik "Daftar Baru")
        try:
            tombol = halaman.get_by_role("button", name="Daftar Baru").first
            if tombol.count():
                tombol.click()
                hasil.append(rekam(halaman, "2_form_pendaftaran_hal1"))
        except Exception as e:
            print("   (tidak bisa membuka 'Daftar Baru':", type(e).__name__, ")")

        simpan_gambar(halaman, "periksa_halaman")

        tujuan = config.HASIL / "struktur_halaman.json"
        tujuan.write_text(json.dumps(hasil, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nStruktur tersimpan: {tujuan}")
        print("Beri tahu Claude bahwa berkas ini sudah ada, biar alurnya disusun.")
        print("\nTekan Enter untuk menutup browser.")
        input()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
