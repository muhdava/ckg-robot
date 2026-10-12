"""
Munculkan jendela browser milik seorang pekerja ke depan layar (Windows).

KENAPA LEWAT SISTEM OPERASI, BUKAN PLAYWRIGHT
    Playwright punya `page.bring_to_front()`, tapi objeknya TERIKAT pada utas
    yang membuatnya. Permintaan dari halaman aplikasi datang lewat utas server,
    dan memanggil objek Playwright dari utas lain membuatnya melempar galat -
    atau lebih buruk, merusak sesi pekerja yang sedang bekerja. Jadi jendelanya
    diangkat lewat Windows, tanpa menyentuh Playwright sama sekali.

BAGAIMANA JENDELA MILIK PEKERJA DIKENALI
    Bukan dari judulnya - semua jendela menampilkan portal yang sama, jadi
    judulnya kembar. Yang membedakan adalah FOLDER PROFIL: tiap pekerja
    dijalankan dengan `--user-data-dir=...\\.profil-browser-N`, dan itu terbaca
    di baris perintah prosesnya.
"""
from __future__ import annotations

import ctypes
import re
import subprocess
from ctypes import wintypes
from pathlib import Path

# Konstanta Windows yang dipakai
SW_RESTORE = 9
HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
SWP_NOMOVE, SWP_NOSIZE, SWP_SHOWWINDOW = 0x0002, 0x0001, 0x0040


def _pid_profil(profil: Path) -> set[int]:
    """PID semua proses chrome yang memakai folder profil itu."""
    # Dicocokkan dengan nama folder saja, bukan seluruh jalur: Chrome menulis
    # ulang argumennya dan pemisah jalurnya tidak selalu sama.
    #
    # DICOCOKKAN SAMPAI UJUNG ANGKANYA. Versi lama memakai `-like '*<nama>*'`,
    # dan pola itu tidak bisa membedakan ".profil-browser-1" dari
    # ".profil-browser-10" - pekerja 1 dan pekerja 10 saling mengambil jendela
    # satu sama lain. Dulu tidak pernah terlihat karena pekerjanya paling
    # banyak 4; begitu batasnya dinaikkan ke 10, cacat itu langsung hidup.
    tanda = re.escape(profil.name) + "(?![0-9])"
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='chrome.exe' or "
          "Name='msedge.exe' or Name='chromium.exe'\" | "
          "Where-Object { $_.CommandLine -match '" + tanda + "' } | "
          "Select-Object -ExpandProperty ProcessId")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=25)
    except Exception:
        return set()
    return {int(b) for b in r.stdout.split() if b.strip().isdigit()}


def _jendela_milik(pid_set: set[int]) -> list[int]:
    """Jendela utama (terlihat, berjudul) milik proses-proses itu."""
    if not pid_set:
        return []
    user32 = ctypes.windll.user32
    hasil: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def periksa(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in pid_set:
            return True
        panjang = user32.GetWindowTextLengthW(hwnd)
        if panjang <= 0:                 # jendela pembantu tanpa judul
            return True
        hasil.append(hwnd)
        return True

    user32.EnumWindows(periksa, 0)
    return hasil


def munculkan(profil: Path) -> str:
    """
    Angkat jendela browser milik profil itu ke depan.

    Kembalikan "" bila berhasil, atau keterangan singkat bila tidak - dipakai
    apa adanya sebagai pesan di halaman, supaya kegagalannya bisa dimengerti
    tanpa membuka catatan.
    """
    if not hasattr(ctypes, "windll"):
        return "hanya bisa di Windows"
    pid = _pid_profil(profil)
    if not pid:
        return f"browser untuk {profil.name} sepertinya sudah ditutup"
    jendela = _jendela_milik(pid)
    if not jendela:
        return f"jendela {profil.name} tidak ditemukan"

    user32 = ctypes.windll.user32
    hwnd = jendela[0]
    # Dicoba dua cara, dan HASILNYA DIPERIKSA sesudah tiap cara. Panggilan
    # Windows di sini "berhasil" tanpa mengangkat apa pun: `SetForegroundWindow`
    # ditolak diam-diam bila proses peminta bukan yang sedang di depan. Versi
    # pertama kode ini mengembalikan "berhasil" begitu saja - terbukti salah:
    # permintaan kedua berturut-turut dilaporkan berhasil padahal jendelanya
    # tidak bergerak sama sekali.
    for cara in (_angkat_langsung, _angkat_lewat_utas):
        try:
            cara(user32, hwnd)
        except Exception:
            continue
        if user32.GetForegroundWindow() == hwnd:
            return ""
    return (f"jendela {profil.name} ditemukan tapi Windows menolak "
            "memunculkannya - klik sendiri di bilah tugas")


def _angkat_langsung(user32, hwnd) -> None:
    """Cara biasa: pulihkan bila terkecil, naikkan sebentar, lalu minta ke depan."""
    user32.ShowWindow(hwnd, SW_RESTORE)
    bendera = SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, bendera)
    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, bendera)
    user32.SetForegroundWindow(hwnd)


def _angkat_lewat_utas(user32, hwnd) -> None:
    """
    Cara kedua: menumpang izin jendela yang SEDANG di depan.

    Windows hanya mengizinkan proses yang sedang di depan memindahkan fokus.
    Dengan `AttachThreadInput`, utas kita disambungkan sementara ke utas jendela
    depan sehingga keduanya berbagi keadaan masukan - dan permintaan fokus kita
    ikut diperlakukan sebagai permintaan dari jendela depan itu. Sambungannya
    dilepas lagi setelah selesai; membiarkannya tersambung membuat kedua utas
    saling menunggu.
    """
    depan = user32.GetForegroundWindow()
    utas_depan = user32.GetWindowThreadProcessId(depan, None)
    utas_kita = ctypes.windll.kernel32.GetCurrentThreadId()
    tersambung = bool(user32.AttachThreadInput(utas_kita, utas_depan, True))
    try:
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if tersambung:
            user32.AttachThreadInput(utas_kita, utas_depan, False)
