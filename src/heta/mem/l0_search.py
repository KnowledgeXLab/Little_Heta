"""Full-text search on L0 raw turns."""

from __future__ import annotations

import sqlite3


def _build_fts_query(query: str) -> str:
    """Build an FTS5 OR query from individual tokens, avoiding syntax errors."""
    import re
    tokens = re.findall(r'[\w一-鿿]+', query)
    if not tokens:
        return '""'
    # quote each token individually to handle special chars, then OR them
    return " OR ".join('"' + t.replace('"', '""') + '"' for t in tokens)


def search_turns(conn: sqlite3.Connection, query: str, top_k: int = 3) -> list[dict]:
    """FTS5 search on raw turn text. Returns matching turns with context."""
    fts_query = _build_fts_query(query)
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
