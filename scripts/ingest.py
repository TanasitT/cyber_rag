from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .chunking import chunks_from_pages, read_txt_pages
from .extract import DEFAULT_VISION_MODEL, configure_ocr, load_pdf_pages
from .index import VectorIndex
from .sources import collect_source_files, doc_id_for, ocr_txt_for, write_manifest


def main(argv: list[str] | None = None):
    p = argparse.ArgumentParser(description="Build a dataset-only RAG index.")
    p.add_argument("--dataset_dir", type=str, default="dataset", help="Folder with PDF / TXT files (subfolders included).")
    p.add_argument("--index_dir", type=str, default="outputs/index", help="Where to store the built index.")
    p.add_argument("--cache_dir", type=str, default="outputs/cache", help="Cache for extracted / OCR'd page text.")
    p.add_argument("--ocr_engine", choices=["tesseract", "openai"], default="tesseract",
                   help="Used for pages without a usable text layer (scans, broken Thai fonts).")
    p.add_argument("--ocr_lang", type=str, default="tha+eng", help="Tesseract languages.")
    p.add_argument("--ocr_dpi", type=int, default=400)
    p.add_argument("--tesseract_cmd", type=str, default=None, help="Path to tesseract.exe if not auto-detected.")
    p.add_argument("--vision_model", type=str, default=DEFAULT_VISION_MODEL, help="Model for --ocr_engine openai.")
    args = p.parse_args(argv)

    dataset_dir = Path(args.dataset_dir)
    if not dataset_dir.is_dir():
        raise SystemExit(f"Dataset folder not found: {dataset_dir}")

    files, replaced = collect_source_files(dataset_dir)
    for pdf in replaced:
        print(f"{doc_id_for(pdf, dataset_dir)}: skipped, using {ocr_txt_for(pdf).name} instead")

    ocr, no_ocr_reason = None, None
    if any(f.suffix.lower() == ".pdf" for f in files):
        ocr, no_ocr_reason = configure_ocr(
            engine=args.ocr_engine,
            lang=args.ocr_lang,
            dpi=args.ocr_dpi,
            tesseract_cmd=args.tesseract_cmd,
            vision_model=args.vision_model,
        )

    chunks = []
    indexed_files = 0
    pages_without_ocr = 0
    for path in files:
        doc_id = doc_id_for(path, dataset_dir)
        try:
            if path.suffix.lower() == ".pdf":
                result = load_pdf_pages(path, args.cache_dir, ocr)
                pages, skipped, cached = result.pages, result.skipped, result.from_cache
            else:
                pages, skipped, cached = read_txt_pages(path), [], False
        except Exception as e:
            print(f"WARNING: {doc_id}: skipped ({type(e).__name__}: {e})", file=sys.stderr)
            continue

        chunks.extend(chunks_from_pages(doc_id, pages))
        indexed_files += bool(pages)
        pages_without_ocr += len(skipped)

        n_ocr = sum(pg.method == "ocr" for pg in pages)
        line = f"{doc_id}: {len(pages)} pages"
        if n_ocr:
            line += f" ({len(pages) - n_ocr} text, {n_ocr} OCR)"
        if skipped:
            line += f", skipped {len(skipped)} page(s) that need OCR"
        if cached:
            line += " [cached]"
        print(line)

    if pages_without_ocr:
        print(
            f"NOTE: {pages_without_ocr} page(s) skipped because OCR is unavailable: {no_ocr_reason}. "
            "See README 'Thai and scanned PDFs', then re-run ingest.",
            file=sys.stderr,
        )
    if not chunks:
        raise SystemExit(f"No text could be extracted from {dataset_dir}; nothing to index.")

    index = VectorIndex.build(chunks)
    index.save(args.index_dir)
    write_manifest(args.index_dir, dataset_dir, files)

    print(f"Indexed {len(chunks)} pages from {indexed_files} files into: {Path(args.index_dir).resolve()}")


if __name__ == "__main__":
    main()
