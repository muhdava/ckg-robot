"""
Menyiapkan Python bawaan untuk Setup.exe -> pemasang/cache/python/

Isinya Python "embeddable" resmi dari python.org (versi SAMA dengan Python
di komputer pembuat paket, 64-bit) ditambah pip. Pustaka aplikasi
(playwright, openpyxl) SENGAJA tidak ikut: playwright saja >100 MB, dan
Setup.exe harus di bawah 50 MB (batas unggah bucket Supabase). Pustaka itu
dipasang pasang.bat saat Setup berjalan - atau aplikasi.bat saat pertama
dibuka, bila waktu itu tidak ada internet.

Hasilnya disimpan dan dipakai ulang; dibuat ulang hanya bila versi Python
komputer ini berubah. Dicetak: jalur folder python yang siap dibundel.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

DI_SINI = Path(__file__).resolve().parent
CACHE = DI_SINI / "cache"
HASIL = CACHE / "python"
PENANDA = HASIL / "versi-bawaan.txt"


def main() -> None:
    if sys.maxsize <= 2 ** 32:
        sys.exit("Python pembuat paket harus 64-bit.")
    v = sys.version_info
    versi = f"{v.major}.{v.minor}.{v.micro}"
    if v.releaselevel != "final":
        sys.exit(f"Python {sys.version} bukan rilis final - pasang rilis resmi.")
    if PENANDA.exists() and PENANDA.read_text().strip() == versi and (HASIL / "Lib/site-packages/pip").exists():
        print(HASIL)
        return

    CACHE.mkdir(parents=True, exist_ok=True)
    zip_ = CACHE / f"python-{versi}-embed-amd64.zip"
    if not zip_.exists():
        url = f"https://www.python.org/ftp/python/{versi}/python-{versi}-embed-amd64.zip"
        print(f"Mengunduh {url}", file=sys.stderr)
        sementara = zip_.with_suffix(".unduh")
        urllib.request.urlretrieve(url, sementara)
        sementara.replace(zip_)

    if HASIL.exists():
        shutil.rmtree(HASIL)
    with zipfile.ZipFile(zip_) as zf:
        zf.extractall(HASIL)

    # Berkas ._pth menentukan sys.path Python embeddable secara mutlak:
    #  - folder skrip TIDAK ditambahkan otomatis, jadi ..\inti dicantumkan
    #    (server.py, run.py, dan modul-modulnya ada di sana);
    #  - "import site" diaktifkan supaya Lib\site-packages (pip, playwright)
    #    terbaca dan pip bisa memasang ke sana.
    pth = HASIL / f"python{v.major}{v.minor}._pth"
    if not pth.exists():
        sys.exit(f"{pth.name} tidak ada di paket embeddable - susunannya berubah?")
    pth.write_text(f"python{v.major}{v.minor}.zip\r\n.\r\nLib\\site-packages\r\n..\\inti\r\n\r\nimport site\r\n",
                   encoding="ascii")

    # pip dipasang memakai pip komputer ini (versinya sama persis).
    subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q",
                    "--target", str(HASIL / "Lib" / "site-packages"), "pip"], check=True,
                   stdout=sys.stderr)
    # Uji: pip jalan dari Python bawaan.
    subprocess.run([str(HASIL / "python.exe"), "-m", "pip", "--version"], check=True, stdout=sys.stderr)
    PENANDA.write_text(versi)
    print(HASIL)


if __name__ == "__main__":
    main()
