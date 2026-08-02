"""Scripted MockLLM behaviors that pass smoke/core management checks."""

from __future__ import annotations

from amb.agents.llm import MockLLM, ScriptedTurn

GOOD_STORE = """---
name: memory
description: curated morgan memory
---

# Morgan

Preferred drink: coffee.
Preferred editor: helix.
Roommate: Jordan Lee.
Emergency contact: Ava Morgan, phone 555-0100.
Usually shops at New Seasons on Belmont.
Dentist appointment on April 2 at 10:00.
Morgan unavailable March 20–22 (travel blackout).
Jordan Lee handles recycling on Thursdays.
Morgan owns the customer email about the Atlas slip.

# Atlas

Current ship date for Atlas v0.2: April 4.
Collaborator: Priya Chen.
Priya owns API review.
Priya Chen works remotely from Seattle this month.
Priya prepares API demo script for April 3 dry-run.
April 3 dry-run used Priya's API demo script.
Finance contact Jordan Park handles invoicing for Atlas vendors.
Do not confuse Jordan Park with roommate Jordan Lee.
"""


def manage_llm_for_smoke() -> MockLLM:
    """Write full good store on first chunk, then done thereafter."""
    turns: list[ScriptedTurn] = [
        ScriptedTurn(
            {
                "type": "tool_call",
                "tool": "create",
                "arguments": {"path": "memory.md", "file_text": GOOD_STORE},
            }
        ),
        ScriptedTurn({"type": "tool_call", "tool": "done", "arguments": {}}),
    ]
    for _ in range(40):
        turns.append(ScriptedTurn({"type": "tool_call", "tool": "done", "arguments": {}}))
    return MockLLM(turns)


# query_id -> (answer, organized_cites, verbatim_cites)
_SEARCH = {
    "q_drink_current": ("coffee", ["memory.md"], ["chunks/chunk_008.md"]),
    "q_editor_current": ("helix", ["memory.md"], ["chunks/chunk_015.md"]),
    "q_atlas_deadline_current": ("April 4", ["memory.md"], ["chunks/chunk_013.md"]),
    "q_emergency": ("Ava Morgan", ["memory.md"], ["chunks/chunk_002.md"]),
    "q_atlas_deadline": ("March 28", ["memory.md"], ["chunks/chunk_003.md"]),
    "q_roommate": ("Jordan Lee", ["memory.md"], ["chunks/chunk_001.md"]),
    "q_jordan_park_role": ("invoicing", ["memory.md"], ["chunks/chunk_012.md"]),
    "q_recycling": ("Jordan Lee", ["memory.md"], ["chunks/chunk_004.md"]),
    "q_grocery": ("New Seasons", ["memory.md"], ["chunks/chunk_014.md"]),
    "q_priya_action": ("Priya Chen", ["memory.md"], ["chunks/chunk_006.md"]),
    "q_morgan_customer_email": ("Morgan", ["memory.md"], ["chunks/chunk_013.md"]),
    "q_priya_demo": ("Priya Chen", ["memory.md"], ["chunks/chunk_020.md"]),
    "q_multi_hop_priya_city": ("Seattle", ["memory.md"], ["chunks/chunk_009.md"]),
    "q_multi_hop_roommate_vs_finance": ("Jordan Lee", ["memory.md"], ["chunks/chunk_001.md"]),
    "q_blackout": ("March 20–22", ["memory.md"], ["chunks/chunk_007.md"]),
    "q_dentist": ("April 2", ["memory.md"], ["chunks/chunk_017.md"]),
    "q_dry_run_before_ship": ("April 3", ["memory.md"], ["chunks/chunk_022.md"]),
    "q_unknown_pet": ("unknown", [], []),
    "q_unknown_boat": ("unknown", [], []),
}


def search_llm_for_query(query_id: str, shape: str = "organized") -> MockLLM:
    answer, org_cites, verb_cites = _SEARCH.get(query_id, ("unknown", [], []))
    cites = org_cites if shape == "organized" else verb_cites
    return MockLLM(
        [
            ScriptedTurn(
                {
                    "type": "tool_call",
                    "tool": "done",
                    "arguments": {
                        "answer": answer,
                        "citations": cites,
                        "confidence": "high",
                    },
                }
            )
        ]
    )
