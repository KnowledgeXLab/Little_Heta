"""Write operations for the l1_episodic table."""

from __future__ import annotations

import sqlite3

from heta.mem.models import L1Episodic


def insert_episodic(conn: sqlite3.Connection, episode: L1Episodic) -> None:
    conn.execute(
        """INSERT INTO l1_episodic
           (memory_id, who, what, where_loc, when_ts, when_text, why, summary)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (episode.memory_id, episode.who, episode.what, episode.where_loc,
         episode.when_ts, episode.when_text, episode.why, episode.summary),
    )
    conn.commit()
