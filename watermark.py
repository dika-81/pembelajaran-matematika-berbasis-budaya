"""
Menambahkan watermark diagonal "Property of Andika Arisetyawan" pada setiap
halaman isi buku, lalu meratakan (flatten) halaman menjadi citra sehingga
watermark menyatu dengan teks artikel: watermark tidak bisa dihapus/diedit
tanpa ikut menghapus tulisan di halaman tersebut.

Watermark: huruf putih dengan bayangan abu-abu tipis (efek emboss) yang
membentang dari sudut kiri bawah menuju sudut kanan atas kertas.
"""

import io
import math
import sys

import fitz  # PyMuPDF
from PIL import Image, ImageOps

SRC = "Pembelajaran Matematika Berbasis Budaya.pdf"
DST = "Pembelajaran Matematika Berbasis Budaya - Watermark.pdf"

TEKS = "Property of Andika Arisetyawan"
DPI = 150                 # resolusi rasterisasi halaman
KUALITAS_JPEG = 78        # kualitas halaman berwarna
FONT = "hebo"             # Helvetica-Bold
LEBAR_RELATIF = 0.86      # panjang teks terhadap diagonal kertas
WARNA_BAYANGAN = (0.55, 0.55, 0.55)
WARNA_GARIS = (0.45, 0.45, 0.45)
OPASITAS_BAYANGAN = 0.32  # bayangan abu-abu di belakang huruf
OPASITAS_ISI = 0.48       # isi huruf putih (transparan agar teks tetap terbaca)
OPASITAS_GARIS = 0.60     # garis tepi huruf
TEBAL_GARIS = 0.014       # tebal garis tepi, relatif terhadap ukuran huruf
GESER_BAYANGAN = 2.5      # jarak bayangan (pt)


HAL_PENERBIT = 1          # halaman romawi ii (indeks 0-based)


def hapus_penerbit(page):
    """Menghapus tulisan "Gong Publishing" pada halaman romawi ii: baris
    penerbit di atas Website/Email/Fb, dan penyebutan di dalam kotak katalog
    (baris ditulis ulang menjadi "Cetakan 1, Serang, 2020")."""
    baris_katalog = fitz.Rect(94.6, 377.7, 302.6, 391.0)
    page.add_redact_annot(fitz.Rect(85.1, 531.4, 169.1, 544.7), fill=(1, 1, 1))
    page.add_redact_annot(baris_katalog, fill=(1, 1, 1))
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)  # kotak tetap utuh
    page.insert_text(fitz.Point(94.6, 388.4), "Cetakan 1, Serang, 2020",
                     fontname="tiro", fontsize=12, color=(0, 0, 0))


def gambar_watermark(page):
    r = page.rect
    font = fitz.Font(FONT)

    # sudut diagonal kiri-bawah -> kanan-atas
    sudut = math.degrees(math.atan2(r.height, r.width))
    diagonal = math.hypot(r.width, r.height)

    ukuran = 100.0
    panjang = font.text_length(TEKS, fontsize=ukuran)
    ukuran = ukuran * (diagonal * LEBAR_RELATIF) / panjang
    panjang = font.text_length(TEKS, fontsize=ukuran)

    pivot = fitz.Point(r.width / 2, r.height / 2)
    mtx = fitz.Matrix(1, 1).prerotate(-sudut)  # rotasi berlawanan arah jarum jam

    # titik awal baseline agar teks terpusat di tengah halaman
    awal = fitz.Point(pivot.x - panjang / 2, pivot.y + ukuran * 0.35)

    # 1) bayangan abu-abu di belakang huruf -> tercetak samar di kertas
    page.insert_text(awal + fitz.Point(GESER_BAYANGAN, GESER_BAYANGAN), TEKS,
                     fontname=FONT, fontsize=ukuran, color=WARNA_BAYANGAN,
                     render_mode=1, stroke_opacity=OPASITAS_BAYANGAN,
                     border_width=TEBAL_GARIS, morph=(pivot, mtx))

    # 2) huruf putih transparan + garis tepi -> tulisan artikel tetap terbaca
    page.insert_text(awal, TEKS, fontname=FONT, fontsize=ukuran,
                     color=WARNA_GARIS, fill=(1, 1, 1), render_mode=2,
                     fill_opacity=OPASITAS_ISI, stroke_opacity=OPASITAS_GARIS,
                     border_width=TEBAL_GARIS, morph=(pivot, mtx))


def proses(src=SRC, dst=DST, halaman=None):
    doc = fitz.open(src)
    out = fitz.open()
    nomor = range(doc.page_count) if halaman is None else halaman

    for i in nomor:
        page = doc[i]
        if i == HAL_PENERBIT:
            hapus_penerbit(page)
        gambar_watermark(page)

        pix = page.get_pixmap(dpi=DPI)
        rect = page.rect
        hal = out.new_page(width=rect.width, height=rect.height)
        hal.insert_image(hal.rect, stream=_kompres(pix))
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{doc.page_count} halaman", flush=True)

    out.set_metadata({
        "title": doc.metadata.get("title") or "Pembelajaran Matematika Berbasis Budaya",
        "author": "Andika Arisetyawan",
        "creator": "Property of Andika Arisetyawan",
        "producer": "Property of Andika Arisetyawan",
    })
    out.save(dst, garbage=4, deflate=True, deflate_images=True, clean=True)
    out.close()
    doc.close()
    print("selesai ->", dst)


def _kompres(pix):
    """Halaman teks -> PNG grayscale terkuantisasi (tajam, kecil);
    halaman berwarna -> JPEG kualitas tinggi."""
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    buf = io.BytesIO()
    if _abu_abu(pix):
        abu = ImageOps.posterize(im.convert("L"), 4)  # 16 tingkat abu, hemat ruang
        abu.save(buf, "PNG", optimize=True, compress_level=9)
    else:
        im.save(buf, "JPEG", quality=KUALITAS_JPEG, optimize=True, subsampling=1)
    return buf.getvalue()


def _abu_abu(pix, ambang=8):
    """Deteksi kasar apakah halaman praktis hitam-putih (untuk hemat ukuran)."""
    if pix.n < 3:
        return True
    s, n = pix.samples, pix.n
    for j in range(0, len(s) - n, n * 37):
        r, g, b = s[j], s[j + 1], s[j + 2]
        if abs(r - g) > ambang or abs(g - b) > ambang or abs(r - b) > ambang:
            return False
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--contoh":
        proses(dst="contoh-watermark.pdf", halaman=[0, 2, 5, 10, 100])
    else:
        proses()
