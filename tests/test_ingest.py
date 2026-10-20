from scripts.index import VectorIndex
from scripts.ingest import main


def test_ingest_end_to_end(tmp_path, capsys):
    ds = tmp_path / "dataset"
    ds.mkdir()
    (ds / "en.txt").write_text("The library opens at nine and lends up to five books.", encoding="utf-8")
    (ds / "th.txt").write_text(
        "--- Page 1 ---\nนักเรียนสามารถดาวน์โหลดเอกสารจากเว็บไซต์ของมหาวิทยาลัย\n"
        "--- Page 2 ---\nให้ผู้อํานวยการมีอํานาจอนุมัติงบประมาณประจําปี",  # split sara am, as OCR writes it
        encoding="utf-8",
    )
    (ds / "bad.pdf").write_bytes(b"this is not a pdf")
    index_dir = tmp_path / "index"

    main(["--dataset_dir", str(ds), "--index_dir", str(index_dir), "--cache_dir", str(tmp_path / "cache")])

    out, err = capsys.readouterr()
    assert "dataset/bad.pdf: skipped" in err
    assert (index_dir / "manifest.json").exists()

    index = VectorIndex.load(index_dir)
    assert index.search("ใครมีอำนาจอนุมัติงบประมาณ", top_k=1)[0][0].chunk_id == "dataset/th.txt::page_2"
    assert index.search("library books", top_k=1)[0][0].chunk_id == "dataset/en.txt::page_1"
