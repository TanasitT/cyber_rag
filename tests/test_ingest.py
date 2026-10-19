from scripts.index import VectorIndex
from scripts.ingest import main


def test_ingest_end_to_end(tmp_path, capsys):
    ds = tmp_path / "dataset"
    ds.mkdir()
    (ds / "en.txt").write_text("Phishing emails trick users into revealing passwords.", encoding="utf-8")
    (ds / "th.txt").write_text(
        "--- Page 1 ---\nมาตรฐานการรักษาความมั่นคงปลอดภัยสำหรับเว็บไซต์\n"
        "--- Page 2 ---\nให้เลขาธิการมีอํานาจออกประกาศ คําสั่ง หลักเกณฑ์",  # split sara am, as OCR writes it
        encoding="utf-8",
    )
    (ds / "bad.pdf").write_bytes(b"this is not a pdf")
    index_dir = tmp_path / "index"

    main(["--dataset_dir", str(ds), "--index_dir", str(index_dir), "--cache_dir", str(tmp_path / "cache")])

    out, err = capsys.readouterr()
    assert "dataset/bad.pdf: skipped" in err
    assert (index_dir / "manifest.json").exists()

    index = VectorIndex.load(index_dir)
    assert index.search("ใครมีอำนาจออกคำสั่ง", top_k=1)[0][0].chunk_id == "dataset/th.txt::page_2"
    assert index.search("phishing", top_k=1)[0][0].chunk_id == "dataset/en.txt::page_1"
