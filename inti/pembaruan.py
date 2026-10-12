"""
Pembaruan aplikasi dari dalam aplikasi (login online).

Alurnya:
  1. Admin menerbitkan paket (Kelola Petugas > Terbitkan pembaruan): ZIP
     diunggah ke bucket privat 'paket', lalu versi + sidik SHA-256 + ukuran
     dicatat di Supabase (admin_terbitkan).
  2. Aplikasi petugas menerima info itu tiap kali masuk (periksa_izin). Bila
     versinya lebih lama, halaman menampilkan tombol "Perbarui sekarang".
  3. Tombol itu: unduh ZIP (tautan sementara, akun petugas sendiri) ->
     cocokkan ukuran & SHA-256 -> periksa isi ZIP (versinya harus sama
     dengan yang diterbitkan) -> cadangkan berkas lama -> pasang -> mulai
     ulang aplikasi.

YANG TIDAK PERNAH DISENTUH: data/, hasil/, mentah/, profil browser, akun.dat,
cadangan, dan pengaturan.txt / inti/login_online.json yang sudah ada.

aplikasi.bat SEDANG DIJALANKAN cmd selama aplikasi hidup, dan cmd membaca
berkas .bat sedikit demi sedikit dari posisi terakhirnya - menimpanya di
tengah jalan bisa membuat cmd menjalankan potongan baris. Karena itu versi
barunya ditulis sebagai aplikasi.bat.baru; aplikasi.bat sendiri menukarnya
pada kali berikutnya dibuka.

Bila pemasangan gagal di tengah, semua berkas yang sudah ditimpa dikembalikan
dari cadangan dan berkas baru dihapus - aplikasi tetap di versi lama.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

import akun_online
import config

AKAR = config.AKAR
FOLDER = AKAR / "pembaruan"
CADANGAN = AKAR / "cadangan-versi"
NAMA_PAKET = "CKG-Robot.zip"
SIMPAN_CADANGAN = 3

# Tidak pernah ditulis, apa pun isi ZIP-nya.
# python/ = Python bawaan Setup.exe (sedang dipakai menjalankan aplikasi ini);
# pemasang/ = alat pembuat Setup, milik admin.
LEWATI_AWALAN = ("data/", "hasil/", "mentah/", ".profil-browser", "cadangan-", "pembaruan/", "alat/",
                 "supabase/", "__pycache__/", "python/", "pemasang/")
LEWATI_NAMA = {"akun.dat", ".pintasan"}
# Milik petugas: dipertahankan bila sudah ada, ditulis hanya bila belum ada.
PERTAHANKAN = {"pengaturan.txt", "inti/login_online.json"}
# Sedang dijalankan cmd: ditulis sebagai <nama>.baru (lihat docstring).
TUNDA = {"aplikasi.bat"}


class GagalPembaruan(Exception):
    pass


def lebih_baru(a: str, b: str) -> bool:
    """Versi 'tahun.bulan.tanggal[.jammenit]' - urutan teks = urutan waktu."""
    return bool(a) and (a or "") > (b or "")


def versi_dalam_zip(zf: zipfile.ZipFile) -> str:
    try:
        teks = zf.read("inti/config.py").decode("utf-8", "replace")
    except KeyError:
        return ""
    m = re.search(r'(?m)^VERSI\s*=\s*"([^"]+)"', teks)
    return m.group(1) if m else ""


# ------------------------------------------------------------------ unduh
def unduh(token: dict, harapan: dict, lapor) -> Path:
    """Unduh paket yang diterbitkan, lalu cocokkan ukuran & SHA-256-nya."""
    if not re.fullmatch(r"[0-9a-f]{64}", harapan.get("sha256", "") or ""):
        raise GagalPembaruan("Paket di server belum diterbitkan dengan benar (tanpa sidik). Hubungi admin.")
    lapor("unduh", "Meminta tautan unduhan…", 2)
    url = akun_online.tautan_unduh(token, NAMA_PAKET)
    FOLDER.mkdir(parents=True, exist_ok=True)
    tujuan = FOLDER / "unduhan.zip"
    sidik = hashlib.sha256()
    total = int(harapan.get("ukuran") or 0)
    didapat = 0
    req = urllib.request.Request(url, headers={"apikey": akun_online._kunci()})
    try:
        with urllib.request.urlopen(req, timeout=60, context=ssl.create_default_context()) as r, \
                open(tujuan, "wb") as f:
            while True:
                potong = r.read(65536)
                if not potong:
                    break
                f.write(potong)
                sidik.update(potong)
                didapat += len(potong)
                if total:
                    lapor("unduh", f"Mengunduh… {didapat // 1024} / {total // 1024} KB",
                          5 + int(60 * min(didapat, total) / total))
    except GagalPembaruan:
        raise
    except Exception as e:
        raise GagalPembaruan(f"Unduhan terputus ({type(e).__name__}). Periksa internet, lalu coba lagi.") from None
    if total and didapat != total:
        raise GagalPembaruan(f"Ukuran unduhan tidak cocok ({didapat} dari {total} bita) - unduhan tidak utuh. "
                             "Coba lagi.")
    if sidik.hexdigest() != harapan["sha256"]:
        raise GagalPembaruan("Sidik SHA-256 paket tidak cocok dengan yang diterbitkan admin - paket rusak "
                             "atau sudah diganti tanpa diterbitkan ulang. Tidak dipasang. Hubungi admin.")
    return tujuan


# ------------------------------------------------------------------ periksa
def _nama_aman(nama: str) -> str | None:
    n = nama.replace("\\", "/")
    if n.startswith("/") or re.match(r"^[A-Za-z]:", n) or any(b == ".." for b in n.split("/")):
        return None
    return n


def periksa_zip(jalur: Path, versi_harapan: str) -> None:
    try:
        with zipfile.ZipFile(jalur) as zf:
            rusak = zf.testzip()
            if rusak:
                raise GagalPembaruan(f"Isi paket rusak ({rusak}).")
            nama = zf.namelist()
            if any(_nama_aman(n) is None for n in nama):
                raise GagalPembaruan("Paket berisi jalur berkas yang tidak sah - ditolak.")
            for wajib in ("inti/server.py", "inti/config.py"):
                if wajib not in nama:
                    raise GagalPembaruan(f"Paket tidak lengkap (tidak ada {wajib}).")
            v = versi_dalam_zip(zf)
    except zipfile.BadZipFile:
        raise GagalPembaruan("Berkas unduhan bukan ZIP yang sah.") from None
    if v != versi_harapan:
        raise GagalPembaruan(f"Versi di dalam paket ({v or '?'}) tidak sama dengan yang diterbitkan "
                             f"({versi_harapan}). Tidak dipasang. Hubungi admin.")


# ------------------------------------------------------------------ pasang
def _rencana(zf: zipfile.ZipFile) -> list[tuple[str, Path, bytes]]:
    """(nama di zip, tujuan, isi) untuk setiap berkas yang memang perlu ditulis."""
    hasil = []
    akar = AKAR.resolve()
    for info in zf.infolist():
        if info.is_dir():
            continue
        nama = _nama_aman(info.filename)
        if not nama or nama in LEWATI_NAMA or nama.startswith(LEWATI_AWALAN) or nama.endswith(".pyc"):
            continue
        tujuan = AKAR / nama
        if nama in PERTAHANKAN and tujuan.exists():
            continue
        if nama in TUNDA:
            tujuan = AKAR / (nama + ".baru")
        if akar not in tujuan.resolve().parents:
            raise GagalPembaruan(f"Jalur di luar folder aplikasi ditolak: {nama}")
        isi = zf.read(info)
        asli = AKAR / nama
        if asli.exists() and asli.read_bytes() == isi:
            if tujuan != asli and tujuan.exists():
                tujuan.unlink()                      # .baru usang yang ternyata sama
            continue
        hasil.append((nama, tujuan, isi))
    return hasil


def _bersihkan_cadangan_lama() -> None:
    if not CADANGAN.exists():
        return
    lama = sorted((d for d in CADANGAN.iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime, reverse=True)
    for d in lama[SIMPAN_CADANGAN:]:
        shutil.rmtree(d, ignore_errors=True)


def pasang(jalur: Path, lapor) -> dict:
    """
    Pasang isi paket. Kembalikan ringkasan; bila gagal di tengah, semua
    dikembalikan seperti semula lalu GagalPembaruan dilempar.
    """
    with zipfile.ZipFile(jalur) as zf:
        versi_baru = versi_dalam_zip(zf)
        rencana = _rencana(zf)
    lapor("pasang", f"Memasang {len(rencana)} berkas…", 70)
    cadangan = CADANGAN / f"{config.VERSI}-{datetime.now():%Y%m%d-%H%M%S}"
    ditimpa: list[tuple[Path, Path]] = []      # (tujuan, salinan cadangan)
    baru: list[Path] = []
    try:
        for i, (nama, tujuan, isi) in enumerate(rencana):
            if tujuan.exists():
                salinan = cadangan / tujuan.relative_to(AKAR)
                salinan.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(tujuan, salinan)
                ditimpa.append((tujuan, salinan))
            else:
                baru.append(tujuan)
            tujuan.parent.mkdir(parents=True, exist_ok=True)
            sementara = tujuan.with_name(tujuan.name + ".sementara")
            sementara.write_bytes(isi)
            sementara.replace(tujuan)
            lapor("pasang", f"Memasang… {i + 1}/{len(rencana)}", 70 + int(20 * (i + 1) / max(1, len(rencana))))
    except Exception as e:
        for tujuan, salinan in ditimpa:
            try:
                shutil.copy2(salinan, tujuan)
            except Exception:
                pass
        for tujuan in baru:
            try:
                tujuan.unlink()
            except Exception:
                pass
        raise GagalPembaruan(f"Pemasangan gagal ({type(e).__name__}: {e}). Semua berkas dikembalikan "
                             "ke versi sebelumnya.") from None
    _bersihkan_cadangan_lama()
    return {"versi": versi_baru, "berkas": len(rencana),
            "pustaka_berubah": any(n == "requirements.txt" for n, _, _ in rencana),
            "cadangan": str(cadangan) if ditimpa else ""}


def pasang_pustaka(lapor) -> str:
    """requirements.txt berubah -> pasang pustakanya. Kegagalan dilaporkan, tidak membatalkan."""
    lapor("pustaka", "Memasang pustaka baru (bisa beberapa menit)…", 92)
    try:
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(AKAR / "requirements.txt")],
                           capture_output=True, text=True, timeout=900)
        return "" if r.returncode == 0 else (r.stderr or r.stdout)[-400:]
    except Exception as e:
        return f"{type(e).__name__}: {e}"


def jalankan(token: dict, harapan: dict, lapor) -> dict:
    """Seluruh proses: unduh -> periksa -> pasang (-> pustaka)."""
    mulai = time.time()
    jalur = unduh(token, harapan, lapor)
    lapor("periksa", "Memeriksa isi paket…", 67)
    periksa_zip(jalur, harapan["versi"])
    hasil = pasang(jalur, lapor)
    if hasil["pustaka_berubah"]:
        hasil["galat_pustaka"] = pasang_pustaka(lapor)
    try:
        jalur.unlink()
    except Exception:
        pass
    hasil["detik"] = round(time.time() - mulai, 1)
    return hasil
