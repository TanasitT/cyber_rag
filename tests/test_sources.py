from scripts.sources import check_stale, collect_source_files, doc_id_for, stale_message, write_manifest


def make_dataset(tmp_path):
    ds = tmp_path / "dataset"
    (ds / "sub").mkdir(parents=True)
    (ds / ".hidden").mkdir()
    for name in ["a.pdf", "a_ocr.txt", "b.PDF", "sub/c.txt", "notes.md", ".hidden/d.pdf", "~$lock.pdf"]:
        (ds / name).write_text("x", encoding="utf-8")
    return ds


def test_collect_source_files(tmp_path):
    ds = make_dataset(tmp_path)
    files, replaced = collect_source_files(ds)
    assert [f.relative_to(ds).as_posix() for f in files] == ["a_ocr.txt", "b.PDF", "sub/c.txt"]
    assert [f.name for f in replaced] == ["a.pdf"]  # its _ocr.txt is used instead


def test_doc_id(tmp_path):
    ds = make_dataset(tmp_path)
    assert doc_id_for(ds / "sub" / "c.txt", ds) == "dataset/sub/c.txt"


def test_check_stale(tmp_path):
    ds = make_dataset(tmp_path)
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    files, _ = collect_source_files(ds)
    write_manifest(index_dir, ds, files)
    assert stale_message(index_dir) is None

    (ds / "new.pdf").write_text("x", encoding="utf-8")
    (ds / "b.PDF").write_text("bigger", encoding="utf-8")
    (ds / "sub" / "c.txt").unlink()
    assert check_stale(index_dir) == {
        "added": ["dataset/new.pdf"],
        "changed": ["dataset/b.PDF"],
        "removed": ["dataset/sub/c.txt"],
    }
    assert "out of date" in stale_message(index_dir)


def test_no_manifest_means_unknown(tmp_path):
    assert check_stale(tmp_path) is None
