"""`heta vector` commands."""

from __future__ import annotations

from dataclasses import replace

import typer
from rich.console import Console

from heta.cli.branding import HETA, MUTED, OK, WARN
from heta.config.io import CONFIG_PATH, load_config, save_config
from heta.config.schema import VectorIndexConfig
from heta.kb import paths
from heta.kb.models import FileChange
from heta.kb.vector_index import sync_wiki_vector_index

console = Console()

app = typer.Typer(
    name="vector",
    help="Turn document search vector indexing on or off.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@app.command("on")
def vector_on() -> None:
    """Enable wiki vector indexing after insert."""
    _set_vector_index(True)


@app.command("off")
def vector_off() -> None:
    """Disable wiki vector indexing after insert."""
    _set_vector_index(False)


@app.command("status")
def vector_status() -> None:
    """Show whether wiki vector indexing is enabled."""
    config = _require_config()
    state = "enabled" if config.vector_index.enable else "disabled"
    console.print(f"[{MUTED}]vector index:[/] [bold {HETA}]{state}[/]")


@app.command("sync")
def vector_sync() -> None:
    """Rebuild the wiki vector index from current wiki pages."""
    config = _require_config()
    page_files = sorted(paths.pages_dir().glob("*.md"))
    changes = [
        FileChange("updated", page.stem, str(page.relative_to(paths.wiki_dir())))
        for page in page_files
    ]
    try:
        sync_wiki_vector_index(changes=changes, config=config)
    except Exception as exc:
        console.print(f"[{WARN}]?[/] Vector index sync failed: {exc}")
        raise typer.Exit(1) from exc
    console.print(f"[{OK}]✓[/] vector index synced ({len(changes)} pages)")


def _set_vector_index(enable: bool) -> None:
    config = _require_config()
    updated = replace(config, vector_index=VectorIndexConfig(enable=enable))
    save_config(updated)
    state = "enabled" if enable else "disabled"
    console.print(f"[{OK}]✓[/] vector index {state}")


def _require_config():
    try:
        config = load_config()
    except Exception as exc:
        console.print(f"[{WARN}]?[/] Failed to read config: {exc}")
        raise typer.Exit(1) from exc
    if config is None:
        console.print(f"[{WARN}]?[/] Little Heta is not initialized.")
        console.print(f"[{MUTED}]  Missing config:[/] {CONFIG_PATH}")
        raise typer.Exit(1)
    return config


__all__ = ["app"]
