"""
Cetak "Panduan CKG Robot.pdf" dari kepala.html + isi.html (gambar di gambar/).

    python panduan/cetak.py                 -> ../Panduan CKG Robot.pdf (akar repo)
    python panduan/cetak.py <tujuan.pdf>

Dicetak dua kali: cetakan pertama untuk mencari halaman tiap bab, lalu nomor
halaman daftar isi ({{A}} ... {{J}}) diisi dan dicetak ulang.
Butuh playwright dan pymupdf (requirements-dev.txt); Google Chrome bila ada, selain itu Chromium Playwright.
Gambar harus berisi DATA REKAAN saja - diambil dari demo / server uji.
"""
import re
import sys
from pathlib import Path

import fitz
from playwright.sync_api import sync_playwright

DIR = Path(__file__).resolve().parent
HTML = DIR / "_cetak.html"
PDF = Path(sys.argv[1]) if len(sys.argv) > 1 else DIR.parent / "Panduan CKG Robot.pdf"
JUDUL = {"A": "A. Yang perlu disiapkan", "B": "B. Membuat akun CKG Robot", "C": "C. Pemasangan (sekali saja)",
         "D": "D. Menyiapkan data peserta", "E": "E. Menjalankan CKG Robot", "F": "F. Membaca hasil",
         "G": "G. Aturan yang menghemat waktu", "H": "H. Memperbarui aplikasi", "I": "I. Kalau ada masalah",
         "J": "J. Khusus admin: Kelola Petugas"}
KAKI = ('<div style="font-size:8px;color:#888;width:100%;text-align:center;font-family:Segoe UI">'
        'Panduan CKG Robot · halaman <span class="pageNumber"></span> / <span class="totalPages"></span></div>')


def cetak(isi_html: str, tujuan: Path) -> None:
    HTML.write_text(isi_html, encoding="utf-8")
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="chrome", headless=True)
        except Exception:
            # Chrome tidak terpasang (PC pengembang kedua) -> Chromium bawaan Playwright.
            b = p.chromium.launch(headless=True)
        h = b.new_page()
        h.goto(HTML.as_uri()); h.wait_for_load_state("networkidle")
        h.pdf(path=str(tujuan), format="A4", print_background=True, prefer_css_page_size=True,
              display_header_footer=True, header_template="<span></span>", footer_template=KAKI)
        b.close()


def main() -> None:
    dasar = (DIR / "kepala.html").read_text(encoding="utf-8") + (DIR / "isi.html").read_text(encoding="utf-8")
    sementara = DIR / "_sementara.pdf"
    cetak(dasar, sementara)
    doc = fitz.open(sementara)
    halaman = {}
    for k, judul in JUDUL.items():
        for i in range(2, doc.page_count):            # lewati sampul & daftar isi
            if judul in doc[i].get_text():
                halaman[k] = i + 1
                break
    doc.close()
    hilang = [k for k in JUDUL if k not in halaman]
    if hilang:
        sys.exit(f"judul tidak ditemukan: {hilang}")
    akhir = re.sub(r"\{\{([A-J])\}\}", lambda m: str(halaman[m.group(1)]), dasar)
    cetak(akhir, PDF)
    sementara.unlink()
    HTML.unlink()
    d = fitz.open(PDF)
    print(PDF, d.page_count, "halaman |", halaman)


if __name__ == "__main__":
    main()
