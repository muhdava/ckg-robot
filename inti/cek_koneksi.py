"""
Uji fondasi — jalankan ini LEBIH DULU sebelum yang lain.

Yang diperiksa:
  1. CSV peserta terbaca
  2. Browser bisa dibuka dengan profil menetap
  3. Portal terbuka dan status login terdeteksi

Cara pakai:
    python cek_koneksi.py

Kalau statusnya "BELUM login", login saja secara manual di jendela browser
yang terbuka, lalu tekan Enter di terminal. Sesinya akan tersimpan sehingga
run berikutnya tidak perlu login lagi.
"""
from __future__ import annotations

import config
import peserta
from browser import buka_browser, simpan_gambar, sudah_login


def main() -> int:
    print("=" * 62)
    print("UJI FONDASI — Playwright CKG")
    print("=" * 62)

    # ---------------------------------------------------------- 1. data
    try:
        semua = peserta.baca_csv()
    except FileNotFoundError:
        print(f"\n[GAGAL] CSV tidak ditemukan: {config.CSV_PESERTA}")
        return 1
    print(f"\n1. Data   : {len(semua)} peserta terbaca dari {config.CSV_PESERTA.name}")

    batch = peserta.ambil_batch(semua, config.BARIS_AWAL, config.JUMLAH_DATA)
    print(f"   Batch  : baris {config.BARIS_AWAL}..{config.BARIS_AWAL + config.JUMLAH_DATA - 1} "
          f"-> {len(batch)} peserta")
    for p in batch[:3]:
        print(f"            {p}")
    if not batch:
        print("   [PERINGATAN] Batch kosong — periksa BARIS_AWAL / JUMLAH_DATA di config.py")

    # ---------------------------------------------------------- 2 & 3. browser
    print("\n2. Browser: membuka profil menetap...")
    with buka_browser() as (konteks, halaman):
        print(f"   Profil : {config.PROFIL_BROWSER}")
        print(f"\n3. Portal : membuka {config.PORTAL}")
        try:
            halaman.goto(config.PORTAL, wait_until="domcontentloaded")
        except Exception as e:
            print(f"   [GAGAL] tidak bisa membuka portal: {type(e).__name__}")
            return 1

        halaman.wait_for_timeout(2500)
        masuk = sudah_login(halaman)
        print(f"   URL    : {halaman.url[:70]}")
        print(f"   Status : {'SUDAH login' if masuk else 'BELUM login'}")

        if not masuk:
            print("\n   >> Silakan login manual di jendela browser yang terbuka.")
            print("   >> Setelah masuk ke halaman utama, tekan Enter di sini.")
            try:
                input()
            except EOFError:
                print("   (tidak ada input — dilewati)")
            halaman.wait_for_timeout(1500)
            masuk = sudah_login(halaman)
            print(f"   Status : {'SUDAH login' if masuk else 'masih BELUM login'}")

        gambar = simpan_gambar(halaman, "cek_koneksi")
        print(f"\n   Tangkapan layar: {gambar}")

        print("\n" + "=" * 62)
        if masuk:
            print("FONDASI SIAP. Sesi login tersimpan di profil —")
            print("run berikutnya tidak perlu login lagi.")
        else:
            print("Fondasi jalan, tapi belum login. Ulangi dan login dulu.")
        print("=" * 62)
        return 0 if masuk else 2


if __name__ == "__main__":
    raise SystemExit(main())
