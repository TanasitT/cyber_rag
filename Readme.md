Cybersecurity Dataset-Only RAG System

This project implements a Retrieval-Augmented Generation (RAG) system that answers cybersecurity-related questions using only documents provided in the dataset/ folder.

The system is designed to:

-Prevent hallucination
-Avoid external knowledge
-Provide page-level citations for the pages the answer actually used
-Return a refusal when the dataset does not contain sufficient information
-Accept any PDF you drop into dataset/, including scanned pages and Thai PDFs (via OCR)

[Project Structure]
cyber_rag/
├── dataset/                       # Input documents (PDF / TXT, subfolders allowed)
│   ├── owasp-top-10.pdf
│   ├── mitre-attack-philosophy-2020.pdf
│   ├── thailand-web-security-standard-2025.pdf
│   └── thailand-web-security-standard-2025_ocr.txt   # OCR text, indexed instead of the PDF above
│
├── scripts/
│   ├── ingest.py            # Build the index
│   ├── ask.py               # CLI question answering
│   ├── api.py               # FastAPI application
│   ├── evaluate.py          # Writes outputs/eval_report.md
│   ├── extract.py           # PDF page text, with automatic OCR fallback
│   ├── thai.py              # Thai text normalization + word segmentation
│   ├── sources.py           # Which files get indexed; out-of-date index check
│   ├── chunking.py          # Page-based chunking
│   ├── index.py             # TF-IDF index
│   └── generator.py         # Constrained LLM generation + citations
│
├── tests/                         # Offline tests (python -m pytest)
├── create_txt_from_pdf.py         # OCR a whole PDF into an editable _ocr.txt
│
├── outputs/
│   ├── index/               # Saved index + manifest.json
│   ├── cache/               # Extracted / OCR'd page text (safe to delete)
│   └── eval_report.md
│
├── requirements.txt
└── Readme.md

Note: the dataset PDFs are not included in this repository. The built index in outputs/index/ already contains their text, so ask.py, the API and evaluate.py work right after cloning. Re-running ingest rebuilds the index from what is in dataset/: put the PDFs (or your own) there first, otherwise only the Thai OCR text is indexed.

[Requirements Installation]

Optional, only needed to OCR PDFs without usable text (scans, Thai PDFs with broken fonts; see "Thai and Scanned PDFs"):

Tesseract OCR with Thai language data
Poppler (for PDF → image conversion; must be on PATH)

Without them everything else works; ingest skips the pages that would need OCR and says how many.

[Dependencies Installation]

1.Install Python packages

pip install -r requirements.txt

2.Set up OpenAI API Key

Set your API key as an environment variable:

PowerShell:  $env:OPENAI_API_KEY = "sk-..."
bash:        export OPENAI_API_KEY="sk-..."

[**Running the Project**]

Step 1: Run the ingestion script:

python -m scripts.ingest --dataset_dir dataset --index_dir outputs/index

(Those are the defaults, so "python -m scripts.ingest" is enough.)

This will:

-Load every PDF / TXT file in dataset/ (subfolders included)
-Read each PDF page's text, or OCR the page when it has no usable text
-Chunk by page
-Build the TF-IDF index
-Save the index to outputs/index/

It prints one line per file, for example:

dataset/thailand-web-security-standard-2025.pdf: skipped, using thailand-web-security-standard-2025_ocr.txt instead
dataset/mitre-attack-philosophy-2020.pdf: 46 pages
dataset/owasp-top-10.pdf: 41 pages
dataset/thailand-web-security-standard-2025_ocr.txt: 77 pages
Indexed 164 pages from 3 files into: ...\outputs\index

Files that can't be read (corrupt, password-protected) are skipped with a warning; the rest are still indexed.

Step 2: Ask Questions (CLI)

python -m scripts.ask --question "What is MITRE ATT&CK, and what is its primary purpose?"

Options: --top_k (pages retrieved, default 8), --show_context (print the retrieved pages).
Note: You have to ask in a language that is the same from the source file (English for English files, Thai for Thai files). Search matches words; it does not translate.

Example output:

QUESTION:
What is MITRE ATT&CK, and what is its primary purpose?

