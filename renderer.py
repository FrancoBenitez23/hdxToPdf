"""
renderer.py - Genera el PDF a partir del HDXDocument

Usa WeasyPrint (HTML→PDF) como motor principal porque los .hdx
contienen HTML internamente — es la conversión más fiel.
Fallback: reportlab para sistemas sin GTK/Cairo.
"""

import re
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from extractor import HDXDocument, Section


# ──────────────────────────────────────────────
# CSS base para el PDF (estilo técnico/manual)
# ──────────────────────────────────────────────
BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@400;600;700&family=Source+Code+Pro&display=swap');

@page {
    size: A4;
    margin: 2.5cm 2cm 2.5cm 2.5cm;
    @bottom-center {
        content: counter(page) " / " counter(pages);
        font-size: 9pt;
        color: #888;
    }
    @top-right {
        content: string(doc-title);
        font-size: 8pt;
        color: #888;
    }
}

body {
    font-family: 'Source Sans Pro', Arial, sans-serif;
    font-size: 10pt;
    line-height: 1.6;
    color: #1a1a1a;
}

h1 {
    font-size: 20pt;
    color: #CC0000;   /* Rojo Huawei */
    border-bottom: 2px solid #CC0000;
    padding-bottom: 6pt;
    margin-top: 30pt;
    string-set: doc-title content();
    page-break-before: always;
}
h1:first-of-type { page-break-before: avoid; }

h2 {
    font-size: 14pt;
    color: #333;
    border-left: 4px solid #CC0000;
    padding-left: 8pt;
    margin-top: 20pt;
}

h3 {
    font-size: 11pt;
    color: #555;
    margin-top: 14pt;
}

p { margin: 6pt 0; }

