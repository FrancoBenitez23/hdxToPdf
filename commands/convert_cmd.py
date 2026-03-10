import time
from dataclasses import dataclass, field
from pathlib import Path

from commands.functions.extractor import HDXExtractor
from commands.functions.renderer import PDFRenderer


@dataclass
class ConvertResult:
    output_path: str | None = None
    section_count: int = 0
    size_kb: float = 0.0
    elapsed_s: float = 0.0
    error: str | None = None


@dataclass
class BatchResult:
    converted: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    error: str | None = None


def _resolve_output(input_path: Path, output_arg: str | None) -> Path:
    if output_arg is None:
        return input_path.with_suffix(".pdf")
    out = Path(output_arg)
    if out.is_dir():
        return out / input_path.with_suffix(".pdf").name
    if out.suffix == "":
        return out.with_suffix(".pdf")
    return out


def run_convert(
    input_path: str,
    output: str | None = None,
    verbose: bool = False,
    toc: bool = True,
) -> ConvertResult:
    try:
        inp = Path(input_path)
        if not inp.exists():
            return ConvertResult(error=f"File not found: '{input_path}'")

        out = _resolve_output(inp, output)
        out.parent.mkdir(parents=True, exist_ok=True)

        t_start = time.perf_counter()
        doc = HDXExtractor(inp, verbose=verbose).extract()
        PDFRenderer(doc, verbose=verbose).render(out, include_toc=toc)
        elapsed = time.perf_counter() - t_start

        return ConvertResult(
            output_path=str(out),
            section_count=len(doc.sections),
            size_kb=out.stat().st_size / 1024,
            elapsed_s=elapsed,
        )
    except Exception as e:
        return ConvertResult(error=str(e))


def run_batch(
    input_dir: str,
    output: str | None = None,
    verbose: bool = False,
    toc: bool = True,
) -> BatchResult:
    try:
        inp = Path(input_dir)
        hdx_files = list(inp.glob("*.hdx"))
        if not hdx_files:
            return BatchResult(error=f"No .hdx files found in '{input_dir}'")

        out_dir = Path(output) if output else inp / "output"
        out_dir.mkdir(exist_ok=True)

        t_start = time.perf_counter()
        converted, failed = [], []

        for f in hdx_files:
            result = run_convert(str(f), str(out_dir / f.with_suffix(".pdf").name), verbose, toc)
            (failed if result.error else converted).append(f.name)

        return BatchResult(
            converted=converted,
            failed=failed,
            elapsed_s=time.perf_counter() - t_start,
        )
    except Exception as e:
        return BatchResult(error=str(e))
