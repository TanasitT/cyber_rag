# Cybersecurity Dataset-Only RAG

A retrieval-augmented generation (RAG) system that answers cybersecurity questions **using only the documents you put in `dataset/`**, and cites the pages each answer came from.

- **No outside knowledge:** the language model may only use the retrieved pages.
- **Page-level citations:** every answer lists the pages it is based on.
- **Refuses when unsure:** answers `Insufficient information in dataset.` when the documents don't contain the answer.
- **Any PDF:** text PDFs, scanned PDFs and Thai PDFs with broken fonts (via OCR).
- **Thai support:** Thai text normalization and word segmentation for search.

> [!NOTE]
> This repository contains **no documents and no built index**. After cloning, add your PDFs to `dataset/` and run ingest before asking questions (see [Quick start](#quick-start)).
>
> The project was developed with *OWASP Top 10 (2021)*, *MITRE ATT&CK: Design and Philosophy (2020)* and Thailand's website security standard (*Royal Gazette, 2025*).

## Requirements

- Python 3.10 or newer (developed on 3.13)
- An OpenAI API key (answers are generated with `gpt-4o-mini`)
- *Optional, for OCR only:* [Tesseract](https://github.com/tesseract-ocr/tesseract) with Thai language data, and [Poppler](https://poppler.freedesktop.org/). See [Thai and scanned PDFs](#thai-and-scanned-pdfs).

## Setup

```bash
git clone https://github.com/TanasitT/cyber_rag.git
cd cyber_rag
python -m venv .venv
```

Activate the virtual environment and install the packages:

```powershell
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:OPENAI_API_KEY = "sk-..."
```

```bash
# macOS / Linux
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."
```

## Quick start

### 1. Add documents

Copy your PDFs (or `.txt` files) into `dataset/`. Subfolders are fine.

### 2. Build the index

```bash
python -m scripts.ingest
```

Ingest reads every page, OCRs pages that have no usable text, and saves the index to `outputs/index/`. It prints one line per file:

```text
dataset/thailand-web-security-standard-2025.pdf: skipped, using thailand-web-security-standard-2025_ocr.txt instead
dataset/mitre-attack-philosophy-2020.pdf: 46 pages
dataset/owasp-top-10.pdf: 41 pages
dataset/thailand-web-security-standard-2025_ocr.txt: 77 pages
Indexed 164 pages from 3 files into: ...\outputs\index
```

Files that can't be read (corrupt or password-protected) are skipped with a warning; everything else is still indexed.

### 3. Ask a question

```bash
python -m scripts.ask --question "What is MITRE ATT&CK, and what is its primary purpose?"
```

```text
QUESTION:
What is MITRE ATT&CK, and what is its primary purpose?

ANSWER:
MITRE ATT&CK is a knowledge base that documents adversary tactics and techniques based on
real-world observations. Its primary purpose is to serve as an authoritative source of
information about adversarial behavior, ...

CITATIONS:
- dataset/mitre-attack-philosophy-2020.pdf#page_44
- dataset/mitre-attack-philosophy-2020.pdf#page_4
```

If the documents don't contain the answer:

```text
ANSWER:
Insufficient information in dataset.
```

> [!IMPORTANT]
> Ask in the language of the document: English for English documents, Thai for Thai documents. Search matches words; it does not translate.

### 4. Run the API (optional)

```bash
uvicorn scripts.api:app --reload
```

Interactive docs: <http://127.0.0.1:8000/docs>

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the OWASP Top 10?", "top_k": 8}'
```

```json
{
  "answer": "The OWASP Top 10 is a standard awareness document for developers and web application security that represents a broad consensus about the most critical security risks to web applications.",
  "citations": ["dataset/owasp-top-10.pdf#page_3"],
  "used_chunks": ["dataset/owasp-top-10.pdf::page_3"]
}
```

`top_k` must be between 1 and 20. The server loads the index once at startup, so restart it after re-running ingest.

## Options

**`python -m scripts.ingest`**

| Option | Default | Description |
|---|---|---|
| `--dataset_dir` | `dataset` | Folder with PDF / TXT files (subfolders included) |
| `--index_dir` | `outputs/index` | Where the index is saved |
| `--cache_dir` | `outputs/cache` | Cache of extracted and OCR'd page text |
| `--ocr_engine` | `tesseract` | `tesseract`, or `openai` to use an OpenAI vision model (sends page images to OpenAI) |
| `--ocr_lang` | `tha+eng` | Tesseract languages |
| `--ocr_dpi` | `400` | Render resolution for OCR (Thai tone marks are small) |
| `--tesseract_cmd` | auto | Path to `tesseract.exe` if it isn't found automatically |
| `--vision_model` | `gpt-4.1` | Model for `--ocr_engine openai` |

**`python -m scripts.ask`**

| Option | Default | Description |
|---|---|---|
| `--question` | *(required)* | The question |
| `--index_dir` | `outputs/index` | Index to search |
| `--top_k` | `8` | Number of pages retrieved and shown to the model |
| `--show_context` | off | Also print the retrieved pages |

The API reads the index from `outputs/index`, or from the `RAG_INDEX_DIR` environment variable if set.

## Adding your own PDFs

1. Copy the PDF into `dataset/`.
2. Run `python -m scripts.ingest`.
3. Restart the API server if it is running.

Ingest decides page by page whether to use the PDF's text or OCR. Results are cached in `outputs/cache/`, so re-running ingest only processes new or changed files. If you add, change or remove files and forget to re-run ingest, `ask` and the API warn that the index is out of date.

## Thai and scanned PDFs

Some PDFs have no usable text: scanned pages, or Thai PDFs whose fonts don't map glyphs to real characters. The Thai standard used during development is one of these: its fonts have corrupt or missing character maps, so every PDF library extracts garbage from it. Ingest detects such pages and reads them with OCR instead. Without Tesseract, those pages are skipped and ingest tells you how many.

### Installing Tesseract and Poppler

| | Tesseract (with Thai) | Poppler |
|---|---|---|
| **Windows** | `winget install UB-Mannheim.TesseractOCR`, then tick *Thai* under "Additional language data" in the installer | Download a [release](https://github.com/oschwartz10612/poppler-windows/releases) and add its `Library\bin` folder to `PATH` |
| **macOS** | `brew install tesseract tesseract-lang` | `brew install poppler` |
| **Ubuntu / Debian** | `sudo apt install tesseract-ocr tesseract-ocr-tha` | `sudo apt install poppler-utils` |

On Windows, ingest finds `C:\Program Files\Tesseract-OCR\tesseract.exe` automatically. For another location, set `TESSERACT_CMD` or pass `--tesseract_cmd`.

For better Thai accuracy, download `tha.traineddata` and `eng.traineddata` from [tessdata_best](https://github.com/tesseract-ocr/tessdata_best) into a folder and set the `TESSDATA_PREFIX` environment variable to that folder.

> [!WARNING]
> **OCR is not perfect for Thai.** On a test page, OpenAI vision got every tone mark right where Tesseract made several mistakes (e.g. มั่นคง read as มั้นคง), but **neither engine read Thai numerals reliably**: dates, volume and clause numbers were often wrong. Check numbers against the original PDF.

### Reviewing OCR text by hand

```bash
python create_txt_from_pdf.py dataset/your-document.pdf
```

This writes `dataset/your-document_ocr.txt` with `--- Page N ---` markers. It accepts `--engine`, `--lang` and `--dpi`. While that file exists, ingest indexes it instead of the PDF, so you can correct OCR mistakes by editing it. An existing file is kept as `<name>_ocr.txt.<timestamp>.bak`.

### Thai text processing

All stored text is normalized:
- sara am that OCR splits into ํ + า is rejoined into ำ
- private-use glyphs from Thai fonts are mapped back to real characters
- mark order and zero-width characters are fixed

Search splits Thai into words with [PyThaiNLP](https://github.com/PyThaiNLP/pythainlp). So ดำเนินการ matches whether a document writes it with ำ or ํา, and Thai digits match Arabic ones (๒๕๖๘ = 2568).

## How retrieval works

Retrieval is **TF-IDF keyword search** (words and word pairs, cosine similarity), not embeddings. Because it matches words, questions must use the document's language and, ideally, its vocabulary.

The top-k pages are given to `gpt-4o-mini` as numbered context blocks, with instructions to answer only from them and to report which blocks it used. **Only those pages are cited.** If it reports none, all retrieved pages are listed.

## Project structure

```text
cyber_rag/
├── dataset/                  # Your documents (not included in this repository)
├── scripts/
│   ├── ingest.py             # Build the index
│   ├── ask.py                # Command-line Q&A
│   ├── api.py                # FastAPI app
│   ├── evaluate.py           # Writes outputs/eval_report.md
│   ├── extract.py            # PDF page text with automatic OCR fallback
│   ├── thai.py               # Thai normalization and word segmentation
│   ├── sources.py            # Which files get indexed; out-of-date index check
│   ├── chunking.py           # One chunk per page
│   ├── index.py              # TF-IDF index
│   └── generator.py          # Constrained LLM answer + citations
├── tests/                    # Offline tests
├── outputs/
│   ├── index/                # Built by ingest (not included)
│   ├── cache/                # Extracted / OCR'd page text (safe to delete)
│   └── eval_report.md        # Latest evaluation answers
├── create_txt_from_pdf.py    # OCR a whole PDF into an editable _ocr.txt
└── requirements.txt
```

## Evaluation

```bash
python -m scripts.evaluate
```

This asks 6 fixed questions (4 English, 2 Thai) and writes the answers and citations to [`outputs/eval_report.md`](outputs/eval_report.md).

## Tests

```bash
python -m pytest
```

The tests run offline and need no API key. Tests that use the original dataset PDFs are skipped when those files aren't present.
