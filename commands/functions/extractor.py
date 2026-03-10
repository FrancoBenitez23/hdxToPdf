"""
extractor.py - Lee y parsea archivos .hdx de documentación Huawei

Los .hdx de HelpNDoc son archivos compuestos. Estrategia de extracción:
  1. Intentar como ZIP (HelpNDoc moderno empaqueta HTML dentro)
  2. Intentar como HTML directo
  3. Fallback: leer como texto plano

La clase HDXExtractor devuelve un objeto HDXDocument con secciones listas
para renderizar.
"""

import zipfile
import re
from pathlib import Path
from dataclasses import dataclass, field
from bs4 import BeautifulSoup


@dataclass
class Section:
    title: str
    content_html: str
    level: int = 1          # 1 = capítulo, 2 = sección, 3 = subsección
    images: list = field(default_factory=list)


@dataclass
class HDXDocument:
    title: str
    sections: list[Section] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class HDXExtractor:
    def __init__(self, path: Path, verbose: bool = False):
        self.path = path
        self.verbose = verbose

    # ------------------------------------------------------------------
    # Internal logging helpers
    # ------------------------------------------------------------------
    def _log(self, msg: str) -> None:
        """Always-visible milestone log."""
        print(f"  [extract] {msg}")

    def _vlog(self, msg: str) -> None:
        """Verbose-only detail log."""
        if self.verbose:
            print(f"  [extract:v] {msg}")

    def extract(self) -> HDXDocument:
        """Punto de entrada principal. Detecta el formato y extrae."""
        raw = self.path.read_bytes()
        file_size_kb = len(raw) / 1024
        self._log(f"Reading '{self.path.name}' ({file_size_kb:.1f} KB)")

        # Intento 1: ZIP (HelpNDoc moderno)
        if raw[:2] == b'PK':
            self._log("Format detected: ZIP / HelpNDoc")
            self._vlog(f"Magic bytes: {raw[:4].hex()} (PK ZIP signature)")
            return self._extract_from_zip(raw)

        # Intento 2: HTML directo
        if b'<html' in raw[:500].lower() or b'<!doctype' in raw[:200].lower():
            self._log("Format detected: direct HTML")
            self._vlog("HTML signature found in first 500 bytes")
            return self._extract_from_html(raw.decode("utf-8", errors="replace"))

        # Intento 3: texto estructurado
        self._log("Format detected: plain text (fallback)")
        self._vlog(f"Magic bytes: {raw[:4].hex()} — no known signature")
        return self._extract_from_text(raw.decode("utf-8", errors="replace"))

    # ------------------------------------------------------------------
    # Extracción desde ZIP
    # ------------------------------------------------------------------
    def _extract_from_zip(self, raw: bytes) -> HDXDocument:
        import io
        doc = HDXDocument(title=self.path.stem)

        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = zf.namelist()
            self._log(f"ZIP contains {len(names)} file(s) total")
            self._vlog(f"ZIP manifest: {names}")

            # Buscar HTML principal
            html_files = sorted(
                [n for n in names if n.endswith((".html", ".htm", ".xhtml"))],
                key=lambda x: (0 if "index" in x.lower() or "main" in x.lower() else 1, x)
            )
            self._log(f"HTML files found in ZIP: {len(html_files)}")
            self._vlog(f"HTML file list (priority-sorted): {html_files}")

            # Extraer metadatos si hay un archivo de proyecto
            meta_files = [n for n in names if n.endswith((".xml", ".hhp", ".hhc"))]
            self._vlog(f"Metadata files found: {meta_files}")
            for mf in meta_files:
                try:
                    content = zf.read(mf).decode("utf-8", errors="replace")
                    doc.metadata[mf] = content
                    # Intentar extraer título del proyecto
                    title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
                    if title_match:
                        doc.title = title_match.group(1).strip()
                        self._vlog(f"Document title resolved from '{mf}': {doc.title!r}")
                except Exception:
                    pass

            for html_file in html_files:
                try:
                    html_content = zf.read(html_file).decode("utf-8", errors="replace")
                    self._vlog(f"Parsing '{html_file}' ({len(html_content)} chars) ...")
                    sections = self._parse_html_into_sections(html_content, source=html_file)
                    self._log(f"  '{html_file}' -> {len(sections)} section(s)")
                    doc.sections.extend(sections)
                except Exception as e:
                    print(f"  [extract] WARNING: could not read '{html_file}': {e}")

        self._log(f"Extraction complete: {len(doc.sections)} total section(s) from {len(html_files)} HTML file(s)")
        return doc

    # ------------------------------------------------------------------
    # Extracción desde HTML único
    # ------------------------------------------------------------------
    def _extract_from_html(self, html: str) -> HDXDocument:
        doc = HDXDocument(title=self.path.stem)
        self._vlog(f"Parsing direct HTML ({len(html)} chars) ...")
        sections = self._parse_html_into_sections(html, source=self.path.name)

        # Intentar extraer título del <title>
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("title")
        if title_tag:
            doc.title = title_tag.get_text(strip=True)
            self._vlog(f"Document title from <title> tag: {doc.title!r}")

        doc.sections = sections
        self._log(f"Extraction complete: {len(sections)} section(s) from direct HTML")
        return doc

    # ------------------------------------------------------------------
    # Extracción desde texto plano
    # ------------------------------------------------------------------
    def _extract_from_text(self, text: str) -> HDXDocument:
        doc = HDXDocument(title=self.path.stem)
        lines = text.splitlines()
        self._vlog(f"Plain-text extraction: {len(lines)} line(s) to scan")

        current_section = None
        current_content: list[str] = []
        headings_found = 0

        for line in lines:
            # Detectar encabezados por patrones comunes en docs Huawei
            # Ej: "1.2.3 Título", "Chapter 1: xxx", "===Título==="
            heading_match = re.match(
                r'^(\d+(?:\.\d+)*)\s+(.+)$|^(Chapter\s+\d+[:\s].+)$|^(={2,})\s*(.+?)\s*\4$',
                line.strip()
            )

            if heading_match:
                # Guardar sección anterior
                if current_section:
                    current_section.content_html = self._text_to_html("\n".join(current_content))
                    doc.sections.append(current_section)

                # Nueva sección
                title = heading_match.group(2) or heading_match.group(3) or heading_match.group(5)
                numbering = heading_match.group(1) or ""
                level = len(numbering.split(".")) if numbering else 1

                self._vlog(f"Heading found (level {level}): {title!r}")
                current_section = Section(title=title.strip(), content_html="", level=level)
                current_content = []
                headings_found += 1
            else:
                current_content.append(line)

        # Última sección
        if current_section:
            current_section.content_html = self._text_to_html("\n".join(current_content))
            doc.sections.append(current_section)

        # Si no se detectaron secciones, meter todo en una
        if not doc.sections:
            self._log("No headings detected — wrapping entire content as a single section")
            doc.sections.append(Section(
                title=doc.title,
                content_html=self._text_to_html(text),
                level=1
            ))

        self._log(f"Extraction complete: {len(doc.sections)} section(s) from plain text ({headings_found} heading(s) matched)")
        return doc

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _parse_html_into_sections(self, html: str, source: str = "") -> list[Section]:
        """Divide un HTML en secciones basándose en headings h1-h3."""
        soup = BeautifulSoup(html, "html.parser")
        sections: list[Section] = []

        current_title = Path(source).stem
        current_level = 1
        current_elements: list = []
        heading_count = 0

        def flush_section() -> None:
            if current_elements:
                content = "".join(str(el) for el in current_elements)
                sections.append(Section(
                    title=current_title,
                    content_html=content,
                    level=current_level
                ))

        body = soup.find("body") or soup
        top_level_elements = [el for el in body.children if hasattr(el, "name")]
        self._vlog(f"  '{source}': {len(top_level_elements)} top-level element(s) in <body>")

        for elem in body.children:
            if not hasattr(elem, "name"):
                continue

            if elem.name in ("h1", "h2", "h3"):
                flush_section()
                current_title = elem.get_text(strip=True)
                current_level = int(elem.name[1])
                current_elements = []
                heading_count += 1
                self._vlog(f"  Heading <{elem.name}>: {current_title!r}")
            else:
                current_elements.append(elem)

        flush_section()
        self._vlog(f"  '{source}': {heading_count} heading(s) -> {len(sections)} section(s)")
        return sections

    def _text_to_html(self, text: str) -> str:
        """Convierte texto plano a HTML básico."""
        paragraphs = re.split(r'\n{2,}', text.strip())
        html_parts = []
        for p in paragraphs:
            p = p.strip()
            if p:
                # Detectar listas
                if re.match(r'^[-*•]\s', p):
                    items = re.split(r'\n[-*•]\s', p)
                    items_html = "".join(f"<li>{i.strip()}</li>" for i in items if i.strip())
                    html_parts.append(f"<ul>{items_html}</ul>")
                else:
                    escaped = p.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    html_parts.append(f"<p>{escaped}</p>")
        return "\n".join(html_parts)
