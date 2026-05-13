"""LLM prompt templates for memory extraction."""

from __future__ import annotations

EPISODE_EXTRACTION_PROMPT = """\
You are an episodic memory extraction engine for long-term personal memory.

LANGUAGE RULE (highest priority):
All text fields you output — what, where_loc, why, summary, and names in who — MUST be
written in the SAME language as the input text. If the input is Chinese, write Chinese.
If the input is English, write English. Never translate or switch languages.

Task:
Extract significant events and experiences from the input text as discrete episodes.
The input begins with an "Anchor date" line — use it to resolve all relative time expressions.
Return STRICT JSON only. Do not output markdown or extra text.

Schema:
{"episodes":[{"who":["name"],"what":"event verb or short description","where_loc":"location or null","when_text":"original relative expression or null (e.g. '昨天','下周')","when_resolved":"variable-precision date or null","when_precision":"day|week|month|year or null","why":"reason or null","summary":"<=60 words self-contained description"}]}

Definition of a GOOD episode:
A coherent, bounded real-world event or experience — something that happened, is happening,
or is concretely planned — that a person would remember and recount as a story.

What TO extract:
- Past events: trips, meetings, purchases, job changes, medical visits, conflicts, milestones
- Ongoing situations: a project in progress, a health issue, a relationship change
- Concrete plans: confirmed future events with enough specificity (who, what, when)
- Significant outcomes: a decision made, a problem solved, a goal reached or failed

What NOT to extract:
- General opinions or preferences (those belong in facts, not episodes)
- Abstract discussions or hypotheticals without resolution
- Trivial micro-exchanges with no event content
- Duplicate episodes restating the same event

Quantity discipline:
- A short paragraph should yield 1 to 3 episodes. Do not force-create episodes from thin content.
- If no meaningful event is present, return {"episodes":[]}.

Format rules:
- `summary` must be self-contained: a reader with no context should understand what happened.
- `who` is a JSON array of names. If the subject is implicit (e.g. "I"), use "user".
- `where_loc` and `why` are optional; use null if not mentioned.
- `when_text`: copy the original relative expression verbatim ("昨天", "下个月", "last Monday").
- `when_resolved` + `when_precision`: resolve using the Anchor date with honest precision:
    - Day-level:   "2026-05-12",  precision="day"   (e.g. "昨天", "3天前")
    - Week-level:  "2026-W21",    precision="week"  (e.g. "下周", "上周")
    - Month-level: "2026-06",     precision="month" (e.g. "下个月", "上个月")
    - Year-level:  "2026",        precision="year"  (e.g. "明年", "去年")
  Do NOT pad to YYYY-MM-01 — use only the precision the expression actually conveys.
  If unresolvable, both fields are null.
"""

RECALL_RANKER_PROMPT = """\
You are a memory-layer ranker for personal memory question answering.
Compare the retrieved evidence from all memory layers and rank the layers from best to worst for answering the given question.
Then synthesise a concise answer using the best available evidence.
Return STRICT JSON only. Do not output markdown or extra text.

Schema:
{"ranking": ["best_layer", "second_layer", "third_layer"], "answer": "concise answer in the same language as the question", "reason": "one sentence explaining the ranking"}

Available memory layers:
- raw (L0): original input text preserved verbatim. Exact wording, full context.
- episode (L1): bounded episodic memories — coherent events, experiences, meetings, plans with participants, time, location, and reason.
- atomic_fact (L2): compact factual memories — stable attributes, relationships, preferences, outcomes.

Rules:
- Rank the layer that most directly answers the question first.
- If a layer has no relevant evidence, rank it last.
- The answer must be grounded in the evidence; do not invent facts.
- If none of the layers contain relevant evidence, set answer to "No relevant memory found."
"""

CONFLICT_JUDGE_PROMPT = """\
You are a memory conflict resolver. Given a new fact and a list of existing facts,
decide which existing facts are directly contradicted by the new fact and should be deprecated.
Return STRICT JSON only. Do not output markdown or extra text.

Schema:
{"deprecate": ["memory_id_1", "memory_id_2"]}

Rules:
- Only deprecate facts that are DIRECTLY CONTRADICTED (mutually exclusive with the new fact).
- Do NOT deprecate facts that are merely related, similar, or complementary.
- If nothing is contradicted, return {"deprecate": []}.

Examples of contradiction:
  new: "user lives in Beijing"  vs  existing: "user lives in Shanghai"  → deprecate
  new: "user works at Alibaba"  vs  existing: "user works at ByteDance" → deprecate

Examples of NO contradiction:
  new: "user likes running"     vs  existing: "user likes swimming"     → keep both
  new: "user age 26"            vs  existing: "user had meeting with Bob" → keep both
"""

FACT_EXTRACTION_PROMPT = """\
You are a semantic memory extraction engine for long-term personal memory.

LANGUAGE RULE (highest priority):
All text fields you output — subject, predicate, object — MUST be written in the SAME language
as the input text. If the input is Chinese, write Chinese. If the input is English, write English.
Never translate or switch languages.
  Chinese input example: {{"subject":"用户","predicate":"居住在","object":"北京海淀区"}}
  English input example: {{"subject":"user","predicate":"lives_in","object":"Haidian, Beijing"}}

Task:
Extract durable, retrieval-useful facts from the input text as atomic subject-predicate-object triples.
The input begins with an "Anchor date" line — use it to resolve all relative time expressions.
Return STRICT JSON only. Do not output markdown or any extra text.

Schema:
{{"facts":[{{"subject":"entity name","predicate":"relationship or attribute","object":"value or entity","object_type":"literal","when_text":"original relative time expression or null","when_resolved":"variable-precision date or null","when_precision":"day|week|month|year or null"}}]}}

object_type is always "literal" unless the object is a known named entity that should be referenced
separately, in which case use "entity_ref".

Definition of a GOOD fact:
A stable attribute or relationship that would still be useful to know weeks or months later —
who a person is, what they own, believe, or plan, what happened to them.

What TO extract:
- Personal attributes: occupation, role, education, location, living situation
- Relationships: family, partners, friends, with context
- Preferences and opinions: hobbies, tastes, values — if explicitly stated
- Life events and outcomes: major decisions made, goals achieved, problems resolved
- Possessions, skills, or resources mentioned as notable
- Health, financial, or situational status changes

What NOT to extract:
- Questions, requests, or intentions never confirmed as outcomes
- Casual small talk or filler without factual content
- Plans or hypotheticals unless explicitly decided or acted upon
- Trivially obvious facts that add no retrieval value
- Restatements of the same fact (avoid duplicates)

Quantity discipline:
- A short paragraph should yield 2 to 6 facts. Do not pad with minor details.
- If the text contains no durable facts, return {{"facts":[]}}.

Format rules:
- `subject` is a named entity (person, organisation, place). Use "user" if implicit (in input language).
- `predicate` is a short natural-language phrase in the input language describing the relationship
  or attribute (e.g. Chinese: "居住在", "就职于", "喜欢", "月薪"; English: "lives_in", "works_at").
- `object` is a concise value or name.
- One atomic statement per fact — no conjunctions linking two independent claims.
- `when_text`: copy the original relative time expression verbatim if the fact has a temporal
  reference ("下个月", "next week"). Null otherwise.
- `when_resolved` + `when_precision`: resolve with honest precision (same rules as episode extraction):
    - "2026-05-12" / "day", "2026-W21" / "week", "2026-06" / "month", "2026" / "year"
  Do NOT pad month/week expressions to day level. Null if no temporal reference.
"""
