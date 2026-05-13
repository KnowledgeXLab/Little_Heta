"""Temporary worktree management for Little Heta KB."""

from __future__ import annotations

import shutil
from pathlib import Path

from heta.kb import paths
from heta.kb.store import ensure_wiki_layout


def create_working_copy(task_id: str, base_dir: Path | None = None) -> Path:
    ensure_wiki_layout(base_dir)
    work_root = paths.worktrees_dir(base_dir) / task_id
    wiki_copy = work_root / "wiki"
    if work_root.exists():
        shutil.rmtree(work_root)
    work_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(paths.wiki_dir(base_dir), wiki_copy, ignore=shutil.ignore_patterns(".git"))
    return wiki_copy


def promote_working_copy(task_id: str, base_dir: Path | None = None) -> None:
    wiki_copy = paths.worktrees_dir(base_dir) / task_id / "wiki"
    if not wiki_copy.exists():
        raise FileNotFoundError(f"working copy does not exist: {task_id}")

    wiki = paths.wiki_dir(base_dir)
    for child in wiki.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    for source in wiki_copy.iterdir():
        target = wiki / source.name
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)


def cleanup_working_copy(task_id: str, base_dir: Path | None = None) -> None:
    work_root = paths.worktrees_dir(base_dir) / task_id
    if work_root.exists():
        shutil.rmtree(work_root)

