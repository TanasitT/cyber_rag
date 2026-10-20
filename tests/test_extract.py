import pytest

from scripts import extract
from scripts.extract import OcrConfig, PageText, PdfPages, load_pdf_pages, looks_garbled, needs_ocr

# What a PDF with a broken font encoding yields as "text"
GARBLED = 'Nอ%@# ํ@N%>%@#!@!/##คห% @P  QหOห%N/"@%? #ํ@O&&อ#์!  ค`  O&&#@"@%#@"@#   #?P"?!Oอ\'#?&\'#B'
TOC = "Table of Contents\nIntroduction ...................................... 1\nBackground .................................... 3"
THAI_TEXT = "ก่อนเริ่มดำเนินการ ให้หน่วยงานจัดทำแบบฟอร์มรายงานผลการดำเนินงานประจำปี"
READABLE = "The committee met on Monday and approved the annual budget for the next financial year."


def test_looks_garbled():
    assert looks_garbled(GARBLED)
    assert looks_garbled("")
    assert not looks_garbled(TOC)
    assert not looks_garbled(THAI_TEXT)


def test_needs_ocr_for_short_pages():
    assert needs_ocr("p. 3")
    assert not needs_ocr(THAI_TEXT)


def fake_reader(monkeypatch, texts, encrypted=False, decrypts=True):
    """Replaces PdfReader with one whose pages return the given texts (or raise, for exceptions)."""

    class Page:
        def __init__(self, text):
            self.text = text

        def extract_text(self):
            if isinstance(self.text, Exception):
                raise self.text
            return self.text

    class Reader:
        def __init__(self, path):
            self.pages = [Page(t) for t in texts]
            self.is_encrypted = encrypted

        def decrypt(self, password):
            return 1 if decrypts else 0

    monkeypatch.setattr(extract, "PdfReader", Reader)


@pytest.fixture
def fake_ocr(monkeypatch):
    calls = []

    def ocr_page(path, page_no, ocr):
        calls.append(page_no)
        return f"OCR text for page {page_no}"

    monkeypatch.setattr(extract, "ocr_page", ocr_page)
    return calls


PAGES = [READABLE, "", GARBLED, "Chapter 2"]  # readable, scanned, broken font, short heading


def test_ocr_only_for_pages_without_usable_text(monkeypatch, fake_ocr):
    fake_reader(monkeypatch, PAGES)
    result = extract.extract_pdf_pages("doc.pdf", OcrConfig())
    assert fake_ocr == [2, 3, 4]
    assert [(p.page, p.method) for p in result.pages] == [(1, "text"), (2, "ocr"), (3, "ocr"), (4, "ocr")]


def test_without_ocr_unusable_pages_are_skipped(monkeypatch):
    fake_reader(monkeypatch, PAGES)
    result = extract.extract_pdf_pages("doc.pdf", None)
    assert [p.page for p in result.pages] == [1, 4]  # short but readable heading is kept
    assert result.skipped == [2, 3]


def test_page_that_fails_to_extract_needs_ocr(monkeypatch, fake_ocr):
    fake_reader(monkeypatch, [RuntimeError("bad page")])
    result = extract.extract_pdf_pages("doc.pdf", OcrConfig())
    assert fake_ocr == [1] and result.pages[0].method == "ocr"


def test_encrypted_pdf_needs_password(monkeypatch):
    fake_reader(monkeypatch, [READABLE], encrypted=True, decrypts=False)
    with pytest.raises(ValueError):
        extract.extract_pdf_pages("doc.pdf", None)


def test_text_layer_is_normalized(monkeypatch):
    fake_reader(monkeypatch, ["รายงานผลการดําเนินงานประจําปีของหน่วยงาน"])  # split sara am
    assert extract.extract_pdf_pages("doc.pdf", None).pages[0].text == "รายงานผลการดำเนินงานประจำปีของหน่วยงาน"


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
