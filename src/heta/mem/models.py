"""Dataclasses for all memory tables."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Session:
    session_id: str
    started_at: int
    ended_at: int | None = None
    consolidated: int = 0
    consolidated_at: int | None = None


@dataclass
class L0Turn:
    session_id: str
    turn_index: int
    role: str           # user / assistant / system / tool
    modality: str       # text / audio / image / mixed
    text_content: str
    created_at: int


@dataclass
class MemoryMeta:
    memory_id: str
    memory_type: str    # L1 / L2
    session_id: str | None
    origin: str         # extracted / promoted / user_explicit / consolidated
    created_at: int
    last_access_at: int
    kb_uid: str | None = None
    status: str = "active"
    deprecated_by: str | None = None
    recency_score: float = 1.0
    access_freq: int = 0
    user_emphasis: float = 0.0
    importance: float = 0.5
    confidence: float = 0.9


@dataclass
class L1Episodic:
    memory_id: str
    who: str            # JSON array, e.g. '["Alice", "Bob"]'
    what: str
    where_loc: str | None
    when_ts: int | None
    when_text: str | None
    why: str | None
    summary: str        # used for vector embedding


@dataclass
class L2Semantic:
    memory_id: str
    subject: str
    predicate: str
    object: str
    object_type: str    # literal / entity_ref
    t_valid_start: int
    t_valid_end: int | None = None
