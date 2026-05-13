"""Vector search on L1 episodic memory summaries."""

from __future__ import annotations

import sqlite3

import sqlite_vec


def search_episodes(conn: sqlite3.Connection, embedding: list[float], top_k: int = 3) -> list[dict]:
    """Return active episodes closest to the query embedding."""
    rows = conn.execute(
        """
        SELECT e.memory_id, e.who, e.what, e.where_loc, e.when_text, e.why, e.summary, v.distance
        FROM l1_episode_vec v
        JOIN l1_episodic e ON e.memory_id = v.memory_id
        JOIN memory_meta m ON m.memory_id = e.memory_id
        WHERE v.embedding MATCH ? AND k = ?
          AND m.status = 'active'
        ORDER BY v.distance
        """,
        (sqlite_vec.serialize_float32(embedding), max(1, top_k)),
    ).fetchall()

    return [
        {
            "memory_id": r["memory_id"],
            "who": r["who"],
            "what": r["what"],
            "where_loc": r["where_loc"],
            "when_text": r["when_text"],
            "why": r["why"],
            "summary": r["summary"],
            "score": 1.0 / (1.0 + float(r["distance"])),
        }
        for r in rows
    ]
