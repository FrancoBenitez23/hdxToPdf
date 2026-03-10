# hdx2pdf Agent Memory

## Logging Convention (established session 1)

Two-tier logging pattern used across all modules:

- `_log(msg)`  — always prints; prefix `  [module]`
- `_vlog(msg)` — prints only when `self.verbose=True`; prefix `  [module:v]`

Modules and their prefixes:
- `HDXExtractor` -> `[extract]` / `[extract:v]`
- `PDFRenderer`  -> `[render]`  / `[render:v]`
- `convert_file` -> `[hdx2pdf]` (direct print, no helper needed)

## Key Milestone Logs (always visible, no -v needed)

extractor.py:
- File size on read
- Format detected (ZIP / direct HTML / plain text)
- ZIP total file count
- HTML files found in ZIP count
- Per-HTML-file section count
- Final total section count

renderer.py:
- Section count at render start
- PDF engine selected (WeasyPrint vs reportlab)
- TOC entry count
- Page count (WeasyPrint; parsed from /Count in PDF bytes via regex)
- Final file size (reportlab path)

convert.py:
- Step 1/2 and 2/2 banners
- Section count after extraction (always, not just verbose)
- WARNING when 0 sections detected
- Wall-clock time for extraction and total
- Final output path + size + elapsed time

## Page Count Strategy (WeasyPrint)

WeasyPrint does not expose a page count API. Instead:
1. Call `HTML(string=html).write_pdf(stylesheets=[css])` to get `bytes`
2. Search `rb'/Count\s+(\d+)'` in those bytes — PDF page tree stores `/Count N`
3. The largest match is the total page count (smaller ones are sub-trees)
   - Current impl returns the FIRST match; may undercount on very large docs
   - Improve later if needed: find max of all matches

## Architecture Reminders

- `extractor.py` must NEVER import from `renderer.py`
- All Huawei-specific logic stays in `extractor.py`
- `renderer.py` is format-agnostic
- New format handling always needs a `# FORMAT: <description>` comment
- All paths via `pathlib.Path`; no hardcoded strings
