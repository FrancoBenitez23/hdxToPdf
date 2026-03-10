from contextlib import contextmanager

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


def print_error(msg: str) -> None:
    console.print(f"[red]✖[/red] {msg}")


def print_success(msg: str) -> None:
    console.print(f"[green]✔[/green] {msg}")


def print_info(msg: str) -> None:
    console.print(f"[blue]ℹ[/blue] {msg}")


def print_warn(msg: str) -> None:
    console.print(f"[yellow]⚠[/yellow] {msg}")


def print_welcome(title: str, subtitle: str = "") -> None:
    content = f"[bold]{title}[/bold]"
    if subtitle:
        content += f"\n[dim]{subtitle}[/dim]"
    console.print(Panel(content, style="cyan", border_style="cyan"))


def print_table(title: str, columns: list[str], rows: list[dict]) -> None:
    table = Table(title=title, border_style="dim")
    for col in columns:
        table.add_column(col, style="white")
    for row in rows:
        table.add_row(*[str(row.get(col, "")) for col in columns])
    console.print(table)


@contextmanager
def spinner(label: str):
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(label)
        yield
