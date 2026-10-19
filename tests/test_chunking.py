from scripts.chunking import chunks_from_pages, read_txt_pages


def test_page_markers(tmp_path):
    f = tmp_path / "doc_ocr.txt"
    f.write_text("\n--- Page 1 ---\nhello\n--- Page 3 ---\nworld\n--- Page 4 ---\n   ", encoding="utf-8")
    pages = read_txt_pages(f)
    assert [(p.page, p.text) for p in pages] == [(1, "hello"), (3, "world")]

    chunks = chunks_from_pages("dataset/doc_ocr.txt", pages)
    assert [c.chunk_id for c in chunks] == ["dataset/doc_ocr.txt::page_1", "dataset/doc_ocr.txt::page_3"]


def test_txt_without_markers_is_one_page(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("plain text file", encoding="utf-8")
    assert [(p.page, p.text) for p in read_txt_pages(f)] == [(1, "plain text file")]


def test_txt_is_normalized(tmp_path):
    f = tmp_path / "th.txt"
    f.write_text("--- Page 1 ---\nดําเนินการ", encoding="utf-8")
    assert read_txt_pages(f)[0].text == "ดำเนินการ"
