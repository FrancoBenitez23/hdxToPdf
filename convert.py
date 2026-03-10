#!/usr/bin/env python3
"""
hdx2pdf - Convierte archivos .hdx de documentación Huawei a PDF
Uso: python convert.py archivo.hdx [-o salida.pdf] [-v]
"""

import argparse
import sys
import os
import time
from pathlib import Path

from extractor import HDXExtractor
from renderer import PDFRenderer


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convierte archivos .hdx (HelpNDoc/Huawei docs) a PDF",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python convert.py manual.hdx
  python convert.py manual.hdx -o mi_manual.pdf
  python convert.py manual.hdx -o salida/ -v
        """
    )
    parser.add_argument(
        "input",
        help="Archivo .hdx de entrada (o carpeta para batch)"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Archivo PDF de salida (default: mismo nombre que input)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Mostrar detalles del proceso"
    )
    parser.add_argument(
        "--toc",
        action="store_true",
        default=True,
        help="Incluir tabla de contenidos (default: True)"
    )
    parser.add_argument(
        "--no-toc",
        action="store_false",
        dest="toc",
        help="No incluir tabla de contenidos"
    )
    return parser.parse_args()


def resolve_output_path(input_path: Path, output_arg: str | None) -> Path:
    if output_arg is None:
        return input_path.with_suffix(".pdf")

    out = Path(output_arg)
    if out.is_dir():
        return out / input_path.with_suffix(".pdf").name

    # Si no tiene extensión, agregar .pdf
    if out.suffix == "":
        return out.with_suffix(".pdf")

    return out


def convert_file(input_path: Path, output_path: Path, verbose: bool, toc: bool) -> None:
    print(f"[hdx2pdf] Processing: {input_path.name}")
    if verbose:
        print(f"[hdx2pdf] Output path: {output_path}")

    t_start = time.perf_counter()

    # 1. Extract content from .hdx
    print("[hdx2pdf] Step 1/2: Extracting content ...")
    extractor = HDXExtractor(input_path, verbose=verbose)
    doc = extractor.extract()
    t_extract = time.perf_counter()

    section_count = len(doc.sections)
    print(f"[hdx2pdf] Extraction done: {section_count} section(s) found  ({t_extract - t_start:.2f}s)")
    if section_count == 0:
        print("[hdx2pdf] WARNING: No sections detected — the output PDF will be empty")

    # 2. Render to PDF
    print("[hdx2pdf] Step 2/2: Rendering PDF ...")
    renderer = PDFRenderer(doc, verbose=verbose)
    renderer.render(output_path, include_toc=toc)
    t_render = time.perf_counter()

    size_kb = output_path.stat().st_size / 1024
    total_s = t_render - t_start
    print(f"[hdx2pdf] Done: {output_path}  ({size_kb:.1f} KB, {total_s:.2f}s total)")


def main():
    args = parse_args()
    input_path = Path(args.input)

    # Validaciones
    if not input_path.exists():
        print(f"❌ Error: No se encontró el archivo '{input_path}'", file=sys.stderr)
        sys.exit(1)

    # Modo batch: si se pasa una carpeta
    if input_path.is_dir():
        hdx_files = list(input_path.glob("*.hdx"))
        if not hdx_files:
            print(f"❌ No se encontraron archivos .hdx en '{input_path}'", file=sys.stderr)
            sys.exit(1)

        print(f"🗂  Modo batch: {len(hdx_files)} archivos encontrados")
        out_dir = Path(args.output) if args.output else input_path / "output"
        out_dir.mkdir(exist_ok=True)

        errors = []
        for f in hdx_files:
            out = out_dir / f.with_suffix(".pdf").name
            try:
                convert_file(f, out, args.verbose, args.toc)
            except Exception as e:
                print(f"  ⚠️  Error en {f.name}: {e}", file=sys.stderr)
                errors.append(f.name)

        print(f"\n{'✅ Batch completo' if not errors else f'⚠️  Completado con {len(errors)} errores'}")
        if errors:
            print("  Fallidos:", ", ".join(errors))
        return

    # Modo archivo único
    if input_path.suffix.lower() != ".hdx":
        print(f"⚠️  Advertencia: el archivo no tiene extensión .hdx", file=sys.stderr)

    output_path = resolve_output_path(input_path, args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        convert_file(input_path, output_path, args.verbose, args.toc)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