table {
    border-collapse: collapse;
    width: 100%;
    margin: 12pt 0;
    font-size: 9pt;
}
th {
    background: #CC0000;
    color: white;
    padding: 6pt 8pt;
    text-align: left;
}
td {
    padding: 5pt 8pt;
    border: 1px solid #ddd;
}
tr:nth-child(even) td { background: #f9f9f9; }

code, pre {
    font-family: 'Source Code Pro', 'Courier New', monospace;
    background: #f4f4f4;
    border: 1px solid #ddd;
    border-radius: 3px;
    font-size: 8.5pt;
}
code { padding: 1pt 4pt; }
pre {
    padding: 10pt;
    overflow-x: auto;
    white-space: pre-wrap;
}

ul, ol { margin: 6pt 0; padding-left: 20pt; }
li { margin: 3pt 0; }

.toc { margin: 20pt 0; }
.toc h2 { color: #CC0000; }
.toc a { color: #333; text-decoration: none; }
.toc-entry { display: flex; margin: 4pt 0; }
.toc-entry .toc-dots { flex: 1; border-bottom: 1px dotted #ccc; margin: 0 6pt; }
.toc-h1 { font-weight: 600; margin-top: 8pt; }
.toc-h2 { padding-left: 16pt; }
.toc-h3 { padding-left: 32pt; font-size: 9pt; color: #555; }

.cover {
    text-align: center;
    padding-top: 100pt;
    page-break-after: always;
}
.cover h1 {
    border: none;
    font-size: 28pt;
    color: #CC0000;
    page-break-before: avoid;
}
.cover .subtitle {
    font-size: 14pt;
    color: #555;
    margin-top: 12pt;
}
.cover .huawei-bar {
    width: 80pt;
    height: 6pt;
    background: #CC0000;
    margin: 20pt auto;
}

img {
    max-width: 100%;
    height: auto;
}

.note {
    background: #fff8e1;
    border-left: 4px solid #ffc107;
    padding: 8pt 12pt;
    margin: 10pt 0;
    font-size: 9pt;
}
.warning {
    background: #fff3f3;
    border-left: 4px solid #CC0000;
    padding: 8pt 12pt;
    margin: 10pt 0;
    font-size: 9pt;
}
"""


# ──────────────────────────────────────────────────────────────────────────────
# Module-level helpers for multiprocessing workers
#
# ProcessPoolExecutor serialises arguments and return values with pickle.
# Instance methods (self.*) are not picklable, so all logic that runs inside
# a worker process must live at module level and receive plain data.
# ──────────────────────────────────────────────────────────────────────────────

def _build_toc_html_standalone(
    all_sections: list[Section],
    max_toc_entries: int,
) -> str:
    """Module-level TOC builder (mirrors PDFRenderer._build_toc_html).

    Accepts plain Section objects so it can be called from worker processes
    without any reference to the PDFRenderer instance.
    """
    total = len(all_sections)

    if total > max_toc_entries:
        candidates = [s for s in all_sections if s.level == 1]
        if not candidates:
            candidates = all_sections
    else:
        candidates = all_sections

    truncated = len(candidates) > max_toc_entries
    toc_sections = candidates[:max_toc_entries]

    lines = ['<div class="toc"><h2>Table of Contents</h2>']
    for section in toc_sections:
        css_class = f"toc-h{min(section.level, 3)}"
        title_safe = section.title.replace("<", "&lt;").replace(">", "&gt;")
        lines.append(
            f'<div class="toc-entry {css_class}">'
            f'<a href="#sec-{id(section)}">{title_safe}</a>'
            f'<span class="toc-dots"></span>'
            f'</div>'
        )
    if truncated:
        lines.append(
            f'<div class="toc-entry toc-h1" style="color:#888;font-style:italic;">'
            f'... and {total - len(toc_sections)} more section(s) not shown in TOC'
            f'</div>'
        )
    lines.append('</div>')
    return "\n".join(lines)


def _build_html_chunk_standalone(
    doc_title: str,
    sections: list[Section],
    include_cover: bool,
    include_toc: bool,
    all_sections_for_toc: list[Section],
    max_toc_entries: int,
) -> str:
    """Module-level HTML chunk builder (mirrors PDFRenderer._build_html_chunk).

    All arguments are plain data so the function is fully picklable.
    """
    parts = [f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{doc_title}</title>
</head>
<body>
"""]

    if include_cover:
        title_safe = doc_title.replace("<", "&lt;").replace(">", "&gt;")
        parts.append(f"""<!-- COVER -->
<div class="cover">
  <div class="huawei-bar"></div>
  <h1>{title_safe}</h1>
  <p class="subtitle">Technical Documentation</p>
  <div class="huawei-bar"></div>
</div>
""")

    if include_toc:
        toc_html = _build_toc_html_standalone(all_sections_for_toc, max_toc_entries)
        parts.append(toc_html)

    for section in sections:
        tag = f"h{min(section.level, 3)}"
        title_safe = section.title.replace("<", "&lt;").replace(">", "&gt;")
        parts.append(f"""<{tag} id="sec-{id(section)}">{title_safe}</{tag}>
{section.content_html}
""")

    parts.append("</body></html>")
    return "\n".join(parts)


# ChunkJob bundles every piece of data a worker needs to render one chunk.
# Using a plain tuple keeps it pickle-safe across all Python versions.
#   [0] chunk_index    int
#   [1] n_chunks       int
#   [2] doc_title      str
#   [3] sections       list[Section]
#   [4] include_cover  bool
#   [5] include_toc    bool
#   [6] all_sections   list[Section]   (for TOC — only meaningful in chunk 0)
#   [7] max_toc        int
#   [8] tmp_dir        str             (directory where temp file is created)
#   [9] css_string     str             (BASE_CSS rendered as a string)

def _render_chunk_worker(args: tuple) -> tuple[int, str, int]:
    """Worker: build HTML for one chunk and render it to a temp PDF file.

    Runs inside a subprocess spawned by ProcessPoolExecutor.

    Returns:
        (chunk_index, temp_file_path, page_count)
    """
    (
        chunk_index,
        n_chunks,
        doc_title,
        sections,
        include_cover,
        include_toc,
        all_sections,
        max_toc,
        tmp_dir,
        css_string,
    ) = args

    from weasyprint import HTML, CSS  # imported inside worker to avoid pickling issues

    html = _build_html_chunk_standalone(
        doc_title=doc_title,
        sections=sections,
        include_cover=include_cover,
        include_toc=include_toc,
        all_sections_for_toc=all_sections,
        max_toc_entries=max_toc,
    )

    css = CSS(string=css_string)
    pdf_bytes = HTML(string=html).write_pdf(stylesheets=[css])

    # Estimate page count the same way PDFRenderer does.
    matches = re.findall(rb'/Count\s+(\d+)', pdf_bytes)
    page_count = max(int(m) for m in matches) if matches else 0

    # Write to a deterministically named temp file so the parent can sort by index.
    chunk_path = Path(tmp_dir) / f"chunk_{chunk_index:04d}.pdf"
    chunk_path.write_bytes(pdf_bytes)

    return chunk_index, str(chunk_path), page_count


class PDFRenderer:
    def __init__(self, doc: HDXDocument, verbose: bool = False):
        self.doc = doc
        self.verbose = verbose

    # ------------------------------------------------------------------
    # Internal logging helpers
    # ------------------------------------------------------------------
    def _log(self, msg: str) -> None:
        """Always-visible milestone log."""
        print(f"  [render] {msg}")

    def _vlog(self, msg: str) -> None:
        """Verbose-only detail log."""
        if self.verbose:
            print(f"  [render:v] {msg}")

    def render(self, output_path: Path, include_toc: bool = True) -> None:
        """Renderiza el documento a PDF. Intenta WeasyPrint primero, luego reportlab."""
        self._log(f"Starting PDF render for '{self.doc.title}' ({len(self.doc.sections)} section(s))")
        self._vlog(f"TOC generation: {'enabled' if include_toc else 'disabled'}")
        try:
            self._log("PDF engine: WeasyPrint (primary)")
            self._render_weasyprint(output_path, include_toc)
        except ImportError:
            self._log("PDF engine: reportlab (fallback — WeasyPrint not available)")
            self._render_reportlab(output_path, include_toc)

    # ──────────────────────────────────────────────
    # Motor 1: WeasyPrint (HTML → PDF, alta fidelidad)
    # ──────────────────────────────────────────────

    # Number of sections rendered per WeasyPrint call.  Keeps each HTML
    # document under ~2 MB even for very large .hdx files.
    _CHUNK_SIZE: int = 200

    def _render_weasyprint(self, output_path: Path, include_toc: bool) -> None:
        from weasyprint import HTML, CSS
        import pikepdf

        css = CSS(string=BASE_CSS)
        sections = self.doc.sections
        total = len(sections)

        # For small documents render in one pass (original behaviour).
        if total <= self._CHUNK_SIZE:
            html = self._build_html_chunk(
                sections,
                include_cover=True,
                include_toc=include_toc,
            )
            self._vlog(f"HTML document built: {len(html):,} chars (single chunk)")
            self._vlog("Calling WeasyPrint write_pdf() ...")
            pdf_bytes = HTML(string=html).write_pdf(stylesheets=[css])
            page_count = self._estimate_pdf_pages(pdf_bytes)
            if page_count is not None:
                self._log(f"Rendered {page_count} page(s) via WeasyPrint")
            else:
                self._log("PDF rendered via WeasyPrint (page count unavailable)")
            output_path.write_bytes(pdf_bytes)
            self._vlog(f"Wrote {len(pdf_bytes):,} bytes to '{output_path}'")
            return

        # Large document: split into chunks, render all chunks in parallel,
        # then merge the resulting PDFs in order.
        chunks = [
            sections[i : i + self._CHUNK_SIZE]
            for i in range(0, total, self._CHUNK_SIZE)
        ]
        n_chunks = len(chunks)
        self._log(
            f"Large document ({total} sections) — splitting into {n_chunks} chunk(s)"
            f" of up to {self._CHUNK_SIZE} sections each"
        )
        self._log(f"Rendering {n_chunks} chunk(s) in parallel (max_workers=6) ...")

        # Build the argument tuple for each worker.  Every item must be
        # pickle-safe because ProcessPoolExecutor uses inter-process pickling.
        def _make_job(idx: int, chunk: list[Section]) -> tuple:
            return (
                idx,                          # chunk_index
                n_chunks,                     # n_chunks  (for log messages in worker)
                self.doc.title,               # doc_title
                chunk,                        # sections for this chunk
                idx == 0,                     # include_cover
                include_toc and idx == 0,     # include_toc
                self.doc.sections,            # all_sections (TOC uses the full list)
                self._MAX_TOC_ENTRIES,        # max_toc
                tmp_dir,                      # directory for temp file
                BASE_CSS,                     # css as a plain string
            )

        # results[chunk_index] = (chunk_index, path_str, page_count)
        results: dict[int, tuple[int, str, int]] = {}

        with tempfile.TemporaryDirectory() as tmp_dir:
            jobs = [_make_job(idx, chunk) for idx, chunk in enumerate(chunks)]

            with ProcessPoolExecutor(max_workers=6) as executor:
                future_to_idx = {
                    executor.submit(_render_chunk_worker, job): job[0]
                    for job in jobs
                }
                for future in as_completed(future_to_idx):
                    chunk_index, path_str, page_count = future.result()
                    results[chunk_index] = (chunk_index, path_str, page_count)
                    self._log(
                        f"  Chunk {chunk_index + 1}/{n_chunks} done"
                        f" ({page_count} page(s)) -> {Path(path_str).name}"
                    )

            # Merge all chunk PDFs in chunk-index order.
            total_pages = sum(r[2] for r in results.values())
            ordered_paths = [results[i][1] for i in range(n_chunks)]

            self._log(f"Merging {n_chunks} chunk PDF(s) -> {output_path.name} ...")
            merged = pikepdf.Pdf.new()
            for path_str in ordered_paths:
                src = pikepdf.Pdf.open(path_str)
                merged.pages.extend(src.pages)
            merged.save(str(output_path))

            # Temp files are cleaned up automatically when the TemporaryDirectory
            # context manager exits — no manual deletion needed.

        self._log(
            f"Rendered ~{total_pages} page(s) via WeasyPrint"
            f" ({n_chunks} chunk(s) merged)"
        )
        self._vlog(
            f"Wrote {output_path.stat().st_size:,} bytes to '{output_path}'"
        )

    def _estimate_pdf_pages(self, pdf_bytes: bytes) -> int | None:
        """Parse /Count from the PDF page tree to get the page count."""
        try:
            # PDF stores page count as /Count <n> in the page tree root.
            # Take the largest match — sub-trees also store /Count but smaller.
            matches = re.findall(rb'/Count\s+(\d+)', pdf_bytes)
            if matches:
                return max(int(m) for m in matches)
        except Exception:
            pass
        return None

    def _build_html_chunk(
        self,
        sections: list[Section],
        *,
        include_cover: bool,
        include_toc: bool,
    ) -> str:
        """Build a self-contained HTML document for a slice of sections.

        Args:
            sections:      The subset of sections to render in this chunk.
            include_cover: Whether to prepend the cover page.
            include_toc:   Whether to include the TOC (uses self.doc for the
                           full section list, not just this chunk's slice).
        """
        n = len(sections)
        cover_flag = "cover + " if include_cover else ""
        toc_flag   = "TOC + " if include_toc else ""
        self._vlog(f"Building HTML chunk: {cover_flag}{toc_flag}{n} section(s)")

        parts = [f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{self.doc.title}</title>
</head>
<body>
"""]

        if include_cover:
            title_safe = self.doc.title.replace("<", "&lt;").replace(">", "&gt;")
            parts.append(f"""<!-- COVER -->
<div class="cover">
  <div class="huawei-bar"></div>
  <h1>{title_safe}</h1>
  <p class="subtitle">Technical Documentation</p>
  <div class="huawei-bar"></div>
</div>
""")

        if include_toc:
            toc_html = self._build_toc_html()
            parts.append(toc_html)

        for section in sections:
            tag = f"h{min(section.level, 3)}"
            title_safe = section.title.replace("<", "&lt;").replace(">", "&gt;")
            parts.append(f"""<{tag} id="sec-{id(section)}">{title_safe}</{tag}>
{section.content_html}
""")

        parts.append("</body></html>")
        return "\n".join(parts)

    # Keep _build_html as a thin wrapper so any external code calling it
    # still works (renders all sections in one shot).
    def _build_html(self, include_toc: bool) -> str:
        return self._build_html_chunk(
            self.doc.sections,
            include_cover=True,
            include_toc=include_toc,
        )

    # Maximum TOC entries to render.  Documents with 1000s of sections produce
    # enormous TOCs that bloat the HTML and slow WeasyPrint to a halt.
    _MAX_TOC_ENTRIES: int = 300

    def _build_toc_html(self) -> str:
        """Build TOC HTML.

        Strategy for very large documents:
        - Prefer level-1 (chapter) entries only; fall back to all levels when
          the document has few sections.
        - Cap the final list at _MAX_TOC_ENTRIES to keep HTML size manageable.
        """
        all_sections = self.doc.sections
        total = len(all_sections)

        # Collect level-1 sections first; use all levels for small docs.
        if total > self._MAX_TOC_ENTRIES:
            candidates = [s for s in all_sections if s.level == 1]
            if not candidates:
                candidates = all_sections  # nothing at level 1 — use all
        else:
            candidates = all_sections

        truncated = len(candidates) > self._MAX_TOC_ENTRIES
        toc_sections = candidates[: self._MAX_TOC_ENTRIES]

        self._log(
            f"Generating TOC: {len(toc_sections)} entry/entries"
            f" (of {total} total section(s)"
            + (f", capped at {self._MAX_TOC_ENTRIES}" if truncated else "")
            + ")"
        )

        # Verbose breakdown by level
        level_counts: dict[int, int] = {}
        for s in toc_sections:
            lv = min(s.level, 3)
            level_counts[lv] = level_counts.get(lv, 0) + 1
        for lv in sorted(level_counts):
            self._vlog(f"  TOC level {lv}: {level_counts[lv]} entry/entries")

        lines = ['<div class="toc"><h2>Table of Contents</h2>']
        for section in toc_sections:
            css_class = f"toc-h{min(section.level, 3)}"
            title_safe = section.title.replace("<", "&lt;").replace(">", "&gt;")
            lines.append(
                f'<div class="toc-entry {css_class}">'
                f'<a href="#sec-{id(section)}">{title_safe}</a>'
                f'<span class="toc-dots"></span>'
                f'</div>'
            )
        if truncated:
            lines.append(
                f'<div class="toc-entry toc-h1" style="color:#888;font-style:italic;">'
                f'... and {total - len(toc_sections)} more section(s) not shown in TOC'
                f'</div>'
            )
        lines.append('</div>')
        return "\n".join(lines)

    # ──────────────────────────────────────────────
    # Motor 2: reportlab (fallback sin dependencias GTK)
    # ──────────────────────────────────────────────
    def _render_reportlab(self, output_path: Path, include_toc: bool) -> None:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, PageBreak, HRFlowable
        )
        from reportlab.platypus.tableofcontents import TableOfContents
        from bs4 import BeautifulSoup

        HUAWEI_RED = colors.HexColor("#CC0000")

        self._vlog("Building reportlab SimpleDocTemplate ...")
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            leftMargin=2.5*cm, rightMargin=2*cm,
            topMargin=2.5*cm, bottomMargin=2.5*cm
        )

        styles = getSampleStyleSheet()
        style_h1 = ParagraphStyle("H1", parent=styles["Heading1"], textColor=HUAWEI_RED, fontSize=16, spaceAfter=12)
        style_h2 = ParagraphStyle("H2", parent=styles["Heading2"], textColor=colors.HexColor("#333333"), fontSize=12)
        style_h3 = ParagraphStyle("H3", parent=styles["Heading3"], fontSize=10)
        style_body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9, leading=14)

        story = []

        # Portada
        self._vlog("Adding cover page to story ...")
        story.append(Spacer(1, 3*cm))
        story.append(HRFlowable(width="100%", color=HUAWEI_RED, thickness=3))
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph(self.doc.title, ParagraphStyle(
            "Cover", parent=styles["Title"], textColor=HUAWEI_RED, fontSize=24, alignment=1
        )))
        story.append(Spacer(1, 0.3*cm))
        story.append(HRFlowable(width="100%", color=HUAWEI_RED, thickness=3))
        story.append(PageBreak())

        if include_toc:
            self._log(f"Generating TOC: {len(self.doc.sections)} entry/entries (reportlab)")

        # Secciones
        flowable_count = 0
        for section in self.doc.sections:
            level = min(section.level, 3)
            heading_style = [style_h1, style_h2, style_h3][level - 1]

            if level == 1:
                story.append(PageBreak())

            story.append(Paragraph(section.title, heading_style))
            story.append(Spacer(1, 0.2*cm))
            flowable_count += 2

            # Parsear HTML del contenido
            soup = BeautifulSoup(section.content_html, "html.parser")
            for elem in soup.descendants:
                if elem.name == "p":
                    text = elem.get_text(strip=True)
                    if text:
                        story.append(Paragraph(text, style_body))
                        story.append(Spacer(1, 0.15*cm))
                        flowable_count += 2
                elif elem.name in ("li",):
                    text = elem.get_text(strip=True)
                    if text:
                        story.append(Paragraph(f"• {text}", style_body))
                        flowable_count += 1

        self._vlog(f"Story built: {flowable_count} content flowable(s) across {len(self.doc.sections)} section(s)")
        self._vlog("Calling reportlab doc.build() ...")
        doc.build(story)
        self._log(f"PDF written via reportlab ({output_path.stat().st_size / 1024:.1f} KB)")


class _PageNumCanvas:
    """Mixin para números de página con reportlab (si se necesita extender)."""
    pass
