"""Write operations, vector search, and conflict handling for l2_semantic."""

from __future__ import annotations

import sqlite3

import sqlite_vec

from heta.mem.models import L2Semantic


def insert_fact(conn: sqlite3.Connection, fact: L2Semantic) -> None:
    conn.execute(
        """INSERT INTO l2_semantic
           (memory_id, subject, predicate, object, object_type,
            fact_text, t_valid_start, t_valid_end, when_text, when_resolved, when_precision)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (fact.memory_id, fact.subject, fact.predicate, fact.object,
         fact.object_type, fact.fact_text, fact.t_valid_start, fact.t_valid_end,
         fact.when_text, fact.when_resolved, fact.when_precision),
    )
    conn.commit()


def insert_fact_embedding(
    conn: sqlite3.Connection, memory_id: str, embedding: list[float]
) -> None:
    conn.execute(
        "INSERT INTO l2_fact_vec (memory_id, embedding) VALUES (?, ?)",
        (memory_id, sqlite_vec.serialize_float32(embedding)),
    )
    conn.commit()


def search_similar_facts(
    conn: sqlite3.Connection,
    embedding: list[float],
    top_k: int = 5,
    exclude_session_id: str | None = None,
) -> list[dict]:
    """Return active facts closest to the given embedding, excluding the current session."""
    if exclude_session_id:
        rows = conn.execute(
            """
            SELECT s.memory_id, s.fact_text, v.distance
            FROM l2_fact_vec v
            JOIN l2_semantic s ON s.memory_id = v.memory_id
            JOIN memory_meta m ON m.memory_id = s.memory_id
            WHERE v.embedding MATCH ? AND k = ?
              AND m.status = 'active'
              AND s.t_valid_end IS NULL
              AND (m.session_id IS NULL OR m.session_id != ?)
            ORDER BY v.distance
            """,
            (sqlite_vec.serialize_float32(embedding), max(1, top_k), exclude_session_id),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT s.memory_id, s.fact_text, v.distance
            FROM l2_fact_vec v
            JOIN l2_semantic s ON s.memory_id = v.memory_id
            JOIN memory_meta m ON m.memory_id = s.memory_id
            WHERE v.embedding MATCH ? AND k = ?
              AND m.status = 'active'
              AND s.t_valid_end IS NULL
            ORDER BY v.distance
            """,
            (sqlite_vec.serialize_float32(embedding), max(1, top_k)),
        ).fetchall()
    return [{"memory_id": r["memory_id"], "fact_text": r["fact_text"], "distance": r["distance"]}
            for r in rows]


def expire_fact(conn: sqlite3.Connection, memory_id: str, t_valid_end: int) -> None:
    conn.execute(
        "UPDATE l2_semantic SET t_valid_end = ? WHERE memory_id = ?",
        (t_valid_end, memory_id),
    )
    conn.commit()
