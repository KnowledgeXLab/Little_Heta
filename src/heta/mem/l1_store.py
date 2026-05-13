"""Write operations for the l1_episodic table."""

from __future__ import annotations

import sqlite3

from heta.mem.models import L1Episodic


def insert_episodic(conn: sqlite3.Connection, episode: L1Episodic) -> None:
    conn.execute(
        """INSERT INTO l1_episodic
           (memory_id, who, what, where_loc,
            when_ts, when_text, when_resolved, when_precision, why, summary)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (episode.memory_id, episode.who, episode.what, episode.where_loc,
         episode.when_ts, episode.when_text, episode.when_resolved,
         episode.when_precision, episode.why, episode.summary),
    )
    conn.commit()


def insert_episode_embedding(
    conn: sqlite3.Connection, memory_id: str, embedding: list[float]
) -> None:
    import sqlite_vec
    conn.execute(
        "INSERT INTO l1_episode_vec (memory_id, embedding) VALUES (?, ?)",
        (memory_id, sqlite_vec.serialize_float32(embedding)),
    )
    conn.commit()
