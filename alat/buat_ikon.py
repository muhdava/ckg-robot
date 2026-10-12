"""
Membuat inti/ikon.ico - ikon CKG Robot untuk shortcut Desktop/Start Menu dan
Setup.exe. Bentuknya sama dengan favicon website: kotak sudut bulat hijau
toska (#0f766e) dengan palang putih.

Digambar 8x lebih besar lalu diperkecil supaya tepinya halus di semua ukuran.
Jalankan ulang hanya bila desainnya diubah:  python alat/buat_ikon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

AKAR = Path(__file__).resolve().parent.parent
TUJUAN = AKAR / "inti" / "ikon.ico"
UKURAN = [16, 20, 24, 32, 40, 48, 64, 128, 256]
ATAS, BAWAH = (20, 160, 145), (15, 118, 110)       # gradasi #14a091 -> #0f766e


def gambar(n: int) -> Image.Image:
    s = 8
    b = n * s
    # Ikon kecil dibuat lebih penuh supaya tidak tampak mengecil di taskbar.
    tepi = 0 if n <= 24 else round(b * 0.04)
    gradasi = Image.new("RGBA", (b, b))
    g = ImageDraw.Draw(gradasi)
    for y in range(b):
        t = y / max(1, b - 1)
        g.line([(0, y), (b, y)], fill=tuple(round(a + (c - a) * t) for a, c in zip(ATAS, BAWAH)) + (255,))
    topeng = Image.new("L", (b, b), 0)
    ImageDraw.Draw(topeng).rounded_rectangle([tepi, tepi, b - 1 - tepi, b - 1 - tepi],
                                             radius=round((b - 2 * tepi) * 0.22), fill=255)
    img = Image.new("RGBA", (b, b), (0, 0, 0, 0))
    img.paste(gradasi, (0, 0), topeng)
    d = ImageDraw.Draw(img)
    # Palang: lengan 3/16 sisi, panjang 9/16 sisi (seperti favicon 32px: 6 dan 18).
    pusat = b / 2
    lengan = (b - 2 * tepi) * 6 / 32 / 2
    panjang = (b - 2 * tepi) * 18 / 32 / 2
    sudut = lengan * 0.35
    d.rounded_rectangle([pusat - lengan, pusat - panjang, pusat + lengan, pusat + panjang], radius=sudut, fill="white")
    d.rounded_rectangle([pusat - panjang, pusat - lengan, pusat + panjang, pusat + lengan], radius=sudut, fill="white")
    return img.resize((n, n), Image.LANCZOS)


def main() -> None:
    gambar_gambar = [gambar(n) for n in UKURAN]
    besar = gambar_gambar[-1]
    besar.save(TUJUAN, format="ICO", sizes=[(n, n) for n in UKURAN], append_images=gambar_gambar[:-1])
    print(f"Ikon dibuat: {TUJUAN} ({TUJUAN.stat().st_size} bita)")


if __name__ == "__main__":
    main()
