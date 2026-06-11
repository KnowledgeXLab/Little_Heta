"""Tests for memory inspection commands."""

from __future__ import annotations

from pathlib import Path

import pytest

from heta.cli.mem_show import _count_all_memories, _fetch_all_memories
from heta.mem.db import get_connection, init_db


@pytest.fixture()
def conn(tmp_path: Path):
    db = tmp_path / "mem.sqlite3"
    c = get_connection(db, with_vec=True)
    init_db(c)
    yield c
    c.close()


def test_fetch_all_memories_returns_all_memory_layers(conn) -> None:
    conn.execute(
        "INSERT INTO session (session_id, started_at, ended_at) VALUES (?, ?, ?)",
        ("session-1", 100, 120),
    )
    conn.execute(
        "INSERT INTO l0_turn (session_id, turn_index, role, modality, text_content, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("session-1", 0, "user", "text", "汪文武是一名博士研究生", 101),
    )
    conn.execute(
        """INSERT INTO memory_meta
           (memory_id, memory_type, session_id, origin, status, created_at, last_access_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("l1-1", "L1", "session-1", "extracted", "active", 102, 102),
    )
    conn.execute(
        """INSERT INTO l1_episodic
           (memory_id, who, what, where_loc, when_ts, when_text, when_resolved, when_precision, why, summary)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("l1-1", '["汪文武"]', "就读", "中国科学院大学", None, None, None, None, None, "汪文武就读于中国科学院大学"),
    )
    conn.execute(
        """INSERT INTO memory_meta
           (memory_id, memory_type, session_id, origin, status, created_at, last_access_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("l2-1", "L2", "session-1", "extracted", "active", 103, 103),
    )
    conn.execute(
        """INSERT INTO l2_semantic
           (memory_id, subject, predicate, object, object_type, fact_text, t_valid_start, t_valid_end)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("l2-1", "汪文武", "就读于", "中国科学院大学", "entity_ref", "汪文武就读于中国科学院大学", 103, None),
    )
    conn.execute(
        """INSERT INTO memory_meta
           (memory_id, memory_type, session_id, origin, status, created_at, last_access_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("kb-1", "kb_insight", None, "kb_insight", "active", 104, 104),
    )
    conn.execute(
        """INSERT INTO kb_insight
           (memory_id, insight, question, source_path, wiki_id, heading_path, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("kb-1", "工业智能中枢是一个工业智能平台", "工业智能中枢是什么", "pages/industrial.md", 1, None, 104),
    )
    conn.execute(
        "INSERT INTO kb_insight_source (memory_id, source_path) VALUES (?, ?)",
        ("kb-1", "pages/industrial.md"),
    )
    conn.commit()

    memories = _fetch_all_memories(conn, limit=10)
    totals = _count_all_memories(conn)

    assert memories["l0"][0]["text_content"] == "汪文武是一名博士研究生"
    assert memories["l1"][0]["summary"] == "汪文武就读于中国科学院大学"
    assert memories["l2"][0]["fact_text"] == "汪文武就读于中国科学院大学"
    assert memories["kb_insight"][0]["insight"] == "工业智能中枢是一个工业智能平台"
    assert totals == {"l0": 1, "l1": 1, "l2": 1, "kb_insight": 1}
