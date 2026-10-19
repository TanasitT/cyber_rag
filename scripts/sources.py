"""Which files in the dataset folder get indexed, and whether a built index is out of date."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SOURCE_SUFFIXES = {".pdf", ".txt"}
OCR_TXT_SUFFIX = "_ocr.txt"  # written by create_txt_from_pdf.py; replaces the PDF it came from
MANIFEST_NAME = "manifest.json"


def ocr_txt_for(pdf: Path) -> Path:
    return pdf.with_name(pdf.stem + OCR_TXT_SUFFIX)


def collect_source_files(dataset_dir: str | Path) -> Tuple[List[Path], List[Path]]:
    """
    Returns (files to index, PDFs skipped because an X_ocr.txt next to them replaces them).
    Searches subfolders; ignores hidden files and Office lock files (~$...).
    """
    dataset_dir = Path(dataset_dir)
    files, replaced = [], []
    for path in sorted(dataset_dir.rglob("*")):
        rel = path.relative_to(dataset_dir)
        if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        if any(part.startswith(".") for part in rel.parts) or path.name.startswith("~$"):
            continue
        if path.suffix.lower() == ".pdf" and ocr_txt_for(path).exists():
            replaced.append(path)
            continue
        files.append(path)
    return files, replaced


def doc_id_for(path: Path, dataset_dir: str | Path) -> str:
    """'dataset/<relative path>', regardless of how dataset_dir was spelled."""
    dataset_dir = Path(dataset_dir)
    return (Path(dataset_dir.resolve().name) / path.relative_to(dataset_dir)).as_posix()


def _fingerprint(files: List[Path], dataset_dir: Path) -> Dict[str, List[int]]:
    result = {}
    for f in files:
        st = f.stat()
        result[doc_id_for(f, dataset_dir)] = [st.st_size, st.st_mtime_ns]
    return result


def write_manifest(index_dir: str | Path, dataset_dir: str | Path, files: List[Path]) -> None:
    dataset_dir = Path(dataset_dir)
    manifest = {
        "dataset_dir": str(dataset_dir.resolve()),
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "files": _fingerprint(files, dataset_dir),
    }
    path = Path(index_dir) / MANIFEST_NAME
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def check_stale(index_dir: str | Path) -> Optional[Dict[str, List[str]]]:
    """
    Compares the dataset folder with the manifest saved at build time.
    Returns {"added": [...], "changed": [...], "removed": [...]}, or None if the index
    has no manifest (built by an older version) or its dataset folder no longer exists.
    """
    path = Path(index_dir) / MANIFEST_NAME
    if not path.exists():
        return None
    manifest = json.loads(path.read_text(encoding="utf-8"))
    dataset_dir = Path(manifest["dataset_dir"])
    if not dataset_dir.is_dir():
        return None

    files, _ = collect_source_files(dataset_dir)
    now = _fingerprint(files, dataset_dir)
    before = manifest["files"]
    return {
        "added": sorted(set(now) - set(before)),
        "changed": sorted(k for k in set(now) & set(before) if now[k] != before[k]),
        "removed": sorted(set(before) - set(now)),
    }


def stale_message(index_dir: str | Path) -> Optional[str]:
    diff = check_stale(index_dir)
    if not diff or not any(diff.values()):
        return None
    parts = [f"{len(v)} {k}" for k, v in diff.items() if v]
    files = ", ".join(diff["added"] + diff["changed"] + diff["removed"])
    return (
        f"The index is out of date ({', '.join(parts)} since it was built: {files}). "
        "Run: python -m scripts.ingest"
    )
