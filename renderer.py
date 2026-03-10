"""
renderer.py - Genera el PDF a partir del HDXDocument

Usa WeasyPrint (HTML→PDF) como motor principal porque los .hdx
contienen HTML internamente — es la conversión más fiel.
Fallback: reportlab para sistemas sin GTK/Cairo.
"""

import re
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
    def _render_weasyprint(self, output_path: Path, include_toc: bool) -> None:
        from weasyprint import HTML, CSS

        html = self._build_html(include_toc)
        self._vlog(f"HTML document built: {len(html):,} chars")
        css = CSS(string=BASE_CSS)
        self._vlog("Calling WeasyPrint write_pdf() ...")

        # WeasyPrint renders to bytes; capture to get page-count metadata if possible
        wp_doc = HTML(string=html)
        pdf_bytes = wp_doc.write_pdf(stylesheets=[css])

        # Estimate page count from PDF cross-reference table entries
        page_count = self._estimate_pdf_pages(pdf_bytes)
        if page_count is not None:
            self._log(f"Rendered {page_count} page(s) via WeasyPrint")
        else:
            self._log("PDF rendered via WeasyPrint (page count unavailable)")

        output_path.write_bytes(pdf_bytes)
        self._vlog(f"Wrote {len(pdf_bytes):,} bytes to '{output_path}'")

    def _estimate_pdf_pages(self, pdf_bytes: bytes) -> int | None:
        """Parse /Count from the PDF page tree to get the page count."""
        try:
            # PDF stores page count as /Count <n> in the page tree root
            match = re.search(rb'/Count\s+(\d+)', pdf_bytes)
            if match:
                return int(match.group(1))
        except Exception:
            pass
        return None

    def _build_html(self, include_toc: bool) -> str:
        self._vlog(f"Building HTML: cover + {'TOC + ' if include_toc else ''}{len(self.doc.sections)} section(s)")
        parts = [f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>{self.doc.title}</title>
</head>
<body>

<!-- PORTADA -->
<div class="cover">
  <div class="huawei-bar"></div>
  <h1>{self.doc.title}</h1>
  <p class="subtitle">Documentación Técnica</p>
  <div class="huawei-bar"></div>
</div>
"""]

        # Tabla de contenidos
        if include_toc:
            toc_html = self._build_toc_html()
            parts.append(toc_html)

        # Secciones
        for section in self.doc.sections:
            tag = f"h{min(section.level, 3)}"
            parts.append(f"""
<{tag} id="sec-{id(section)}">{section.title}</{tag}>
{section.content_html}
""")

        parts.append("</body></html>")
        return "\n".join(parts)

    def _build_toc_html(self) -> str:
        toc_entries = len(self.doc.sections)
        self._log(f"Generating TOC: {toc_entries} entry/entries")
        # Break down by level for verbose detail
        level_counts: dict[int, int] = {}
        for s in self.doc.sections:
            lv = min(s.level, 3)
            level_counts[lv] = level_counts.get(lv, 0) + 1
        for lv in sorted(level_counts):
            self._vlog(f"  TOC level {lv}: {level_counts[lv]} entry/entries")

        lines = ['<div class="toc"><h2>Tabla de Contenidos</h2>']
        for section in self.doc.sections:
            css_class = f"toc-h{min(section.level, 3)}"
            lines.append(
                f'<div class="toc-entry {css_class}">'
                f'<a href="#sec-{id(section)}">{section.title}</a>'
                f'<span class="toc-dots"></span>'
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
