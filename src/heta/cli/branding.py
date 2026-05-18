"""Shared Little Heta CLI branding and color palette.

Single source of truth for the Heta blue color family. Every CLI command
imports its colors from here so the product keeps one consistent look.
"""

from __future__ import annotations

from heta import __version__

# --- Heta blue palette ---
HETA = "rgb(52,144,220)"       # primary blue — command names, arrows, panel borders
HETA_DARK = "rgb(31,91,156)"   # deep blue — secondary emphasis
CYAN = "rgb(88,196,220)"       # cyan accent — blended / secondary highlights
OK = "rgb(76,196,142)"         # green — success
WARN = "rgb(238,183,74)"       # amber — warnings, prompts
ERR = "rgb(224,108,108)"       # coral red — errors, destructive markers
MUTED = "rgb(126,146,158)"     # slate gray — secondary text

APP_TITLE = "Little Heta"
APP_TAGLINE = "Personal knowledge, memory, and document intelligence CLI"
APP_TEAM = "KnowledgeXLab"


def brand_line() -> str:
    return (
        f"[bold {HETA}]>_ {APP_TITLE}[/] "
        f"[bold {CYAN}]✦[/][bold {OK}]✧[/] "
        f"[{MUTED}]v{__version__}[/]"
    )


def apply_typer_theme() -> None:
    """Re-skin Typer's ``--help`` screen to the Heta blue palette.

    Typer reads these module-level style constants at render time, so
    overriding them once at import keeps every command's help consistent.
    """
    from typer import rich_utils as ru

    ru.STYLE_OPTION = f"bold {HETA}"
    ru.STYLE_SWITCH = f"bold {OK}"
    ru.STYLE_NEGATIVE_OPTION = f"bold {CYAN}"
    ru.STYLE_NEGATIVE_SWITCH = f"bold {ERR}"
    ru.STYLE_METAVAR = f"bold {CYAN}"
    ru.STYLE_METAVAR_SEPARATOR = MUTED
    ru.STYLE_USAGE = HETA
    ru.STYLE_HELPTEXT = MUTED
    ru.STYLE_OPTION_DEFAULT = MUTED
    ru.STYLE_OPTION_ENVVAR = MUTED
    ru.STYLE_REQUIRED_SHORT = ERR
    ru.STYLE_REQUIRED_LONG = ERR
    ru.STYLE_OPTIONS_PANEL_BORDER = HETA
    ru.STYLE_COMMANDS_PANEL_BORDER = HETA
    ru.STYLE_ERRORS_PANEL_BORDER = ERR
    ru.STYLE_COMMANDS_TABLE_FIRST_COLUMN = f"bold {HETA}"
    ru.STYLE_ABORTED = ERR
    ru.STYLE_DEPRECATED = ERR
    ru.STYLE_DEPRECATED_COMMAND = MUTED
    ru.STYLE_ERRORS_SUGGESTION = MUTED


__all__ = [
    "APP_TAGLINE",
    "APP_TEAM",
    "APP_TITLE",
    "CYAN",
    "ERR",
    "HETA",
    "HETA_DARK",
    "MUTED",
    "OK",
    "WARN",
    "apply_typer_theme",
    "brand_line",
]
