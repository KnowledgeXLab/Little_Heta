"""LLM prompt templates for memory extraction."""

from __future__ import annotations

EPISODE_EXTRACTION_PROMPT = """\
You are an episodic memory extraction engine for long-term personal memory.

Task:
Extract significant events and experiences from the input text as discrete episodes.
Return STRICT JSON only. Do not output markdown or extra text.

Schema:
{"episodes":[{"who":["name"],"what":"event verb or short description","where_loc":"location or null","when_text":"original time expression or null","why":"reason or null","summary":"<=60 words self-contained description"}]}

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
- `when_text` preserves the original time expression ("yesterday", "last Monday", etc.).
- Output language should follow input language.
"""

FACT_EXTRACTION_PROMPT = """\
You are a semantic memory extraction engine for long-term personal memory.

Task:
Extract durable, retrieval-useful facts from the input text as atomic subject-predicate-object triples.
Return STRICT JSON only. Do not output markdown or any extra text.

Schema:
{"facts":[{"subject":"entity name","predicate":"relationship or attribute","object":"value or entity","object_type":"literal"}]}

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
- If the text contains no durable facts, return {"facts":[]}.

Format rules:
- `subject` is a named entity (person, organisation, place). Use "user" if implicit.
- `predicate` uses snake_case (e.g. "works_at", "lives_in", "owns", "prefers").
- `object` is a concise value or name.
- One atomic statement per fact — no conjunctions linking two independent claims.
- Output language should follow input language.
"""
