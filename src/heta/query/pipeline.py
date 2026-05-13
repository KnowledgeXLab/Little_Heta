"""Pipeline entry point for Little Heta read-only wiki query."""

from __future__ import annotations

from pathlib import Path

from heta.config.schema import HetaConfig
from heta.kb import paths
from heta.query.agent import run_query_agent
from heta.query.models import QueryResult


def run_wiki_query(
    question: str,
    config: HetaConfig,
    *,
    top_k: int = 5,
    extra_context: str | None = None,
    base_dir: Path | None = None,
) -> QueryResult:
    if not question.strip():
        raise ValueError("question must not be empty")
    if not paths.index_path(base_dir).exists():
        raise FileNotFoundError("Little Heta wiki is not initialized. Run `heta insert` first.")
    return run_query_agent(
        question=question.strip(),
        config=config,
        base_dir=base_dir,
        top_k=top_k,
        extra_context=extra_context,
    )

