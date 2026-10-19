"""
Page text from PDFs. Pages whose text layer is missing (scans) or garbled (broken font
encodings, common in Thai PDFs) are read with OCR instead. Results are cached per file.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import shutil
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from PyPDF2 import PdfReader

from .thai import normalize_thai

EXTRACTOR_VERSION = 1

# Share of non-space characters that must be letters, marks or digits. Measured on the
# dataset: readable pages score >= 0.81, the garbled Thai PDF pages mostly 0.3-0.6.
GARBLED_THRESHOLD = 0.7
MIN_TEXT_CHARS = 20  # fewer non-space characters than this = probably a scanned page

TESSERACT_CONFIG = "--oem 1 --psm 6 -c preserve_interword_spaces=1"
WINDOWS_TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
DEFAULT_VISION_MODEL = "gpt-4.1"
VISION_PROMPT = (
    "Transcribe all text on this page exactly as printed. "
    "Do not translate, correct, summarize or add anything. "
    "Keep Thai numerals and punctuation as they appear. "
    "Output plain text only."
)

_DOT_LEADERS = re.compile(r"([^\w\s])\1{2,}")  # "........" in tables of contents


@dataclass(frozen=True)
class OcrConfig:
    engine: str = "tesseract"  # "tesseract" or "openai"
    lang: str = "tha+eng"  # Tesseract languages
    dpi: int = 400
    vision_model: str = DEFAULT_VISION_MODEL

    def cache_key(self) -> str:
        if self.engine == "openai":
            return f"openai:{self.vision_model}:{self.dpi}"
        return f"tesseract:{self.lang}:{self.dpi}"


@dataclass
class PageText:
    page: int
    text: str
    method: str  # "text" (PDF text layer) or "ocr"


@dataclass
class PdfPages:
    pages: List[PageText]
    skipped: List[int] = field(default_factory=list)  # pages that needed OCR but none was available
    from_cache: bool = False


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def looks_garbled(text: str) -> bool:
    chars = [c for c in _DOT_LEADERS.sub(" ", text) if not c.isspace()]
    if not chars:
        return True
    good = sum(unicodedata.category(c)[0] in "LMN" for c in chars)
    return good / len(chars) < GARBLED_THRESHOLD


def needs_ocr(text: str) -> bool:
    return sum(not c.isspace() for c in text) < MIN_TEXT_CHARS or looks_garbled(text)


def configure_ocr(
    engine: str = "tesseract",
    lang: str = "tha+eng",
    dpi: int = 400,
    tesseract_cmd: Optional[str] = None,
    vision_model: str = DEFAULT_VISION_MODEL,
) -> Tuple[Optional[OcrConfig], Optional[str]]:
    """Returns (config, None) when OCR can run, otherwise (None, reason)."""
    if engine == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            return None, "OPENAI_API_KEY is not set"
        return OcrConfig(engine="openai", dpi=dpi, vision_model=vision_model), None

    import pytesseract

    cmd = tesseract_cmd or os.getenv("TESSERACT_CMD")
    if not cmd and WINDOWS_TESSERACT.exists():
        cmd = str(WINDOWS_TESSERACT)
    if not cmd:
        cmd = shutil.which("tesseract")
    if not cmd:
        return None, "Tesseract is not installed (or set TESSERACT_CMD / --tesseract_cmd)"
    pytesseract.pytesseract.tesseract_cmd = cmd

    try:
        installed = set(pytesseract.get_languages(config=""))
    except Exception as e:  # tesseract present but not runnable
        return None, f"Tesseract could not run: {e}"
    wanted = [code for code in lang.split("+") if code]
    missing = [code for code in wanted if code not in installed]
    usable = [code for code in wanted if code in installed]
    if missing:
        print(f"WARNING: Tesseract language data not installed: {', '.join(missing)}", file=sys.stderr)
    if not usable:
        return None, f"none of the OCR languages '{lang}' are installed for Tesseract"
    return OcrConfig(engine="tesseract", lang="+".join(usable), dpi=dpi), None


def ocr_page(pdf_path: str | Path, page_no: int, ocr: OcrConfig) -> str:
    from pdf2image import convert_from_path

    image = convert_from_path(str(pdf_path), dpi=ocr.dpi, first_page=page_no, last_page=page_no)[0]
    if ocr.engine == "openai":
        text = _ocr_openai(image, ocr.vision_model)
    else:
        import pytesseract

        text = pytesseract.image_to_string(image, lang=ocr.lang, config=TESSERACT_CONFIG)
    return normalize_thai(clean_text(text))


def _ocr_openai(image, model: str) -> str:
    from .generator import get_client

    image = image.copy()
    image.thumbnail((2048, 2048))  # the API downsizes larger images anyway
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    extra = {"temperature": 0.0} if model.startswith("gpt-4") else {}  # reasoning models reject it
    response = get_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": VISION_PROMPT},
            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": data_url, "detail": "high"}}]},
        ],
        **extra,
    )
    return response.choices[0].message.content or ""


def extract_pdf_pages(path: str | Path, ocr: Optional[OcrConfig]) -> PdfPages:
    reader = PdfReader(str(path))
    if reader.is_encrypted and not reader.decrypt(""):
        raise ValueError("encrypted PDF that needs a password")

    result = PdfPages(pages=[])
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = (page.extract_text() or "").strip()
        except Exception:
            text = ""

        method = "text"
        if needs_ocr(text):
            if ocr is not None:
                text, method = ocr_page(path, i, ocr), "ocr"
            elif not text or looks_garbled(text):
                result.skipped.append(i)
                continue
            # else: short but readable text, keep it

        text = normalize_thai(text)
        if text:
            result.pages.append(PageText(page=i, text=text, method=method))
    return result


def file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _cache_usable(entry: dict, digest: str, ocr: Optional[OcrConfig]) -> bool:
    if entry.get("version") != EXTRACTOR_VERSION or entry.get("sha256") != digest:
        return False
    if ocr is None or entry.get("ocr") == ocr.cache_key():
        return True  # never throw away earlier OCR results just because OCR is unavailable now
    # different OCR settings: only reusable if no page needed OCR in the first place
    return not entry["skipped"] and all(p["method"] == "text" for p in entry["pages"])


def load_pdf_pages(path: str | Path, cache_dir: str | Path | None, ocr: Optional[OcrConfig]) -> PdfPages:
    """extract_pdf_pages with a JSON cache keyed by file content and OCR settings."""
    if cache_dir is None:
        return extract_pdf_pages(path, ocr)

    digest = file_sha256(path)
    cache_file = Path(cache_dir) / "pages" / f"{digest}.json"
    if cache_file.exists():
        entry = json.loads(cache_file.read_text(encoding="utf-8"))
        if _cache_usable(entry, digest, ocr):
            return PdfPages(
                pages=[PageText(**p) for p in entry["pages"]],
                skipped=entry["skipped"],
                from_cache=True,
            )

    result = extract_pdf_pages(path, ocr)
    entry = {
        "version": EXTRACTOR_VERSION,
        "sha256": digest,
        "source": Path(path).name,
        "ocr": ocr.cache_key() if ocr else "none",
        "pages": [asdict(p) for p in result.pages],
        "skipped": result.skipped,
    }
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
    return result
