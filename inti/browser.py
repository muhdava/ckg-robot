"""
Lapisan browser.

Memakai profil yang MENETAP (persistent context): kamu cukup login SEKALI
secara manual, sesinya tersimpan di folder .profil-browser dan dipakai lagi
pada setiap run berikutnya. Skrip ini tidak pernah menyentuh kata sandimu.
"""
from __future__ import annotations

import contextlib
from collections.abc import Iterator

from playwright.sync_api import BrowserContext, Page, sync_playwright

import config


@contextlib.contextmanager
def buka_browser(tampilkan: bool | None = None,
                 profil: "Path | None" = None) -> Iterator[tuple[BrowserContext, Page]]:
    """
    Buka browser dengan profil menetap. Pakai lewat `with`.

    `profil` memungkinkan beberapa browser berjalan berdampingan. Satu folder
    profil TIDAK BOLEH dipakai dua browser sekaligus - Chrome akan menolak atau,
    lebih buruk, merusak profilnya. Tiap pekerja karena itu punya foldernya
    sendiri, dan itu pula yang membuat tiap pekerja bisa memakai AKUN PORTAL
    yang berbeda: sesi login menempel pada profil.
    """
    config.siapkan_folder()
    tampilkan = config.TAMPILKAN_BROWSER if tampilkan is None else tampilkan
    profil = profil or config.PROFIL_BROWSER
    profil.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        argumen = dict(
            user_data_dir=str(profil),
            headless=not tampilkan,
            slow_mo=config.PERLAMBAT_MS,
            viewport={"width": 1440, "height": 900},
            accept_downloads=True,
        )
        if tampilkan:
            # JENDELA harus memuat VIEWPORT-nya.
            #
            # `viewport=` memaksa halaman dirender 1440x900 apa pun ukuran
            # jendelanya. Tanpa baris di bawah, Chrome membuka jendela seukuran
            # bawaannya - biasanya lebih kecil - sehingga halaman yang 1440x900
            # tidak muat dan tampak terpotong di layar. Yang terpotong hanya
            # PENGLIHATAN KITA: robotnya tetap membaca dan mengklik seluruh
            # 1440x900, jadi ini soal enak dilihat, bukan soal benar-salah.
            #
            # Ukurannya dilebihkan: window-size mengatur ukuran LUAR jendela,
            # sedangkan yang harus 1440x900 adalah area isinya - bilah tab,
            # bilah alamat, dan bingkai memakan sisanya.
            argumen["args"] = ["--window-size=1456,1012", "--window-position=0,0"]
        try:
            konteks = pw.chromium.launch_persistent_context(channel=config.BROWSER, **argumen)
        except Exception:
            # Chrome tidak tersedia -> pakai Chromium bawaan Playwright
            konteks = pw.chromium.launch_persistent_context(**argumen)

        konteks.set_default_timeout(config.TIMEOUT_UMUM)
        konteks.set_default_navigation_timeout(config.TIMEOUT_PINDAH_HALAMAN)
        halaman = konteks.pages[0] if konteks.pages else konteks.new_page()
        try:
            yield konteks, halaman
        finally:
            konteks.close()


def sudah_login(halaman: Page) -> bool:
    """
    Deteksi status login di portal.

    Ciri sudah login: menu utama portal muncul (mis. "Cari/Daftarkan Individu").
    Ciri belum login: ada kolom kata sandi, atau URL memuat kata 'login'.
    """
    if "login" in halaman.url.lower():
        return False
    if halaman.locator("input[type=password]").count() > 0:
        return False
    penanda = halaman.get_by_text("Cari/Daftarkan Individu", exact=False)
    return penanda.count() > 0


def simpan_gambar(halaman: Page, nama: str) -> str:
    """Simpan tangkapan layar ke folder hasil/gagal. Kembalikan path-nya."""
    config.siapkan_folder()
    aman = "".join(c if c.isalnum() or c in "-_." else "_" for c in nama)[:80]
    tujuan = config.GAMBAR_GAGAL / f"{aman}.png"
    halaman.screenshot(path=str(tujuan), full_page=True)
    return str(tujuan)
