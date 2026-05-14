"""CRUD and search operations for kb_insight."""

from __future__ import annotations

import sqlite3

import sqlite_vec

from heta.mem.models import KBInsight


def insert_kb_insight(conn: sqlite3.Connection, insight: KBInsight) -> None:
    conn.execute(
        """INSERT INTO kb_insight
               (memory_id, insight, question, source_path, wiki_id, heading_path, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (insight.memory_id, insight.insight, insight.question, insight.source_path,
         insight.wiki_id, insight.heading_path, insight.created_at),
    )


def insert_insight_embedding(
    conn: sqlite3.Connection, memory_id: str, embedding: list[float]
) -> None:
    conn.execute(
        "INSERT INTO kb_insight_vec (memory_id, embedding) VALUES (?, ?)",
        (memory_id, sqlite_vec.serialize_float32(embedding)),
    )


def search_kb_insights(
    conn: sqlite3.Connection,
    embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    rows = conn.execute(
        """SELECT i.memory_id, i.insight, i.source_path, v.distance
           FROM kb_insight_vec v
           JOIN kb_insight i ON i.memory_id = v.memory_id
           JOIN memory_meta m ON m.memory_id = i.memory_id
           WHERE v.embedding MATCH ? AND k = ?
             AND m.status = 'active'
           ORDER BY v.distance""",
        (sqlite_vec.serialize_float32(embedding), top_k),
    ).fetchall()
    return [
        {
            "memory_id": r["memory_id"],
            "insight": r["insight"],
            "source_path": r["source_path"],
            "score": 1.0 / (1.0 + float(r["distance"])),
        }
        for r in rows
    ]
