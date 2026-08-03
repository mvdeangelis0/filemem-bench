# Visual suite v4 — figure-first hybrid (E)

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | 2026-08-03 |
| **Approved** | 2026-08-03 (E + figure-first; §1–§2) |
| **Supersedes** | Animated HTML gallery as README hero (v1–v3) |

## Goal

Match popular memory/eval repos: **static research figures + numbers strip** in the README. No beat-loop HTML as the primary story.

## Ship

1. `docs/visuals/architecture.svg` (+ `.png`) — pipeline: stream → manage → dual stores → search → grade  
2. `docs/visuals/fs-vs-rag.svg` (+ `.png`) — annotated coffee vs tea bakeoff  
3. README: pitch → architecture fig → bakeoff fig → Haiku core numbers table → quickstart + repro link  
4. Archive animated boards to `docs/visuals/archive/`  
5. Rewrite `docs/visuals/README.md` for the new assets  

## Style

Clean research diagram (light paper, ink, sans). No multi-second CSS/JS loops in the hero.

## Non-goals

New animated gallery; live leaderboard infra; regenerating hero GIF.
