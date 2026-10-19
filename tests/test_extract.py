from pathlib import Path

import pytest

from scripts import extract
from scripts.extract import OcrConfig, PageText, PdfPages, load_pdf_pages, looks_garbled, needs_ocr

DATASET = Path(__file__).resolve().parents[1] / "dataset"
OWASP = DATASET / "owasp-top-10.pdf"
THAI_PDF = DATASET / "thailand-web-security-standard-2025.pdf"

# Real samples from the dataset
GARBLED_THAI = 'Nอ%@# ํ@N%>%@#!@!/##คห% @P  QหOห%N/"@%? #ํ@O&&อ#์!  ค`  O&&#@"@%#@"@#   #?P"?!Oอ\'#?&\'#B'
TOC = "Table of Contents\nIntroduction ...................................... 1\nBackground .................................... 3"
THAI_OCR = "ก่อนการดำเนินการตามวรรคหนึ่ง ให้หน่วยงานจัดทำแบบฟอร์ม ค๒ แบบรายงานรายการที่ยังต้องปรับปรุง"


def test_looks_garbled():
    assert looks_garbled(GARBLED_THAI)
    assert looks_garbled("")
    assert not looks_garbled(TOC)
    assert not looks_garbled(THAI_OCR)


def test_needs_ocr_for_short_pages():
    assert needs_ocr("p. 3")
    assert not needs_ocr(THAI_OCR)


@pytest.fixture
def fake_ocr(monkeypatch):
    calls = []

    def ocr_page(path, page_no, ocr):
        calls.append(page_no)
        return f"OCR text for page {page_no}"

    monkeypatch.setattr(extract, "ocr_page", ocr_page)
    return calls


@pytest.mark.skipif(not OWASP.exists(), reason="dataset PDF missing")
def test_text_pdf_only_ocrs_near_empty_pages(fake_ocr):
    result = extract.extract_pdf_pages(OWASP, OcrConfig())
    assert fake_ocr == [6, 38]  # section divider pages with < 20 characters
    assert len(result.pages) == 41 and not result.skipped


@pytest.mark.skipif(not OWASP.exists(), reason="dataset PDF missing")
def test_text_pdf_without_ocr_keeps_short_readable_pages():
    result = extract.extract_pdf_pages(OWASP, None)
    assert len(result.pages) == 41 and not result.skipped


@pytest.mark.skipif(not THAI_PDF.exists(), reason="dataset PDF missing")
def test_garbled_thai_pdf_uses_ocr(fake_ocr):
    result = extract.extract_pdf_pages(THAI_PDF, OcrConfig())
    text_pages = [p.page for p in result.pages if p.method == "text"]
    assert text_pages == [73, 74, 76, 77]  # readable English bibliography pages
    assert len(fake_ocr) == 73


@pytest.mark.skipif(not THAI_PDF.exists(), reason="dataset PDF missing")
def test_garbled_pages_skipped_without_ocr():
    result = extract.extract_pdf_pages(THAI_PDF, None)
    assert len(result.skipped) == 73
    assert [p.page for p in result.pages] == [73, 74, 76, 77]


@pytest.fixture
def counting_extractor(monkeypatch):
    """Replaces the real extractor; the next result can be set via .next."""

    class Extractor:
        calls = 0
        next = PdfPages(pages=[PageText(1, "hello", "text")])

        def __call__(self, path, ocr):
            Extractor.calls += 1
            return self.next

    ex = Extractor()
    monkeypatch.setattr(extract, "extract_pdf_pages", ex)
    return ex


def test_cache_is_reused(tmp_path, counting_extractor):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"fake")
    load_pdf_pages(pdf, tmp_path / "cache", None)
    second = load_pdf_pages(pdf, tmp_path / "cache", None)
    assert counting_extractor.calls == 1
    assert second.from_cache and second.pages[0].text == "hello"


def test_cache_redone_when_ocr_becomes_available(tmp_path, counting_extractor):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"fake")
    counting_extractor.next = PdfPages(pages=[], skipped=[1])
    load_pdf_pages(pdf, tmp_path / "cache", None)
    load_pdf_pages(pdf, tmp_path / "cache", OcrConfig())
    assert counting_extractor.calls == 2


def test_cache_keeps_ocr_results_when_ocr_unavailable(tmp_path, counting_extractor):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"fake")
    counting_extractor.next = PdfPages(pages=[PageText(1, "ocr'd", "ocr")])
    load_pdf_pages(pdf, tmp_path / "cache", OcrConfig())
    again = load_pdf_pages(pdf, tmp_path / "cache", None)
    assert counting_extractor.calls == 1 and again.pages[0].method == "ocr"


def test_cache_invalidated_when_file_changes(tmp_path, counting_extractor):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"fake")
    load_pdf_pages(pdf, tmp_path / "cache", None)
    pdf.write_bytes(b"changed")
    load_pdf_pages(pdf, tmp_path / "cache", None)
    assert counting_extractor.calls == 2
