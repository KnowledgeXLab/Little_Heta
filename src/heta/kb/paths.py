"""Runtime path helpers for Little Heta KB."""

from __future__ import annotations

from pathlib import Path

HETA_HOME = Path.home() / ".heta"


def workspace_root(base_dir: Path | None = None) -> Path:
    if base_dir is None:
        return HETA_HOME / "workspace" / "kb"
    root = base_dir
    return root / "workspace" / "kb"


def raw_dir(base_dir: Path | None = None) -> Path:
    return workspace_root(base_dir) / "raw"


def wiki_dir(base_dir: Path | None = None) -> Path:
    return workspace_root(base_dir) / "wiki"


def pages_dir(base_dir: Path | None = None) -> Path:
    return wiki_dir(base_dir) / "pages"


def index_path(base_dir: Path | None = None) -> Path:
    return wiki_dir(base_dir) / "index.md"


def log_path(base_dir: Path | None = None) -> Path:
    return wiki_dir(base_dir) / "log.md"


def worktrees_dir(base_dir: Path | None = None) -> Path:
    return workspace_root(base_dir) / ".worktrees"


def vector_db_path(base_dir: Path | None = None) -> Path:
    return workspace_root(base_dir) / "db" / "wiki_vectors.sqlite3"