ANSWER:
MITRE ATT&CK is a knowledge base that documents adversary tactics and techniques based on real-world observations. Its primary purpose is to serve as an authoritative source of information about adversarial behavior, guiding users in understanding how to defend against adversaries by categorizing their actions and relating them to defensive measures. ...

CITATIONS:
- dataset/mitre-attack-philosophy-2020.pdf#page_44
- dataset/mitre-attack-philosophy-2020.pdf#page_4

If the dataset does not contain the answer:

ANSWER:
Insufficient information in dataset.

Step 3: Run the FastAPI Server

Start the API:

uvicorn scripts.api:app --reload

Open API docs at:

http://127.0.0.1:8000/docs

Example API request
POST /ask
{
  "question": "What is OWASP Top 10?",
  "top_k": 8
}

top_k must be between 1 and 20. Restart the server after re-running ingest; it loads the index once at startup.

[Adding Your Own PDFs]

1. Copy the PDF into dataset/ (subfolders are fine).
2. Run: python -m scripts.ingest
3. Restart the API server if it is running.

Ingest decides page by page whether to use the PDF's text or OCR. Results are cached in outputs/cache/, so re-running ingest only processes new or changed files. If you add, change or remove files and forget to re-run ingest, ask.py and the API print a warning that the index is out of date.

[Thai and Scanned PDFs]

Some PDFs have no usable text: scanned pages, or Thai PDFs whose fonts don't map glyphs to real characters. The Thai standard in dataset/ is one of these: its fonts have corrupt or missing character maps, so every PDF library extracts garbage from it. Ingest detects such pages and reads them with OCR instead.

Install Tesseract (Windows):

winget install UB-Mannheim.TesseractOCR

Then make sure Thai language data is installed: tick Thai under "Additional language data" in the installer, or download tha.traineddata into C:\Program Files\Tesseract-OCR\tessdata. Ingest finds C:\Program Files\Tesseract-OCR\tesseract.exe automatically; for another location set TESSERACT_CMD or pass --tesseract_cmd.

For better Thai accuracy, download the tessdata_best models (tha.traineddata and eng.traineddata) from https://github.com/tesseract-ocr/tessdata_best into a folder and set the TESSDATA_PREFIX environment variable to that folder.

Without Tesseract, pages that need OCR are skipped and ingest tells you how many.

OCR options for ingest:
--ocr_lang tha+eng      Tesseract languages
--ocr_dpi 400           render resolution (Thai tone marks are small)
--ocr_engine openai     use an OpenAI vision model instead of Tesseract (sends page images to OpenAI)
--vision_model gpt-4.1  model for --ocr_engine openai

OCR accuracy for Thai: on a test page, OpenAI vision got every tone mark right where Tesseract made several mistakes (e.g. มั่นคง read as มั้นคง), but neither engine read Thai numerals reliably: dates, volume and clause numbers were often wrong. Check numbers against the original PDF.

Review or correct OCR text by hand:

python create_txt_from_pdf.py dataset/thailand-web-security-standard-2025.pdf

This writes dataset/<name>_ocr.txt with "--- Page N ---" markers (it accepts the same --engine/--lang/--dpi options). While that file exists, ingest indexes it instead of the PDF. An existing file is kept as <name>_ocr.txt.<timestamp>.bak.

Thai text processing: all stored text is normalized (sara am split into ํ + า by OCR is rejoined into ำ, Thai-font private-use glyphs are mapped back, mark order and zero-width characters are fixed), and search splits Thai into words with PyThaiNLP. So ดำเนินการ matches whether a document writes it with ำ or ํา, and Thai digits match Arabic ones (๒๕๖๘ = 2568).

[How Retrieval Works]

Retrieval is TF-IDF keyword search (words and word pairs, cosine similarity), not embeddings; the "Embed Chunks" step in diagram.png is this TF-IDF step. Because it matches words, questions must use the document's language and, ideally, its vocabulary.

The model is shown the top-k pages (numbered) and reports which ones its answer is based on; only those pages are cited. If it cites none, all retrieved pages are listed.

[Evaluation]

To generate the report, you can run the following command which will create eval_report.md

python -m scripts.evaluate --index_dir outputs/index --out outputs/eval_report.md

It asks 6 fixed questions (4 English, 2 Thai). See outputs/eval_report.md for the latest answers and citations.

[Tests]

python -m pytest

The tests run offline and need no API key.
