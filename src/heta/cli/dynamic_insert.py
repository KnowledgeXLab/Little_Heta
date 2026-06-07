"""`heta dynamic-insert` commands."""

from __future__ import annotations

from dataclasses import replace

import typer
from rich.console import Console

from heta.cli.branding import HETA, MUTED, OK, WARN
from heta.config.io import CONFIG_PATH, load_config, save_config
from heta.config.schema import DynamicInsertConfig

console = Console()

app = typer.Typer(
    name="dynamic-insert",
    help="Turn dynamic LLM wiki merging on or off.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@app.command("on")
def dynamic_insert_on() -> None:
    """Enable dynamic LLM wiki merging during insert."""
    _set_dynamic_insert(True)


@app.command("true")
def dynamic_insert_true() -> None:
    """Enable dynamic LLM wiki merging during insert."""
    _set_dynamic_insert(True)


@app.command("off")
def dynamic_insert_off() -> None:
    """Disable dynamic LLM wiki merging during insert."""
    _set_dynamic_insert(False)


@app.command("false")
def dynamic_insert_false() -> None:
    """Disable dynamic LLM wiki merging during insert."""
    _set_dynamic_insert(False)


@app.command("status")
def dynamic_insert_status() -> None:
    """Show whether dynamic LLM wiki merging is enabled."""
    config = _require_config()
    state = "enabled" if config.dynamic_insert.enable else "disabled"
    console.print(f"[{MUTED}]dynamic insert:[/] [bold {HETA}]{state}[/]")


def _set_dynamic_insert(enable: bool) -> None:
    config = _require_config()
    updated = replace(config, dynamic_insert=DynamicInsertConfig(enable=enable))
    save_config(updated)
    state = "enabled" if enable else "disabled"
    console.print(f"[{OK}]✓[/] dynamic insert {state}")


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
