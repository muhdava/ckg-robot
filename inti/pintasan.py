"""
Shortcut "CKG Robot" (ikon sendiri) di Desktop dan Start Menu, menuju
aplikasi.bat di folder ini. Jendela hitamnya dibuka biasa (pesan galat saat
mulai tetap terlihat); server.py sendiri mengecilkannya begitu siap.

Dipakai oleh:
  - pasang.bat              -> python inti/pintasan.py   (selalu dibuat ulang)
  - server.py saat dibuka   -> pastikan_sekali()         (petugas lama yang
                               mendapat fitur ini lewat tombol Perbarui)

Tidak dibuat otomatis bila:
  - folder ini dipasang lewat Setup.exe (ada unins000.exe) - shortcut-nya
    sudah diurus Setup, termasuk dihapus saat uninstall;
  - folder pengembang (ada .git);
  - sudah pernah dibuat (penanda .pintasan) - kalau petugas sengaja
    menghapus shortcut-nya, tidak dimunculkan lagi.
Shortcut bernama sama yang menunjuk folder CKG Robot LAIN yang masih ada
tidak ditimpa: komputer itu memang punya salinan lain yang dipakai.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
PENANDA = AKAR / ".pintasan"
NAMA = "CKG Robot"


def _ps(skrip: str, **nilai: str) -> str:
    """
    Jalankan PowerShell. Nilai diteruskan lewat variabel lingkungan CKG_*,
    bukan disisipkan ke teks perintah - jalur folder boleh berisi spasi,
    tanda petik, atau apostrof.
    """
    env = {**os.environ, **{f"CKG_{k.upper()}": v for k, v in nilai.items()}}
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                        "-Command", skrip],
                       capture_output=True, text=True, timeout=60, env=env,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[-300:])
    return r.stdout.strip()


_BUAT = r"""
$akar, $nama, $paksa = $env:CKG_AKAR, $env:CKG_NAMA, ($env:CKG_PAKSA -eq '1')
$sh = New-Object -ComObject WScript.Shell
$hasil = @()
foreach ($folder in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
    if (-not $folder) { continue }
    $lnk = Join-Path $folder ($nama + '.lnk')
    if ((Test-Path $lnk) -and -not $paksa) {
        $lama = $sh.CreateShortcut($lnk).TargetPath
        $dirLama = Split-Path $lama -Parent
        if ($lama -and ($dirLama -ne $akar) -and (Test-Path $lama)) { $hasil += "lewat:$lnk"; continue }
    }
    $s = $sh.CreateShortcut($lnk)
    $s.TargetPath = Join-Path $akar 'aplikasi.bat'
    $s.WorkingDirectory = $akar
    $s.IconLocation = (Join-Path $akar 'inti\ikon.ico') + ',0'
    $s.WindowStyle = 1
    $s.Description = 'CKG Robot - input otomatis Cek Kesehatan Gratis'
    $s.Save()
    $hasil += "dibuat:$lnk"
}
$hasil -join "`n"
"""


def buat(paksa: bool = True) -> list[str]:
    """Buat shortcut Desktop + Start Menu. Kembalikan baris 'dibuat:<jalur>' / 'lewat:<jalur>'."""
    if os.name != "nt":
        return []
    keluaran = _ps(_BUAT, akar=str(AKAR), nama=NAMA, paksa="1" if paksa else "0")
    try:
        PENANDA.write_text("shortcut sudah dibuat\n", encoding="utf-8")
    except OSError:
        pass
    return [b for b in keluaran.splitlines() if b]


def pastikan_sekali() -> None:
    """Dipanggil server saat dibuka. Diam bila gagal - shortcut bukan hal penting."""
    if os.name != "nt" or PENANDA.exists() or (AKAR / ".git").exists() or (AKAR / "unins000.exe").exists():
        return
    try:
        buat(paksa=False)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        for baris in buat(paksa="--jangan-timpa" not in sys.argv):
            jenis, jalur = baris.split(":", 1)
            print(("  Shortcut dibuat: " if jenis == "dibuat" else "  Dilewati (milik salinan lain): ") + jalur)
    except Exception as e:
        print(f"  [PERINGATAN] Shortcut tidak bisa dibuat: {e}")
        sys.exit(1)
