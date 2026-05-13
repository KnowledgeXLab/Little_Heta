"""Write operations for the l0_turn table."""

from __future__ import annotations

import sqlite3

from heta.mem.models import L0Turn


def insert_turn(conn: sqlite3.Connection, turn: L0Turn) -> None:
    conn.execute(
        "INSERT INTO l0_turn (session_id, turn_index, role, modality, text_content, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (turn.session_id, turn.turn_index, turn.role,
         turn.modality, turn.text_content, turn.created_at),
    )
    conn.execute(
        "INSERT INTO l0_turn_fts (session_id, turn_index, text_content) VALUES (?, ?, ?)",
        (turn.session_id, turn.turn_index, turn.text_content),
    )
    conn.commit()
