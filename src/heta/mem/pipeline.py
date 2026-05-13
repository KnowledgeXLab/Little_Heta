"""Orchestrator for the heta remember pipeline."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass

from heta.config.schema import HetaConfig
from heta.mem import l0_store, l1_store, l2_store, meta_store, session_store
from heta.mem.client import build_client, build_embedding_client
from heta.mem.db import get_connection, init_db
from heta.mem.embedder import embed_text, fact_text
from heta.mem.l1_extractor import extract_episodes, resolve_when_ts
from heta.mem.l2_conflict import detect_conflicts
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
    conn = get_connection(db_path(), with_vec=True)
    init_db(conn)

    now = int(time.time())
    session_id = str(uuid.uuid4())
    llm_client, llm_model = build_client(config)
    emb_client, emb_model = build_embedding_client(config)

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
    raw_episodes = extract_episodes(llm_client, llm_model, text, config, session_ts=now)
    raw_facts = extract_facts(llm_client, llm_model, text, config, session_ts=now)

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
            when_ts=resolve_when_ts(ep.get("when_resolved")),
            when_text=ep.get("when_text"),
            when_resolved=ep.get("when_resolved"),
            when_precision=ep.get("when_precision"),
            why=ep.get("why"),
            summary=ep.get("summary", ep.get("what", "")),
        )
        meta_store.insert_meta(conn, meta)
        l1_store.insert_episodic(conn, episode)
        l1_emb = embed_text(emb_client, emb_model, episode.summary)
        l1_store.insert_episode_embedding(conn, memory_id, l1_emb)
        l1_count += 1

    # --- persist L2 (semantic conflict resolution) ---
    l2_count = 0
    for raw_fact in raw_facts:
        memory_id = str(uuid.uuid4())
        subject = str(raw_fact.get("subject", ""))
        predicate = str(raw_fact.get("predicate", ""))
        object_ = str(raw_fact.get("object", ""))
        raw_object_type = raw_fact.get("object_type", "literal")
        object_type_val = raw_object_type[0] if isinstance(raw_object_type, list) else str(raw_object_type)
        ft = fact_text(subject, predicate, object_)

        ids_to_deprecate, embedding = detect_conflicts(
            conn=conn,
            new_fact_text=ft,
            llm_client=llm_client,
            llm_model=llm_model,
            emb_client=emb_client,
            emb_model=emb_model,
            config=config,
            session_id=session_id,
        )

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
            object=object_,
            object_type=object_type_val,
            fact_text=ft,
            t_valid_start=now,
            when_text=raw_fact.get("when_text"),
            when_resolved=raw_fact.get("when_resolved"),
            when_precision=raw_fact.get("when_precision"),
        )

        # insert new meta + fact first so FK reference is valid
        meta_store.insert_meta(conn, meta)
        for old_id in ids_to_deprecate:
            l2_store.expire_fact(conn, old_id, now)
            meta_store.deprecate(conn, old_id, memory_id)
        l2_store.insert_fact(conn, fact_record)
        l2_store.insert_fact_embedding(conn, memory_id, embedding)
        l2_count += 1

    session_store.close_session(conn, session_id, int(time.time()))
    conn.close()

    return RememberResult(
        session_id=session_id,
        l1_count=l1_count,
        l2_count=l2_count,
        elapsed_s=round(time.time() - t0, 2),
    )
