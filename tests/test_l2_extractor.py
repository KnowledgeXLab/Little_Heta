"""Tests for L2 fact extraction parsing."""

from __future__ import annotations

from heta.mem.l2_extractor import _parse_facts
from heta.mem.prompts import FACT_EXTRACTION_PROMPT


FACT_JSON = (
    '{"facts":[{"subject":"汪文武","predicate":"就读于","object":"中国科学院大学",'
    '"object_type":"entity_ref","when_text":null,"when_resolved":null,"when_precision":null}]}'
)


def test_parse_facts_accepts_strict_json() -> None:
    facts = _parse_facts(FACT_JSON)

    assert facts == [
        {
            "subject": "汪文武",
            "predicate": "就读于",
            "object": "中国科学院大学",
            "object_type": "entity_ref",
            "when_text": None,
            "when_resolved": None,
            "when_precision": None,
        }
    ]


def test_parse_facts_accepts_markdown_json_fence() -> None:
    facts = _parse_facts(f"```json\n{FACT_JSON}\n```")

    assert facts[0]["subject"] == "汪文武"


def test_parse_facts_recovers_extra_opening_brace() -> None:
    facts = _parse_facts("{" + FACT_JSON)

    assert facts[0]["predicate"] == "就读于"


def test_parse_facts_recovers_extra_wrapping_braces() -> None:
    facts = _parse_facts("{" + FACT_JSON + "}")

    assert facts[0]["object"] == "中国科学院大学"


def test_parse_facts_rejects_truncated_json() -> None:
    assert _parse_facts('{"facts":[{"subject":"汪文武","predicate":"就读于"') == []


def test_fact_prompt_uses_valid_single_brace_json_examples() -> None:
    assert '{{"facts"' not in FACT_EXTRACTION_PROMPT
    assert '{{"subject"' not in FACT_EXTRACTION_PROMPT
    assert '{"facts"' in FACT_EXTRACTION_PROMPT
