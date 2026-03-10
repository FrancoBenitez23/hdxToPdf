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

### Interactive mode

Run without arguments to launch the interactive menu:

```bash
python hdxtopdf.py
```

```
╭──────────────────────────╮
│ hdx2pdf                  │
│ Huawei .hdx → PDF        │
╰──────────────────────────╯
? Select an action:
  ❯ Convert file
    Batch convert folder
    Exit
```

### CLI mode

```bash
# Convert a single file
python hdxtopdf.py convert manual.hdx

# Specify output file
python hdxtopdf.py convert manual.hdx -o documentation.pdf

# Save to a directory
python hdxtopdf.py convert manual.hdx -o ./output/

# Verbose (shows processing details)
python hdxtopdf.py convert manual.hdx -v

# Without table of contents
python hdxtopdf.py convert manual.hdx --no-toc

# Batch: convert an entire folder
python hdxtopdf.py batch ./hdx_manuals/ -o ./pdfs/
```

## How it works

```
                    ┌─────────────────────────────────┐
                    │           hdxtopdf.py            │
                    │                                  │
                    │  interactive mode  │  CLI mode   │
                    │  (InquirerPy menu) │  (argparse) │
                    └────────────┬───────┴─────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │    commands/            │
                    │    convert_cmd.py       │
                    │  run_convert / run_batch│
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │    commands/functions/  │
                    │                         │
                    │  HDXExtractor           │
                    │  ├─ ZIP  → HTML files   │
                    │  ├─ HTML → direct parse │
                    │  └─ Text → headings     │
                    │          │              │
                    │          ▼              │
                    │  HDXDocument            │
                    │  (title + sections)     │
                    │          │              │
                    │          ▼              │
                    │  PDFRenderer            │
                    │  ├─ WeasyPrint (primary)│
                    │  └─ reportlab (fallback)│
                    └────────────┬────────────┘
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
├── hdxtopdf.py              # Entry point: CLI + interactive mode
├── commands/
│   ├── convert_cmd.py       # Command logic → ConvertResult / BatchResult
│   └── functions/
│       ├── extractor.py     # Reads .hdx → HDXDocument with sections
│       └── renderer.py      # HDXDocument → PDF (WeasyPrint + pikepdf)
├── prompts/
│   └── interactive.py       # InquirerPy interactive menu flows
├── ui/
│   └── output.py            # Rich-based output (print_success, spinner, etc.)
├── exceptions/
│   └── __init__.py          # CLISoftError, CommandError, PromptAbortedError
└── requirements.txt
```

## Troubleshooting

**Empty PDF**
→ Run with `-v` to see how many sections the extractor detected.

**Garbled characters / encoding issues**
→ For Huawei documents in Chinese (GB2312), change in `extractor.py`:
`raw.decode("gb2312", errors="replace")`
