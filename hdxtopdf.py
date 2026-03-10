#!/usr/bin/env python3
"""hdx2pdf — Converts Huawei .hdx documentation files to PDF."""

import sys
from argparse import ArgumentParser
from pathlib import Path

from commands.convert_cmd import run_batch, run_convert
from exceptions import PromptAbortedError
from ui.output import print_error, print_info, print_success, print_warn, spinner


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="hdx2pdf", description="Convert Huawei .hdx files to PDF")
    subparsers = parser.add_subparsers(dest="command")

    # convert subcommand
    sub_convert = subparsers.add_parser("convert", help="Convert a single .hdx file")
    sub_convert.add_argument("input", help="Input .hdx file")
    sub_convert.add_argument("-o", "--output", default=None, help="Output PDF path or directory")
    sub_convert.add_argument("-v", "--verbose", action="store_true", help="Show processing details")
    sub_convert.add_argument("--no-toc", action="store_false", dest="toc", help="Exclude table of contents")

    # batch subcommand
    sub_batch = subparsers.add_parser("batch", help="Convert all .hdx files in a folder")
    sub_batch.add_argument("input", help="Input folder")
    sub_batch.add_argument("-o", "--output", default=None, help="Output directory")
    sub_batch.add_argument("-v", "--verbose", action="store_true", help="Show processing details")
    sub_batch.add_argument("--no-toc", action="store_false", dest="toc", help="Exclude table of contents")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "convert":
            inp = Path(args.input)
            if not inp.exists():
                print_error(f"File not found: '{args.input}'")
                sys.exit(1)
            if inp.suffix.lower() != ".hdx":
                print_warn("File does not have .hdx extension")

            print_info(f"Converting: {inp.name}")

            if args.verbose:
                result = run_convert(args.input, args.output, args.verbose, args.toc)
            else:
                with spinner("Rendering PDF..."):
                    result = run_convert(args.input, args.output, args.verbose, args.toc)

            if result.error:
                print_error(result.error)
                sys.exit(1)
            if result.section_count == 0:
                print_warn("No sections detected — PDF may be empty")
            print_success(
                f"Done → {result.output_path}  "
                f"({result.size_kb:.1f} KB, {result.elapsed_s:.2f}s, {result.section_count} sections)"
            )

        elif args.command == "batch":
            inp = Path(args.input)
            if not inp.exists() or not inp.is_dir():
                print_error(f"Directory not found: '{args.input}'")
                sys.exit(1)

            print_info(f"Batch converting: {inp}")
            with spinner("Converting files..."):
                result = run_batch(args.input, args.output, args.verbose, args.toc)

            if result.error:
                print_error(result.error)
                sys.exit(1)
            elif result.failed:
                print_warn(
                    f"Completed with errors — {len(result.converted)} converted, "
                    f"{len(result.failed)} failed ({result.elapsed_s:.2f}s)"
                )
                print_error("Failed: " + ", ".join(result.failed))
            else:
                print_success(f"Batch done — {len(result.converted)} file(s) converted ({result.elapsed_s:.2f}s)")

        else:
            # No subcommand → interactive mode
            from prompts.interactive import start_interactive
            start_interactive()

    except PromptAbortedError:
        pass
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
