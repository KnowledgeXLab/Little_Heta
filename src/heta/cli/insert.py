"""`heta insert` command."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn
from rich.table import Table

from heta.cli.branding import HETA, MUTED, OK, WARN
from heta.config.io import CONFIG_PATH, load_config
from heta.kb import paths
from heta.kb.discovery import collect_insert_files, supported_extensions
from heta.kb.insert import insert_paths
from heta.kb.models import InsertProgress
from heta.kb.pdf_plan import PDF_PAGE_THRESHOLD, estimate_pdf_pages

console = Console()


def insert_command(
    targets: list[Path] = typer.Argument(
        None,
        help="File or directory paths to insert. Defaults to the current directory.",
    ),
) -> None:
    """Add files to your knowledge base."""
    config = load_config()
    if config is None:
        console.print(f"[{WARN}]?[/] Little Heta is not initialized.")
        console.print(f"[{MUTED}]  Missing config:[/] {CONFIG_PATH}")
        console.print(f"[{MUTED}]  Next:[/] [bold {HETA}]heta init[/]")
        raise typer.Exit(1)

    try:
        files = collect_insert_files(targets or [], config)
    except Exception as exc:
        console.print(f"[{WARN}]?[/] {exc}")
        raise typer.Exit(1) from exc

    if not files:
        extensions = ", ".join(sorted(supported_extensions(config)))
        console.print(f"[{WARN}]?[/] No supported files found.")
        console.print(f"[{MUTED}]  Supported:[/] {extensions}")
        raise typer.Exit(1)

    pdf_planning = config.insert_planning.enable
    _show_plan(files, config, pdf_planning=pdf_planning)

    try:
        with _insert_progress() as progress:
            task_id = progress.add_task("preparing files", total=100, completed=1)

            def on_progress(event: InsertProgress) -> None:
                progress.update(task_id, completed=event.percent, description=_progress_description(event))

            result = insert_paths(
                targets or [],
                config,
                enable_pdf_planning=pdf_planning,
                on_progress=on_progress,
            )
    except KeyboardInterrupt:
        console.print(f"\n[{WARN}]Insert cancelled. Rolled back partial changes.[/]")
        raise typer.Exit(130) from None
    except Exception as exc:
        console.print(f"[{WARN}]?[/] Insert failed. Rolled back partial changes.")
        console.print(f"[{MUTED}]  Reason:[/] {exc}")
        raise typer.Exit(1) from exc

    _show_result(result)


def _show_plan(files: list[Path], config, *, pdf_planning: bool) -> None:
    table = Table.grid(padding=(0, 2))
    table.add_column(style=f"bold {HETA}")
    table.add_column()
    table.add_row("files", str(len(files)))
    table.add_row("mode", "dynamic" if config.dynamic_insert.enable else "static")
    table.add_row("mineru", "enabled" if config.mineru.enable else "disabled")
    table.add_row("pdf planning", "enabled" if pdf_planning else "disabled")
    table.add_row("workspace", str(paths.workspace_root()))

    console.print(
        Panel(
            table,
            title="insert",
            border_style=HETA,
            padding=(1, 2),
        )
    )

    console.print(f"[{MUTED}]Files:[/]")
    for file in files:
        suffix = ""
        if file.suffix.lower() == ".pdf" and pdf_planning:
            suffix = _pdf_plan_hint(file)
        console.print(f"  [{HETA}]→[/] {file}{suffix}")


def _show_result(result) -> None:
    console.print()
    console.print(f"[{OK}]✓[/] Insert completed.")

    if result.added:
        console.print("\nAdded pages:")
        for change in result.added:
            console.print(f"[{OK}]+[/] {change.title} [{MUTED}]({_absolute_page_path(change.path)})[/]")

    if result.updated:
        console.print("\nUpdated pages:")
        for change in result.updated:
            console.print(f"[{WARN}]~[/] {change.title} [{MUTED}]({_absolute_page_path(change.path)})[/]")

    if result.deleted:
        console.print("\nDeleted pages:")
        for change in result.deleted:
            console.print(f"[red]-[/] {change.title} [{MUTED}]({_absolute_page_path(change.path)})[/]")

    if result.commit_id:
        console.print(f"\n[{MUTED}]wiki commit:[/] [bold {HETA}]{result.commit_id}[/]")
    else:
        console.print(f"\n[{MUTED}]wiki commit:[/] no changes")

    if result.planned_pdf_parts:
        console.print(f"[{MUTED}]pdf parts:[/] {result.planned_pdf_parts}")

    if result.invalidated_memories:
        console.print(f"[{MUTED}]invalidated memories:[/] {result.invalidated_memories}")

    if result.vector_index_error:
        console.print(f"[{WARN}]![/] Vector index sync failed; wiki pages were still committed.")
        console.print(f"[{MUTED}]  Reason:[/] {result.vector_index_error}")
        console.print(f"[{MUTED}]  Next:[/] rerun [bold {HETA}]heta vector sync[/] after fixing the issue.")

    if result.skipped_documents:
        console.print(f"\n[{WARN}]Documents not organized into wiki pages:[/]")
        for source_name in result.skipped_documents:
            console.print(f"[{WARN}]![/] {source_name}")


def _insert_progress() -> Progress:
    return Progress(
        TextColumn(f"[bold {HETA}]heta insert[/]"),
        BarColumn(bar_width=28, complete_style=HETA, finished_style=OK),
        TaskProgressColumn(),
        TextColumn("[dim]{task.description}[/]"),
        console=console,
    )


def _progress_description(event: InsertProgress) -> str:
    if event.phase == "prepare":
        return event.label
    if event.phase == "merge":
        return f"merging {event.current}/{event.total} · {event.label}"
    if event.phase == "finalize":
        return "finalizing wiki, vector index, and commit"
    if event.phase == "done":
        return "done"
    return event.label


def _absolute_page_path(relative_path: str) -> str:
    return str((paths.wiki_dir() / relative_path).resolve())


def _pdf_plan_hint(file: Path) -> str:
    try:
        pages = estimate_pdf_pages(file)
    except Exception:
        return f" [{WARN}](page count unavailable)[/]"
    if pages > PDF_PAGE_THRESHOLD:
        return f" [{HETA}]({pages} pages, will split)[/]"
    return f" [{MUTED}]({pages} pages)[/]"
