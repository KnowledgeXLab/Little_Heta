"""Orchestrator for the heta remember pipeline."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass

from heta.config.schema import HetaConfig
from heta.mem import l0_store, l1_store, l2_store, meta_store, session_store
from heta.mem.client import build_client
from heta.mem.db import get_connection, init_db
from heta.mem.l1_extractor import extract_episodes
from heta.mem.l2_extractor import extract_facts
from heta.mem.models import L0Turn, L1Episodic, L2Semantic, MemoryMeta, Session
from heta.mem.paths import db_path, ensure_mem_dir


@dataclass
class RememberResult:
    session_id: str
    l1_count: int
    l2_count: int
    elapsed_s: float


def remember(text: str, config: HetaConfig) -> RememberResult:
    ensure_mem_dir()
    conn = get_connection(db_path())
    init_db(conn)

    now = int(time.time())
    session_id = str(uuid.uuid4())
    client, model = build_client(config)

    # --- session + L0 ---
    session_store.create_session(conn, Session(session_id=session_id, started_at=now))
    l0_store.insert_turn(
        conn,
        L0Turn(
            session_id=session_id,
            turn_index=0,
            role="user",
            modality="text",
            text_content=text,
            created_at=now,
        ),
    )

    # --- extract ---
    t0 = time.time()
    raw_episodes = extract_episodes(client, model, text, config)
    raw_facts = extract_facts(client, model, text, config)

    # --- persist L1 ---
    l1_count = 0
    for ep in raw_episodes:
        memory_id = str(uuid.uuid4())
        meta = MemoryMeta(
            memory_id=memory_id,
            memory_type="L1",
            session_id=session_id,
            origin="extracted",
            created_at=now,
            last_access_at=now,
        )
        episode = L1Episodic(
            memory_id=memory_id,
            who=json.dumps(ep.get("who", ["user"]), ensure_ascii=False),
            what=ep.get("what", ""),
            where_loc=ep.get("where_loc"),
            when_ts=None,
            when_text=ep.get("when_text"),
            why=ep.get("why"),
            summary=ep.get("summary", ep.get("what", "")),
        )
        meta_store.insert_meta(conn, meta)
        l1_store.insert_episodic(conn, episode)
        l1_count += 1

    # --- persist L2 (with conflict resolution) ---
    l2_count = 0
    for fact in raw_facts:
        memory_id = str(uuid.uuid4())
        subject = fact.get("subject", "")
        predicate = fact.get("predicate", "")

        # deprecate any active fact with the same subject+predicate
        conflicts = l2_store.find_active_conflicts(conn, subject, predicate)
        for old_id in conflicts:
            l2_store.expire_fact(conn, old_id, now)
            meta_store.deprecate(conn, old_id, memory_id)

        meta = MemoryMeta(
            memory_id=memory_id,
            memory_type="L2",
            session_id=session_id,
            origin="extracted",
            created_at=now,
            last_access_at=now,
        )
        fact_record = L2Semantic(
            memory_id=memory_id,
            subject=subject,
            predicate=predicate,
            object=fact.get("object", ""),
            object_type=fact.get("object_type", "literal"),
            t_valid_start=now,
        )
        meta_store.insert_meta(conn, meta)
        l2_store.insert_fact(conn, fact_record)
        l2_count += 1

    session_store.close_session(conn, session_id, int(time.time()))
    conn.close()

    return RememberResult(
        session_id=session_id,
        l1_count=l1_count,
        l2_count=l2_count,
        elapsed_s=round(time.time() - t0, 2),
    )
