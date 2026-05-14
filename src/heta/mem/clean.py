"""Wipe all memory data while preserving the schema."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass
class CleanMemoryResult:
    deleted_sessions: int
    deleted_l0_turns: int
    deleted_l1_episodes: int
    deleted_l2_facts: int
    deleted_kb_insights: int
    deleted_meta: int


def clean_memory(conn: sqlite3.Connection) -> CleanMemoryResult:
    """Delete every row from all memory tables. Schema is preserved."""
    sessions = _count(conn, "session")
    turns = _count(conn, "l0_turn")
    episodes = _count(conn, "l1_episodic")
    facts = _count(conn, "l2_semantic")
    insights = _count(conn, "kb_insight")
    meta = _count(conn, "memory_meta")

    # vec0 and FTS5 virtual tables must be cleared before main tables
    conn.execute("DELETE FROM l2_fact_vec")
    conn.execute("DELETE FROM l1_episode_vec")
    conn.execute("DELETE FROM l0_turn_fts")
    conn.execute("DELETE FROM kb_insight_vec")
    # legacy vec tables (may exist on older DBs)
    for t in ("kb_chunk_vec", "kb_qa_vec"):
        try:
            conn.execute(f"DELETE FROM {t}")
        except Exception:
            pass

    # delete leaf tables first to avoid FK ordering issues
    conn.execute("DELETE FROM kb_insight")
    # legacy tables
    for t in ("kb_qa_chunk", "kb_qa", "kb_chunk", "kb_source"):
        try:
            conn.execute(f"DELETE FROM {t}")
        except Exception:
            pass
    conn.execute("DELETE FROM l2_semantic")
    conn.execute("DELETE FROM l1_episodic")
    conn.execute("DELETE FROM memory_meta")
    conn.execute("DELETE FROM l0_turn")
    conn.execute("DELETE FROM session")
    conn.commit()

    return CleanMemoryResult(
        deleted_sessions=sessions,
        deleted_l0_turns=turns,
        deleted_l1_episodes=episodes,
        deleted_l2_facts=facts,
        deleted_kb_insights=insights,
        deleted_meta=meta,
    )


def _count(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
