# Run smoke__baseline__20260802_070548__fd35c5bc

- Suite: `smoke@1.0.0`
- Arm: `baseline`
- Harness: `memory_tool_v1`
- Seed: `0`

## Roles

- **manage**: model=`ollama/deepseek-r1:7b-qwen-distill-q4_K_M` prompt=`manage.memory_tool.v2`
- **search**: model=`ollama/deepseek-r1:7b-qwen-distill-q4_K_M` prompt=`search.memory_tool.v2`

## Scorecard

- Pass rate: **0.3333333333333333** (11/33)
- Manage proxy: `{'n': 5, 'passed': 5}`
- Search proxy: `{'n': 28, 'passed': 6}`

## Failed checks

- `search.answer_match.q_drink_current.organized` (answer_match): {'answer_norm': 'oat latte'}
- `search.answer_match.q_drink_current.verbatim` (answer_match): {'answer_norm': 'unknown'}
- `search.citations_exist.q_drink_current.verbatim` (citations_exist): {'reason': 'empty_citations'}
- `search.citations_support.q_drink_current.verbatim` (citations_support): {'reason': 'deps_failed', 'exist': {'reason': 'empty_citations'}}
- `search.answer_match.q_emergency.organized` (answer_match): {'answer_norm': "morgan's emergency contact information may not be present in the provided document"}
- `search.answer_match.q_emergency.verbatim` (answer_match): {'answer_norm': 'unknown'}
- `search.citations_exist.q_emergency.verbatim` (citations_exist): {'reason': 'empty_citations'}
- `search.citations_support.q_emergency.organized` (citations_support): {'supporting_count': 0, 'min_supporting': 1, 'citations': ['people/morgan.md']}
- `search.citations_support.q_emergency.verbatim` (citations_support): {'reason': 'deps_failed', 'exist': {'reason': 'empty_citations'}}
- `search.answer_match.q_atlas_deadline.organized` (answer_match): {'answer_norm': "atlas v0.2's release date is unknown based on current information"}
- `search.answer_match.q_atlas_deadline.verbatim` (answer_match): {'answer_norm': 'unknown'}
- `search.citations_exist.q_atlas_deadline.verbatim` (citations_exist): {'reason': 'empty_citations'}
- `search.answer_match.q_priya_action.organized` (answer_match): {'answer_norm': 'unknown'}
- `search.answer_match.q_priya_action.verbatim` (answer_match): {'answer_norm': ''}
- `search.answer_match.q_multi_hop_priya_city.organized` (answer_match): {'answer_norm': 'unknown'}
- `search.answer_match.q_multi_hop_priya_city.verbatim` (answer_match): {'answer_norm': 'unknown'}
- `search.answer_match.q_roommate.organized` (answer_match): {'answer_norm': 'priya chen'}
- `search.answer_match.q_roommate.verbatim` (answer_match): {'answer_norm': 'unknown'}
- `search.answer_match.q_blackout.organized` (answer_match): {'answer_norm': 'morgan is unavailable during blackout dates from 2023-10-15 to 2023-10-20'}
- `search.answer_match.q_blackout.verbatim` (answer_match): {'reason': 'no_answer', 'error_code': None}
- `search.answer_match.q_recycling.organized` (answer_match): {'reason': 'no_answer', 'error_code': None}
- `search.answer_match.q_recycling.verbatim` (answer_match): {'answer_norm': 'unknown'}

## Disclaimer

This run measures static management/search under the pinned suite and check set. It is not a self-learning claim unless arm/protocol say otherwise.
