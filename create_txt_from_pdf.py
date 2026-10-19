"""
OCR every page of a PDF into an editable <name>_ocr.txt next to it.

Ingest OCRs unreadable pages automatically; use this script when you want a text file
you can review and hand-correct. While <name>_ocr.txt exists, ingest uses it instead of
the PDF. An existing output file is kept as <name>_ocr.txt.<timestamp>.bak.

Example:
    python create_txt_from_pdf.py dataset/thailand-web-security-standard-2025.pdf
"""
import argparse
from datetime import datetime
from pathlib import Path

from PyPDF2 import PdfReader

from scripts.extract import DEFAULT_VISION_MODEL, configure_ocr, ocr_page
from scripts.sources import ocr_txt_for


def main(argv: list[str] | None = None):
    p = argparse.ArgumentParser(description="OCR a PDF into a page-marked .txt file.")
    p.add_argument("pdf", type=Path)
    p.add_argument("--out", type=Path, default=None, help="Default: <pdf name>_ocr.txt next to the PDF.")
    p.add_argument("--engine", choices=["tesseract", "openai"], default="tesseract")
    p.add_argument("--lang", type=str, default="tha+eng", help="Tesseract languages.")
    p.add_argument("--dpi", type=int, default=400)
    p.add_argument("--tesseract_cmd", type=str, default=None)
    p.add_argument("--vision_model", type=str, default=DEFAULT_VISION_MODEL)
    args = p.parse_args(argv)

    out = args.out or ocr_txt_for(args.pdf)
    ocr, reason = configure_ocr(args.engine, args.lang, args.dpi, args.tesseract_cmd, args.vision_model)
    if ocr is None:
        raise SystemExit(f"OCR unavailable: {reason}")

    n_pages = len(PdfReader(str(args.pdf)).pages)
    print(f"OCR {args.pdf.name} ({n_pages} pages) with {ocr.cache_key()}")

    all_text = []
    for i in range(1, n_pages + 1):
        print(f"OCR page {i}/{n_pages}")
        text = ocr_page(args.pdf, i, ocr)
        if not text:
            continue
        all_text.append(f"\n--- Page {i} ---\n")
        all_text.append(text)

    if out.exists():
        backup = out.with_name(f"{out.name}.{datetime.now():%Y%m%d-%H%M%S}.bak")
        out.replace(backup)
        print(f"Previous file kept as: {backup}")
    out.write_text("\n".join(all_text), encoding="utf-8")
    print(f"\nOCR text saved to: {out}")


if __name__ == "__main__":
    main()
