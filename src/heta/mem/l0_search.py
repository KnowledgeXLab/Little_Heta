"""Full-text search on L0 raw turns."""

from __future__ import annotations

import sqlite3


def search_turns(conn: sqlite3.Connection, query: str, top_k: int = 3) -> list[dict]:
    """FTS5 search on raw turn text. Returns matching turns with context."""
    # wrap in quotes for phrase search to avoid FTS5 syntax errors on
    # punctuation and special characters
    fts_query = '"' + query.replace('"', '""') + '"'
    try:
        rows = conn.execute(
            """
            SELECT session_id, turn_index, text_content, rank
            FROM l0_turn_fts
            WHERE text_content MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, top_k),
        ).fetchall()
    except Exception:
        rows = []

    results = []
    for r in rows:
        score = 1.0 / (1.0 + abs(float(r["rank"])))
        results.append({
            "session_id": r["session_id"],
            "turn_index": r["turn_index"],
            "text_content": r["text_content"],
            "score": score,
        })
    return results
