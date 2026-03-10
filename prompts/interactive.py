from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from commands.convert_cmd import run_batch, run_convert
from exceptions import PromptAbortedError
from ui.output import (
    print_error,
    print_info,
    print_success,
    print_warn,
    print_welcome,
    spinner,
)


def start_interactive() -> None:
    print_welcome("hdx2pdf", "Huawei .hdx → PDF converter")
    while True:
        try:
            action = inquirer.select(
                message="Select an action:",
                choices=[
                    Choice(value="convert", name="Convert file"),
                    Choice(value="batch", name="Batch convert folder"),
                    Choice(value=None, name="Exit"),
                ],
            ).execute()

            if action is None:
                break
            elif action == "convert":
                _flow_convert()
            elif action == "batch":
                _flow_batch()

        except PromptAbortedError:
            break
        # InquirerPy can raise KeyboardInterrupt directly from the main menu
        # prompt before any sub-flow has had a chance to wrap it as PromptAbortedError.
        except KeyboardInterrupt:
            break


def _flow_convert() -> None:
    try:
        input_path = inquirer.filepath(
            message="Select .hdx file:",
            validate=lambda p: p.endswith(".hdx") or "Must be a .hdx file",
        ).execute()

        output = inquirer.text(
            message="Output path (leave empty for auto):",
            default="",
        ).execute() or None

        toc = inquirer.confirm(message="Include table of contents?", default=True).execute()
        verbose = inquirer.confirm(message="Verbose output?", default=False).execute()

        print_info(f"  File   : {input_path}")
        print_info(f"  Output : {output or 'auto'}")
        print_info(f"  TOC    : {'yes' if toc else 'no'}  |  Verbose: {'yes' if verbose else 'no'}")

        action = inquirer.select(
            message="Ready to convert:",
            choices=[
                Choice(value="convert", name="Convert"),
                Choice(value="back", name="Cancel"),
            ],
        ).execute()

        if action == "back":
            return

        print_info(f"Converting {input_path} ...")

        if verbose:
            result = run_convert(input_path, output, verbose, toc)
        else:
            with spinner("Rendering PDF..."):
                result = run_convert(input_path, output, verbose, toc)

        if result.error:
            print_error(result.error)
        else:
            if result.section_count == 0:
                print_warn("No sections detected — PDF may be empty")
            print_success(
                f"Done → {result.output_path}  "
                f"({result.size_kb:.1f} KB, {result.elapsed_s:.2f}s, {result.section_count} sections)"
            )
    except KeyboardInterrupt:
        raise PromptAbortedError("convert")


def _flow_batch() -> None:
    try:
        input_dir = inquirer.filepath(
            message="Select folder with .hdx files:",
            only_directories=True,
        ).execute()

        output = inquirer.text(
            message="Output directory (leave empty for auto):",
            default="",
        ).execute() or None

        toc = inquirer.confirm(message="Include table of contents?", default=True).execute()
        verbose = inquirer.confirm(message="Verbose output?", default=False).execute()

        print_info(f"  Folder : {input_dir}")
        print_info(f"  Output : {output or 'auto'}")
        print_info(f"  TOC    : {'yes' if toc else 'no'}  |  Verbose: {'yes' if verbose else 'no'}")

        action = inquirer.select(
            message="Ready to convert:",
            choices=[
                Choice(value="convert", name="Convert"),
                Choice(value="back", name="Cancel"),
            ],
        ).execute()

        if action == "back":
            return

        print_info(f"Batch converting: {input_dir} ...")

        if verbose:
            result = run_batch(input_dir, output, verbose=verbose, toc=toc)
        else:
            with spinner("Converting files..."):
                result = run_batch(input_dir, output, verbose=verbose, toc=toc)

        if result.error:
            print_error(result.error)
        elif result.failed:
            print_warn(
                f"Completed with errors — {len(result.converted)} converted, "
                f"{len(result.failed)} failed ({result.elapsed_s:.2f}s)"
            )
            print_error("Failed: " + ", ".join(result.failed))
        else:
            print_success(f"Batch done — {len(result.converted)} file(s) converted ({result.elapsed_s:.2f}s)")
    except KeyboardInterrupt:
        raise PromptAbortedError("batch")
