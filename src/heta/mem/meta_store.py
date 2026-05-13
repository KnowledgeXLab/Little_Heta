"""CRUD operations for the memory_meta table."""

from __future__ import annotations

import sqlite3

from heta.mem.models import MemoryMeta


def insert_meta(conn: sqlite3.Connection, meta: MemoryMeta) -> None:
    conn.execute(
        """INSERT INTO memory_meta
           (memory_id, memory_type, session_id, origin, kb_uid, status,
            deprecated_by, recency_score, access_freq, user_emphasis,
            importance, confidence, created_at, last_access_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (meta.memory_id, meta.memory_type, meta.session_id, meta.origin,
         meta.kb_uid, meta.status, meta.deprecated_by, meta.recency_score,
         meta.access_freq, meta.user_emphasis, meta.importance,
         meta.confidence, meta.created_at, meta.last_access_at),
    )
    conn.commit()


def deprecate(conn: sqlite3.Connection, memory_id: str, deprecated_by: str) -> None:
    conn.execute(
        "UPDATE memory_meta SET status = 'deprecated', deprecated_by = ? WHERE memory_id = ?",
        (deprecated_by, memory_id),
    )
    conn.commit()
