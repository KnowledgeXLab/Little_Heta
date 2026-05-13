"""SQLite connection factory and schema initialisation."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def get_connection(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS session (
            session_id      TEXT PRIMARY KEY,
            started_at      INTEGER NOT NULL,
            ended_at        INTEGER,
            consolidated    INTEGER NOT NULL DEFAULT 0,
            consolidated_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS l0_turn (
            session_id   TEXT    NOT NULL REFERENCES session(session_id),
            turn_index   INTEGER NOT NULL,
            role         TEXT    NOT NULL,
            modality     TEXT    NOT NULL DEFAULT 'text',
            text_content TEXT    NOT NULL,
            created_at   INTEGER NOT NULL,
            UNIQUE(session_id, turn_index)
        );

        CREATE TABLE IF NOT EXISTS memory_meta (
            memory_id      TEXT    PRIMARY KEY,
            memory_type    TEXT    NOT NULL,
            session_id     TEXT    REFERENCES session(session_id),
            origin         TEXT    NOT NULL,
            kb_uid         TEXT,
            status         TEXT    NOT NULL DEFAULT 'active',
            deprecated_by  TEXT    REFERENCES memory_meta(memory_id),
            recency_score  REAL    NOT NULL DEFAULT 1.0,
            access_freq    INTEGER NOT NULL DEFAULT 0,
            user_emphasis  REAL    NOT NULL DEFAULT 0.0,
            importance     REAL    NOT NULL DEFAULT 0.5,
            confidence     REAL    NOT NULL DEFAULT 0.9,
            created_at     INTEGER NOT NULL,
            last_access_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS l1_episodic (
            memory_id  TEXT PRIMARY KEY REFERENCES memory_meta(memory_id) ON DELETE CASCADE,
            who        TEXT NOT NULL,
            what       TEXT NOT NULL,
            where_loc  TEXT,
            when_ts    INTEGER,
            when_text  TEXT,
            why        TEXT,
            summary    TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_l1_when ON l1_episodic(when_ts);

        CREATE TABLE IF NOT EXISTS l2_semantic (
            memory_id     TEXT    PRIMARY KEY REFERENCES memory_meta(memory_id) ON DELETE CASCADE,
            subject       TEXT    NOT NULL,
            predicate     TEXT    NOT NULL,
            object        TEXT    NOT NULL,
            object_type   TEXT    NOT NULL DEFAULT 'literal',
            t_valid_start INTEGER NOT NULL,
            t_valid_end   INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_l2_subject_active
            ON l2_semantic(subject, predicate) WHERE t_valid_end IS NULL;

        CREATE INDEX IF NOT EXISTS idx_l2_object_active
            ON l2_semantic(object, predicate) WHERE t_valid_end IS NULL;

        CREATE INDEX IF NOT EXISTS idx_l2_predicate
            ON l2_semantic(predicate);
    """)
    conn.commit()
