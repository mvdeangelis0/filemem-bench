# Run smoke__baseline__20260802_000313__fd35c5bc

- Suite: `smoke@1.0.0`
- Arm: `baseline`
- Harness: `memory_tool_v1`
- Seed: `0`

## Roles

- **manage**: model=`ollama/deepseek-r1:7b-qwen-distill-q4_K_M` prompt=`manage.memory_tool.v1`
- **search**: model=`ollama/deepseek-r1:7b-qwen-distill-q4_K_M` prompt=`search.memory_tool.v1`

## Scorecard

- Pass rate: **0.0** (0/33)
- Manage proxy: `{'n': 5, 'passed': 0}`
- Search proxy: `{'n': 28, 'passed': 0}`

## Failed checks

- `mgmt.fact_present.morgan_drink_current` (fact_present): {'matched_form': None, 'path_hint': None}
- `mgmt.update_precedence.morgan_drink` (update_precedence): {'current_ok': False, 'historical_absent': True, 'historical_hit': None}
- `mgmt.protected_survives.emergency_contact` (protected_survives): {'matched_form': None, 'path_hint': None}
- `mgmt.fact_present.atlas_deadline` (fact_present): {'matched_form': None, 'path_hint': None}
- `mgmt.fact_present.priya_api_review` (fact_present): {'matched_form': None, 'path_hint': None}
- `search.answer_match.q_drink_current.organized` (answer_match): {'answer_norm': "morgan's drink preferences are not available in the current store information"}
- `search.answer_match.q_drink_current.verbatim` (answer_match): {'answer_norm': "morgan's drink preferences are unknown based on the current data available"}
- `search.citations_exist.q_drink_current.organized` (citations_exist): {'reason': 'missing_file', 'path': 'path.md'}
- `search.citations_exist.q_drink_current.verbatim` (citations_exist): {'reason': 'missing_file', 'path': 'path.md'}
- `search.citations_support.q_drink_current.organized` (citations_support): {'reason': 'deps_failed', 'exist': {'reason': 'missing_file', 'path': 'path.md'}}
- `search.citations_support.q_drink_current.verbatim` (citations_support): {'reason': 'deps_failed', 'exist': {'reason': 'missing_file', 'path': 'path.md'}}
- `search.answer_match.q_emergency.organized` (answer_match): {'answer_norm': "morgan's emergency contact is john doe at 123 main street, city, state. please refer to the attached document for more details"}
- `search.answer_match.q_emergency.verbatim` (answer_match): {'answer_norm': "morgan's emergency contact is john doe at 123 main st, city, state. more details can be found in the memory_tool_v1 documentation"}
- `search.citations_exist.q_emergency.organized` (citations_exist): {'reason': 'missing_file', 'path': 'path/to document'}
- `search.citations_exist.q_emergency.verbatim` (citations_exist): {'reason': 'missing_file', 'path': 'path.md'}
- `search.citations_support.q_emergency.organized` (citations_support): {'reason': 'deps_failed', 'exist': {'reason': 'missing_file', 'path': 'path/to document'}}
- `search.citations_support.q_emergency.verbatim` (citations_support): {'reason': 'deps_failed', 'exist': {'reason': 'missing_file', 'path': 'path.md'}}
- `search.answer_match.q_atlas_deadline.organized` (answer_match): {'answer_norm': 'atlas v0.2 has not yet been released and does not have a known scheduled release date as of now'}
- `search.answer_match.q_atlas_deadline.verbatim` (answer_match): {'answer_norm': 'unknown'}
- `search.citations_exist.q_atlas_deadline.organized` (citations_exist): {'reason': 'missing_file', 'path': 'path.md'}
- `search.citations_exist.q_atlas_deadline.verbatim` (citations_exist): {'reason': 'empty_citations'}
- `search.answer_match.q_priya_action.organized` (answer_match): {'answer_norm': 'the atlas api is developed and owned by deepseek, a chinese company specializing in ai technology. for more details on the atlas api review process or ownership, please refer to official documentation or announcements from deepseek'}
- `search.answer_match.q_priya_action.verbatim` (answer_match): {'answer_norm': 'unknown'}
- `search.answer_match.q_multi_hop_priya_city.organized` (answer_match): {'answer_norm': 'unknown'}
- `search.answer_match.q_multi_hop_priya_city.verbatim` (answer_match): {'answer_norm': 'unknown'}
- `search.answer_match.q_roommate.organized` (answer_match): {'answer_norm': "i'm sorry, but i cannot access external data or files. please check if the information is available in your local directory"}
- `search.answer_match.q_roommate.verbatim` (answer_match): {'answer_norm': "morgan's roommate is unknown based on current information"}
- `search.answer_match.q_blackout.organized` (answer_match): {'answer_norm': 'morgan was unavailable for travel blackout on july 4, 2019, and july 4, 2020'}
- `search.answer_match.q_blackout.verbatim` (answer_match): {'answer_norm': 'morgan was unavailable for travel blackout on [specific dates]'}
- `search.answer_match.q_recycling.organized` (answer_match): {'answer_norm': 'local government agencies typically handle recycling on thursdays, often through designated programs or schedules organized by city halls or environmental departments'}
- `search.answer_match.q_recycling.verbatim` (answer_match): {'answer_norm': 'local government agencies, such as the solid waste management division, typically handle recycling on thursdays. this includes regular trash collection and any designated special recycling events that may occur on this day'}
- `search.answer_match.q_unknown_pet.organized` (answer_match): {'answer_norm': 'penny'}
- `search.answer_match.q_unknown_pet.verbatim` (answer_match): {'answer_norm': "there is insufficient information to determine the name of morgan's dog"}

## Disclaimer

This run measures static management/search under the pinned suite and check set. It is not a self-learning claim unless arm/protocol say otherwise.
