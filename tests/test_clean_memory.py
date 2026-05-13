"""Tests for heta.mem.clean.clean_memory."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import pytest

from heta.mem.clean import clean_memory
from heta.mem.db import get_connection, init_db
from heta.mem.l0_store import insert_turn
from heta.mem.l1_store import insert_episodic
from heta.mem.l2_store import expire_fact, insert_fact
from heta.mem.meta_store import deprecate, insert_meta
from heta.mem.models import L0Turn, L1Episodic, L2Semantic, MemoryMeta, Session
from heta.mem.session_store import close_session, create_session


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def conn(tmp_path: Path):
    db = tmp_path / "test_mem.sqlite3"
    c = get_connection(db, with_vec=True)
    init_db(c)
    yield c
    c.close()


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> int:
    return int(time.time())


def _insert_session(conn, session_id: str | None = None) -> str:
    sid = session_id or _new_id()
    create_session(conn, Session(session_id=sid, started_at=_now()))
    close_session(conn, sid, _now())
    return sid


def _insert_l0(conn, session_id: str) -> None:
    insert_turn(conn, L0Turn(
        session_id=session_id,
        turn_index=0,
        role="user",
        modality="text",
        text_content="hello world",
        created_at=_now(),
    ))


def _insert_l2(conn, session_id: str) -> str:
    mid = _new_id()
    insert_meta(conn, MemoryMeta(
        memory_id=mid, memory_type="L2", session_id=session_id,
        origin="extracted", created_at=_now(), last_access_at=_now(),
    ))
    insert_fact(conn, L2Semantic(
        memory_id=mid, subject="user", predicate="lives_in", object="Beijing",
        object_type="literal", fact_text="user lives_in Beijing",
        t_valid_start=_now(),
    ))
    return mid


def _insert_l1(conn, session_id: str) -> str:
    mid = _new_id()
    insert_meta(conn, MemoryMeta(
        memory_id=mid, memory_type="L1", session_id=session_id,
        origin="extracted", created_at=_now(), last_access_at=_now(),
    ))
    insert_episodic(conn, L1Episodic(
        memory_id=mid, who='["user"]', what="went to the park",
        where_loc="park", when_ts=None, when_text=None,
        when_resolved=None, when_precision=None, why=None,
        summary="user went to the park",
    ))
    return mid


def _row_count(conn, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# ── tests ─────────────────────────────────────────────────────────────────────

def test_clean_empty_db_is_idempotent(conn) -> None:
    result = clean_memory(conn)
    assert result.deleted_sessions == 0
    assert result.deleted_l0_turns == 0
    assert result.deleted_l1_episodes == 0
    assert result.deleted_l2_facts == 0
    assert result.deleted_meta == 0


def test_clean_removes_session_and_l0_turns(conn) -> None:
    sid = _insert_session(conn)
    _insert_l0(conn, sid)

    result = clean_memory(conn)

    assert result.deleted_sessions == 1
    assert result.deleted_l0_turns == 1
    assert _row_count(conn, "session") == 0
    assert _row_count(conn, "l0_turn") == 0


def test_clean_removes_l2_facts_and_meta(conn) -> None:
    sid = _insert_session(conn)
    _insert_l2(conn, sid)

    result = clean_memory(conn)

    assert result.deleted_l2_facts == 1
    assert result.deleted_meta == 1
    assert _row_count(conn, "l2_semantic") == 0
    assert _row_count(conn, "memory_meta") == 0


def test_clean_removes_l1_episodes_and_meta(conn) -> None:
    sid = _insert_session(conn)
    _insert_l1(conn, sid)

    result = clean_memory(conn)

    assert result.deleted_l1_episodes == 1
    assert result.deleted_meta == 1
    assert _row_count(conn, "l1_episodic") == 0
    assert _row_count(conn, "memory_meta") == 0


def test_clean_removes_deprecated_facts(conn) -> None:
    sid = _insert_session(conn)
    old_id = _insert_l2(conn, sid)
    new_id = _insert_l2(conn, sid)
    expire_fact(conn, old_id, _now())
    deprecate(conn, old_id, new_id)

    assert _row_count(conn, "l2_semantic") == 2
    assert _row_count(conn, "memory_meta") == 2

    result = clean_memory(conn)

    assert result.deleted_l2_facts == 2
    assert result.deleted_meta == 2
    assert _row_count(conn, "l2_semantic") == 0
    assert _row_count(conn, "memory_meta") == 0


def test_clean_removes_all_layers_together(conn) -> None:
    sid = _insert_session(conn)
    _insert_l0(conn, sid)
    _insert_l1(conn, sid)
    _insert_l2(conn, sid)

    result = clean_memory(conn)

    assert result.deleted_sessions == 1
    assert result.deleted_l0_turns == 1
    assert result.deleted_l1_episodes == 1
    assert result.deleted_l2_facts == 1
    assert result.deleted_meta == 2  # one L1 meta + one L2 meta


def test_clean_multiple_sessions(conn) -> None:
    for _ in range(3):
        sid = _insert_session(conn)
        _insert_l0(conn, sid)
        _insert_l2(conn, sid)

    result = clean_memory(conn)

    assert result.deleted_sessions == 3
    assert result.deleted_l0_turns == 3
    assert result.deleted_l2_facts == 3
    assert _row_count(conn, "session") == 0
    assert _row_count(conn, "l0_turn") == 0
    assert _row_count(conn, "l2_semantic") == 0


def test_clean_preserves_schema(conn) -> None:
    """Tables must still exist and accept inserts after a clean."""
    sid = _insert_session(conn)
    _insert_l0(conn, sid)
    _insert_l1(conn, sid)
    _insert_l2(conn, sid)
    clean_memory(conn)

    # DB should still be fully usable after clean
    sid2 = _insert_session(conn)
    _insert_l0(conn, sid2)
    _insert_l2(conn, sid2)

    assert _row_count(conn, "session") == 1
    assert _row_count(conn, "l0_turn") == 1
    assert _row_count(conn, "l2_semantic") == 1


def test_clean_is_idempotent(conn) -> None:
    sid = _insert_session(conn)
    _insert_l0(conn, sid)
    _insert_l2(conn, sid)

    first = clean_memory(conn)
    second = clean_memory(conn)  # called on already-empty DB

    assert first.deleted_sessions == 1
    assert second.deleted_sessions == 0
    assert second.deleted_l2_facts == 0
