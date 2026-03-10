# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**hdx2pdf** — converts Huawei `.hdx` documentation files to PDF. The `.hdx` format (HelpNDoc) can be a ZIP archive containing HTML, a raw HTML file, or plain text; the tool detects the format automatically.

## Setup

```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

On Linux, WeasyPrint requires system libs:
```bash
sudo apt install libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev
```

## Running the Converter

```bash
# Single file
python convert.py archivo.hdx

# Specify output
python convert.py archivo.hdx -o salida.pdf

# Output to directory
python convert.py archivo.hdx -o ./output/

# Verbose (shows detected format, section count, etc.)
python convert.py archivo.hdx -v

# Without table of contents
python convert.py archivo.hdx --no-toc

# Batch: convert all .hdx files in a folder
python convert.py ./manuales_hdx/ -o ./pdfs/
```

## Architecture

Three files make up the entire project:

**`convert.py`** — CLI entry point. Parses args, handles single-file and batch modes, wires `HDXExtractor` → `PDFRenderer`.

**`extractor.py`** — Reads an `.hdx` file and returns an `HDXDocument`. Detection order:
1. ZIP (magic bytes `PK`) → extracts all `.html`/`.htm`/`.xhtml` files, parses each into sections
2. HTML (checks first 500 bytes for `<html` or `<!doctype`) → parses directly
3. Fallback → reads as UTF-8 text, splits on numbered headings (`1.2.3 Title`, `Chapter N:`, `==Title==`)

Key data classes (both in `extractor.py`):
- `Section(title, content_html, level, images)` — one heading block; `level` 1/2/3 maps to h1/h2/h3
- `HDXDocument(title, sections, metadata)` — the full parsed document

**`renderer.py`** — Takes an `HDXDocument` and writes a PDF. Two engines:
- **WeasyPrint** (primary): builds a full HTML string with `BASE_CSS`, passes to `weasyprint.HTML.write_pdf()`. Produces high-fidelity output with cover page, TOC, and Huawei-branded styling (red `#CC0000`).
- **reportlab** (fallback, auto-activated on `ImportError`): uses `SimpleDocTemplate` + `Paragraph` flowables; strips HTML via BeautifulSoup; no CSS rendering.

## Key Notes

- All three source files import from each other at the project root level (no `src/` subdirectory despite README showing one).
- The `env/` directory is the virtualenv — ignore it when searching for project code.
- For Huawei docs in Chinese (GB2312 encoding), change the decode call in `extractor.py` from `utf-8` to `gb2312`.
- If a PDF comes out empty, run with `-v` to see how many sections were detected.
