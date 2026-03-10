# hdx2pdf

Converts Huawei `.hdx` documentation files to PDF.

> **Status:** functional v1 prototype. Tested with files up to 171 MB and 17,000+ sections.

## Installation

```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

On Linux, WeasyPrint requires system libraries:
```bash
sudo apt install libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev
```

## Usage

```bash
# Basic
python convert.py manual.hdx

# Specify output file
python convert.py manual.hdx -o documentation.pdf

# Save to a directory
python convert.py manual.hdx -o ./output/

# Verbose (shows processing details)
python convert.py manual.hdx -v

# Without table of contents
python convert.py manual.hdx --no-toc

# Batch: convert an entire folder
python convert.py ./hdx_manuals/ -o ./pdfs/
```

## How it works

```
file.hdx
    │
    ▼
HDXExtractor
  ├─ ZIP  → extracts internal HTML files
  ├─ HTML → parses directly
  └─ Text → splits on numbered headings
    │
    ▼
HDXDocument (title + sections)
    │
    ▼
PDFRenderer
  ├─ WeasyPrint (primary): HTML+CSS → PDF with Huawei styling
  └─ reportlab  (fallback): no GTK dependencies required
    │
    ▼
  output.pdf
```

## Large documents

For files with more than 200 sections, the renderer splits the document into 200-section chunks and renders them in parallel (6 workers), then merges them with pikepdf. This allows converting documents with thousands of sections without hanging.

```
[render] Large document (17462 sections) — splitting into 88 chunk(s)
[render] Rendering 88 chunk(s) in parallel (max_workers=6) ...
[render]   Chunk 3/88 done ...
[render]   Chunk 1/88 done ...
[render] Merging 88 chunk PDF(s) -> output.pdf ...
```

Log order is non-sequential (parallel rendering), but the final PDF always preserves the correct order.

## Project structure

```
hdx2pdf/
├── convert.py       # CLI: argument parsing, batch mode, orchestration
├── extractor.py     # Reads .hdx → HDXDocument with sections
├── renderer.py      # HDXDocument → PDF (WeasyPrint + pikepdf)
└── requirements.txt
```

## Troubleshooting

**Empty PDF**
→ Run with `-v` to see how many sections the extractor detected.

**Garbled characters / encoding issues**
→ For Huawei documents in Chinese (GB2312), change in `extractor.py`:
`raw.decode("gb2312", errors="replace")`
