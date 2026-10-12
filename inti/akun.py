"""
Akun pengguna aplikasi CKG Robot.

    python inti/akun.py daftar
    python inti/akun.py tambah <nama>
    python inti/akun.py sandi  <nama>      ganti kata sandi
    python inti/akun.py hapus  <nama>

KATA SANDI TIDAK PERNAH DISIMPAN, bahkan dalam bentuk terenkripsi.

Enkripsi bisa dibalik, dan kuncinya mau tak mau ikut tersimpan di folder yang
sama - jadi siapa pun yang memegang berkasnya bisa membacanya kembali. Yang
dipakai di sini pengacakan SEARAH (PBKDF2-HMAC-SHA256, 240.000 putaran, dengan
garam acak per pengguna). Dari isi `akun.dat` kata sandinya tidak bisa
dikembalikan oleh siapa pun, termasuk oleh yang membuat program ini.

Yang disimpan hanya: nama, garam, hasil pengacakan, jumlah putaran, dan waktu
dibuat. Semuanya memakai pustaka bawaan Python.
"""
from __future__ import annotations

import getpass
import hashlib
import hmac
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import config

BERKAS = config.AKAR / "akun.dat"
PUTARAN = 240_000


def _acak(sandi: str, garam: bytes, putaran: int = PUTARAN) -> str:
    return hashlib.pbkdf2_hmac("sha256", sandi.encode("utf-8"), garam, putaran).hex()


def muat() -> dict:
    if not BERKAS.exists():
        return {}
    try:
        return json.loads(BERKAS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def simpan(data: dict) -> None:
    config.siapkan_folder()
    BERKAS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def ada_akun() -> bool:
    return bool(muat())


def tambah(nama: str, sandi: str) -> None:
    nama = nama.strip().lower()
    data = muat()
    garam = os.urandom(16)
    data[nama] = {
        "garam": garam.hex(),
        "acak": _acak(sandi, garam),
        "putaran": PUTARAN,
        "dibuat": datetime.now().isoformat(timespec="seconds"),
    }
    simpan(data)


def hapus(nama: str) -> bool:
    data = muat()
    if nama.strip().lower() not in data:
        return False
    del data[nama.strip().lower()]
    simpan(data)
    return True


def periksa(nama: str, sandi: str) -> bool:
    """
    Benar bila nama + kata sandi cocok.

    `compare_digest` dipakai, bukan `==`: perbandingan biasa berhenti pada huruf
    pertama yang berbeda, dan selisih waktunya - walau sangat kecil - bisa
    dipakai menebak isi hash sedikit demi sedikit.
    """
    orang = muat().get((nama or "").strip().lower())
    if not orang:
        # Tetap hitung sekali walau namanya tak ada, supaya lamanya menjawab
        # tidak membocorkan nama mana yang terdaftar.
        _acak(sandi or "", b"kosong", 1000)
        return False
    hasil = _acak(sandi or "", bytes.fromhex(orang["garam"]),
                  int(orang.get("putaran", PUTARAN)))
    return hmac.compare_digest(hasil, orang["acak"])


# ------------------------------------------------------------------ perintah
def _baca_sandi(ajakan: str) -> str:
    """
    Baca kata sandi sambil menampilkan bintang.

    `getpass` tidak menampilkan APA PUN saat diketik. Itu aman, tapi di jendela
    hitam Windows hasilnya tidak bisa dibedakan dari papan ketik yang tidak
    berfungsi - dan orang berhenti mengetik karena mengira alatnya rusak.
    Bintang memberi tanda bahwa ketikannya terbaca, tanpa memperlihatkan isinya.
    """
    if os.name == "nt" and sys.stdin.isatty():
        try:
            import msvcrt
        except ImportError:
            msvcrt = None
        if msvcrt is not None:
            print(ajakan, end="", flush=True)
            isi: list[str] = []
            while True:
                ch = msvcrt.getwch()
                if ch in ("\r", "\n"):
                    print()
                    return "".join(isi)
                if ch == "\003":                 # Ctrl+C
                    print()
                    raise KeyboardInterrupt
                if ch in ("\b", "\x7f"):         # Backspace
                    if isi:
                        isi.pop()
                        print("\b \b", end="", flush=True)
                    continue
                if ch in ("\x00", "\xe0"):       # panah dan tombol khusus
                    msvcrt.getwch()
                    continue
                isi.append(ch)
                print("*", end="", flush=True)
    return getpass.getpass(ajakan)


def _minta_sandi() -> str:
    """Diketik sebagai bintang, jadi tidak tertinggal terbaca di layar."""
    print("  (ketikan tampil sebagai bintang — itu wajar)")
    while True:
        a = _baca_sandi("  Kata sandi baru      : ")
        if len(a) < 6:
            print("  Terlalu pendek — minimal 6 karakter.")
            continue
        b = _baca_sandi("  Ulangi kata sandinya : ")
        if a != b:
            print("  Tidak sama. Coba lagi.")
            continue
        return a


def main(argv: list[str]) -> int:
    import akun_online
    if akun_online.aktif():
        print("Aplikasi ini memakai LOGIN ONLINE - akun tidak dibuat di sini.\n"
              "  Petugas baru: buka aplikasi.bat, lalu pilih 'Daftar akun baru'.\n"
              "  Lupa sandi  : minta admin menggantinya dari halaman Kelola Petugas.")
        return 0
    perintah = argv[1].lower() if len(argv) > 1 else ""
    nama = argv[2] if len(argv) > 2 else ""

    if perintah == "daftar":
        data = muat()
        if not data:
            print("Belum ada akun. Buat dengan:  python inti/akun.py tambah <nama>")
            return 0
        print(f"{len(data)} akun di {BERKAS.name}:")
        for n, d in sorted(data.items()):
            print(f"  {n:20} dibuat {d.get('dibuat', '-')}")
        return 0

    if perintah in ("tambah", "sandi") and nama:
        data = muat()
        ada = nama.strip().lower() in data
        if perintah == "tambah" and ada:
            print(f"Akun '{nama}' sudah ada. Pakai 'sandi' untuk menggantinya.")
            return 1
        if perintah == "sandi" and not ada:
            print(f"Akun '{nama}' belum ada.")
            return 1
        tambah(nama, _minta_sandi())
        print(f"OK — akun '{nama.strip().lower()}' tersimpan di {BERKAS.name}")
        return 0

    if perintah == "hapus" and nama:
        print(f"OK — akun '{nama}' dihapus." if hapus(nama)
              else f"Akun '{nama}' tidak ada.")
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
