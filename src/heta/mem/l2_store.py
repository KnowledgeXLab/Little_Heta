"""Write operations and conflict handling for the l2_semantic table."""

from __future__ import annotations

import sqlite3

from heta.mem.models import L2Semantic


def insert_fact(conn: sqlite3.Connection, fact: L2Semantic) -> None:
    conn.execute(
        """INSERT INTO l2_semantic
           (memory_id, subject, predicate, object, object_type, t_valid_start, t_valid_end)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (fact.memory_id, fact.subject, fact.predicate, fact.object,
         fact.object_type, fact.t_valid_start, fact.t_valid_end),
    )
    conn.commit()


def find_active_conflicts(
    conn: sqlite3.Connection, subject: str, predicate: str
) -> list[str]:
    """Return memory_ids of active facts with the same subject+predicate."""
    rows = conn.execute(
        "SELECT memory_id FROM l2_semantic "
        "WHERE subject = ? AND predicate = ? AND t_valid_end IS NULL",
        (subject, predicate),
    ).fetchall()
    return [row["memory_id"] for row in rows]


def expire_fact(conn: sqlite3.Connection, memory_id: str, t_valid_end: int) -> None:
    conn.execute(
        "UPDATE l2_semantic SET t_valid_end = ? WHERE memory_id = ?",
        (t_valid_end, memory_id),
    )
    conn.commit()
