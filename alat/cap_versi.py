r"""
Cap nomor versi aplikasi (inti\config.py: VERSI) dengan waktu sekarang.

    python alat\cap_versi.py          -> VERSI = "2026.10.08.0930"

Dipanggil buat_paket.bat sebelum menyalin berkas, supaya setiap paket punya
versi yang lebih baru dari paket sebelumnya - dasar tombol "Perbarui
sekarang" di aplikasi petugas. Formatnya tahun.bulan.tanggal.jammenit:
urutan teksnya sama dengan urutan waktu.
"""
import re
import sys
from datetime import datetime
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "inti" / "config.py"

versi = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y.%m.%d.%H%M")
teks = CONFIG.read_text(encoding="utf-8")
baru, n = re.subn(r'(?m)^VERSI = "[^"]*"', f'VERSI = "{versi}"', teks, count=1)
if n != 1:
    sys.exit("[GAGAL] baris VERSI tidak ditemukan di inti\\config.py")
CONFIG.write_text(baru, encoding="utf-8")
print(versi)
