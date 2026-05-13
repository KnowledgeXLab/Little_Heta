"""CRUD operations for the session table."""

from __future__ import annotations

import sqlite3

from heta.mem.models import Session


def create_session(conn: sqlite3.Connection, session: Session) -> None:
    conn.execute(
        "INSERT INTO session (session_id, started_at, ended_at, consolidated, consolidated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (session.session_id, session.started_at, session.ended_at,
         session.consolidated, session.consolidated_at),
    )
    conn.commit()


def close_session(conn: sqlite3.Connection, session_id: str, ended_at: int) -> None:
    conn.execute(
        "UPDATE session SET ended_at = ? WHERE session_id = ?",
        (ended_at, session_id),
    )
    conn.commit()
