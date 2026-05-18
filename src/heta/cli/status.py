"""`heta status` command."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from heta.cli.branding import HETA, MUTED, WARN, brand_line
from heta.config.io import CONFIG_PATH, load_config
from heta.config.schema import HetaConfig, MinerUConfig
from heta.kb import paths

console = Console()

BAR_FULL = "█"
BAR_EMPTY = "░"
BAR_WIDTH = 20


@dataclass(frozen=True)
class StatusSummary:
    llm_provider: str
    mineru: str
    insert_planning: str
    kb_files: int
    wiki_pages: int
    heta_space: Path
    heta_used_bytes: int
    disk_free_bytes: int


def status_command() -> None:
    """Show the current Little Heta status."""
    try:
        config = load_config()
    except Exception as exc:
        console.print(f"[{WARN}]?[/] Failed to read config: {exc}")
        raise typer.Exit(1) from exc

    summary = build_status_summary(config)
    _show_status(summary, config is not None)


def build_status_summary(config: HetaConfig | None, base_dir: Path | None = None) -> StatusSummary:
    heta_space = _heta_space(base_dir)
    disk = shutil.disk_usage(_disk_anchor(heta_space))
    return StatusSummary(
        llm_provider=config.llm.provider if config else "not configured",
        mineru=_mineru_summary(config.mineru) if config else "not configured",
        insert_planning=_enabled_summary(config.insert_planning.enable) if config else "not configured",
        kb_files=_count_files(paths.raw_dir(base_dir)),
        wiki_pages=_count_markdown_pages(paths.pages_dir(base_dir)),
        heta_space=heta_space,
        heta_used_bytes=_directory_size(heta_space),
        disk_free_bytes=disk.free,
    )


def _show_status(summary: StatusSummary, has_config: bool) -> None:
    table = Table.grid(padding=(0, 2))
    table.add_column(style=f"bold {HETA}")
    table.add_column()
    table.add_row("Heta space:", f"{_display_path(summary.heta_space).rstrip('/')}/")
    table.add_row("Model provider:", summary.llm_provider)
    table.add_row("MinerU:", summary.mineru)
    table.add_row("Insert planning:", summary.insert_planning)
    table.add_row("KB files:", str(summary.kb_files))
    table.add_row("Wiki pages:", str(summary.wiki_pages))

    if not has_config:
        table.add_row("Config status:", "missing")

    table.add_row(
        "Heta usage:",
        _heta_usage_bar(summary.heta_used_bytes, summary.disk_free_bytes),
    )

    console.print(
        Panel(
            _status_content(table),
            border_style=HETA,
            padding=(1, 2),
        )
    )


def _mineru_summary(config: MinerUConfig) -> str:
    if not config.enable:
        return "disabled"
    if config.provider == "local":
        return f"local ({config.endpoint})"
    return "cloud"


def _enabled_summary(enable: bool) -> str:
    return "enabled" if enable else "disabled"


def _status_content(table: Table) -> Table:
    layout = Table.grid()
    layout.add_column()
    layout.add_row(brand_line())
    layout.add_row("")
    layout.add_row(table)
    return layout


def _count_files(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(1 for path in directory.rglob("*") if path.is_file())


def _count_markdown_pages(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(1 for path in directory.glob("*.md") if path.is_file())


def _heta_space(base_dir: Path | None) -> Path:
    if base_dir is not None:
        return base_dir
    return CONFIG_PATH.parent


def _disk_anchor(path: Path) -> Path:
    if path.exists():
        return path

    candidate = path
    while not candidate.exists() and candidate.parent != candidate:
        candidate = candidate.parent
    return candidate if candidate.exists() else Path.home()


def _directory_size(directory: Path) -> int:
    if not directory.exists():
        return 0

    total = 0
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        try:
            total += path.stat().st_size
        except OSError:
            continue
    return total


def _heta_usage_bar(used_bytes: int, free_bytes: int) -> str:
    total_available = used_bytes + free_bytes
    if total_available <= 0:
        return f"[{BAR_EMPTY * BAR_WIDTH}] unknown"

    ratio = max(0.0, min(1.0, used_bytes / total_available))
    filled = round(ratio * BAR_WIDTH)
    bar = BAR_FULL * filled + BAR_EMPTY * (BAR_WIDTH - filled)
    percent = round(ratio * 100)
    percent_text = "<1" if used_bytes > 0 and percent == 0 else str(percent)
    return (
        f"[{bar}] {percent_text}% used "
        f"({_format_bytes(used_bytes)} used / {_format_bytes(free_bytes)} free)"
    )


def _format_bytes(value: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024


def _display_path(path: Path) -> str:
    home = Path.home()
    try:
        return f"~/{path.resolve().relative_to(home)}"
    except ValueError:
        return str(path)


__all__ = ["StatusSummary", "build_status_summary", "status_command"]
