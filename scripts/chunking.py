from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List
import re

from .extract import PageText
from .thai import normalize_thai


@dataclass(frozen=True)
class Chunk:
    doc_id: str
    chunk_id: str
    text: str
    page: int


def read_txt_pages(file_path: str | Path) -> List[PageText]:
    """
    Split a .txt file by '--- Page X ---' markers (the format written by
    create_txt_from_pdf.py). A file without markers is a single page 1.
    """
    raw_text = Path(file_path).read_text(encoding="utf-8", errors="replace")

    parts = re.split(r"--- Page (\d+) ---", raw_text)
    if len(parts) == 1:
        sections = [(1, parts[0])]
    else:
        sections = [(int(parts[i]), parts[i + 1]) for i in range(1, len(parts), 2)]

    pages = []
    for page_num, page_text in sections:
        page_text = normalize_thai(page_text.strip())
        if page_text:
            pages.append(PageText(page=page_num, text=page_text, method="text"))
    return pages


def chunks_from_pages(doc_id: str, pages: Iterable[PageText]) -> List[Chunk]:
    """One chunk per page, so every chunk maps to a citable page."""
    return [
        Chunk(doc_id=doc_id, chunk_id=f"{doc_id}::page_{p.page}", text=p.text, page=p.page)
        for p in pages
    ]
