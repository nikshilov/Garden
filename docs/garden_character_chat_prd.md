# Garden Character & Chat System — PRD

Status: Draft for review (Doc-first)
Owner: GardenCore
Last updated: 2025-08-22

---

## 1. Purpose & Goals

Build a modular, LangGraph-first character chat system for Garden that enables multi-character conversations, emotional memory, context longevity, and transparent cost tracking, with clean interfaces to outsource modules safely.

Top goals (MVP→P5):
- Natural multi-character dialogue with routing and optional cross-talk.
- Character-specific prompts with mood and episodic/semantic memory.
- Long-context via sliding window + episodic summaries.
- Intimacy Mode with auto-switch triggers and explicit commands.
- Cost tracking with per-model and per-category breakdowns.
- Persisted state and deterministic prompt assembly.

Non-goals (MVP):
- Public social backend; marketplace; billing.

References:
- Backend code: `backend/garden_graph/`
- Docs: `docs/architecture.md`, `docs/memory_algorithm.md`, `docs/long_context.md`, `docs/emotional_memory.md`, `docs/cost_tracker.md`, `docs/intimacy_mode.md`

---

## 2. High-Level Architecture

- Orchestration (LangGraph)
  - Graph: `garden_graph/graph.py` → `create_world_chat_graph()` builds nodes and conditional edges.
  - State: `ChatState` with `user_message`, `message_history`, `active_characters`, `selected_characters`, `character_responses`, `intimacy_mode`, `final_response`, `costs`.

- Core nodes
  - Router: `garden_graph/router.py` → `Router.route()` chooses characters (≤2) based on mentions, names, fuzzy rules, then LLM fallback.
  - Character: `garden_graph/character.py` → `Character.respond()` assembles prompt (persona + mood + memories + episodic summaries) and calls LLM.
  - Collator: `collate_node()` merges replies into final output.
  - Cross-talk: `cross_talk_node()` lets characters briefly react to each other with a “pass” escape.

- Services
  - Cost tracker: `garden_graph/cost_tracker.py` → `CostTracker.record(model, prompt_tokens, completion_tokens, category=...)` and summaries.
  - Intimacy agent: `garden_graph/intimate_agent.py` (used when `intimacy_mode=true`).
  - Summarizer: `garden_graph/summarizer.py` (episodic TL;DR).
  - Episodic store: `garden_graph/memory/episodic.py` (`EpisodicStore`).
  - Config: `garden_graph/config.py` → `get_llm()`, `ROUTER_MODEL`, thresholds for Intimacy Mode (`INTIMACY_AFFECTION_THRESHOLD`, `INTIMACY_AROUSAL_THRESHOLD`).

- Persistence
  - Lightweight file-based stores under `backend/data/` (e.g., `mood_states.json`, `last_seen_times.json`) + episodic store files.
  - iOS client: Core Data + CloudKit (see `docs/architecture.md`).

---

## 3. Data Model (Backend-facing)

- Message (history list entries in `graph.py`)
```jsonc
{
  "role": "Eve" | "Atlas" | "user",          // UI label (character name or user)
  "content": "string",                        // message text
  "character_id": "eve" | "atlas" | null,    // null for user
  "timestamp": "ISO8601"
}
```

- Character template (`Character`)
```jsonc
{
  "id": "eve",
  "name": "Eve",
  "base_prompt": "You are Eve...",
  "model": "gpt-3.5-turbo",
  "mood": {"vector": {"valence": 0.1, "arousal": 0.2, ...}, "set_at": "ISO"}
}
```

- Memory (legacy in-object + external manager)
```jsonc
{
  "id": "mem_...",
  "event_text": "user insulted me once...",
  "sentiment": -1,
  "weight": 0.6,
  "created_at": "ISO",
  "last_touched": "ISO"
}
```

- Episodic summaries (`EpisodicStore`)
```jsonc
{
  "character_id": "eve",
  "summary": "TL;DR of 8 popped messages",
  "created_at": "ISO"
}
```

- Relationships (if external memory manager is present)
```jsonc
{
  "affection": 0.72, "trust": 0.55, "tension": 0.05, ...
}
```

---

## 4. Prompt Assembly & Context Budgeting

Implemented in `Character._build_prompt_with_memories()` and `Character.respond()`:
- Persona/system: `base_prompt` per character.
- Mood prefix: derived from `MoodState` (dominant axis → adjective, with qualifier by magnitude).
- Memories:
  - If external `memory_manager` is present: `memory_manager.prompt_segment(char_id)` is appended verbatim.
  - Else fallback: top-K in-object memories by decayed `weight` and non-zero `sentiment`.
- Episodic retrieval: `EpisodicStore.search(char_id, user_message, k=3)` → “Relevant summaries:” section.
- Short-term window: keeps last `EpisodicStore.WINDOW_SIZE` messages; on overflow, pops and summarizes via `Summarizer` into episodic store.
- History shaping: last ~5 recent messages are included as chat turns.
- Event context: if `memory_manager` exposes pending events/reminders, add an “IMPORTANT SCHEDULING INFORMATION” block.

Budgeting principles (see `docs/long_context.md`):
- Strict layer order: persona + mood + memory + episodic + short-window.
- Deterministic selection: no random sampling of summaries; bounded K.
- Compression: Summaries constrained to ≤~120 tokens each.

---

## 5. Routing Rules (`Router.route()`)

- Explicit mentions: `@name` forces inclusion of that character.
- Name mentions in text: `\b(eve|atlas)\b` selects mentioned names.
- Prefix cues: message starting with `eve:` or `atlas,` selects the name.
- Fuzzy heuristics: common short forms and difflib close matches add candidates.
- LLM decision: if above do not decide, uses `ROUTER_MODEL` via `get_llm()` and a JSON contract `{ "character_ids": ["eve"] }`.
- Group/plural cue handling: if LLM returns exactly one but message has plural cue (e.g., “друзья/вы все/guys/folks”) → system expands to all valid characters.
- Fallbacks: on LLM error → select both characters.

---

## 6. LangGraph Flow (`create_world_chat_graph()`)

Nodes and edges in `garden_graph/graph.py`:
- `route_message(state)`
  - Handles `/intimate on|off` and `/intimate model <name>` before routing.
  - Calls `Router.route()` → `active_characters` and `selected_characters`.
  - Auto-intimacy: if not active and `relationships[char].affection ≥ INTIMACY_AFFECTION_THRESHOLD` AND mood `arousal ≥ INTIMACY_AROUSAL_THRESHOLD` → set `intimacy_mode=true` and restrict to that single character.
  - If `memory_manager` exists: `analyze_message(...)` + `save_to_file(...)`.

- `character_{id}(state)`
  - If `intimacy_mode`: `IntimateAgent.respond(user_message, history)`; else `Character.respond(user_message, history)`.
  - Cost: records prompt/completion tokens (estimation `len(text)//4`) with category `intimacy` or `general`.
  - Appends assistant message to `message_history` with `role = characters[id].name`.

- `cross_talk_node(state)`
  - If ≥2 character responses: build a small prompt with others’ replies; if LLM returns “pass” or too short → skip; else append inline parenthetical.
  - Cost recorded per cross-talk.

- `collate_node(state)`
  - Merges `selected_characters` in order to final string.
  - Memory processing (if `memory_manager`):
    - `process_conversation_update(character_id, user_message, character_response, llm)` → may create memories.
    - `reflect(character_id, context, llm)` after integrating a little recent history.

Conditional routing:
- Entry: `router` → for each `active_characters`: `character_{id}` → back to `router` until empty → `cross_talk` → `collator` → END.

---

## 7. Intimacy Mode

User commands (handled in router/collator):
- `/intimate on` | `/intimate off`
- `/intimate model <name>`

Auto-switch (graph):
- On high affection (relationships) and high arousal (mood), enter `intimacy_mode` for the chosen character.

Execution:
- `character_node(...)` uses `IntimateAgent` when `intimacy_mode=true`.
- Cost category = `intimacy` (see `docs/costs.md`).

Safety & consent: see `docs/intimacy_mode.md`.

---

## 8. Cost Tracking

- `CostTracker.record(model, prompt_tokens, completion_tokens, category)` at each LLM call.
- Estimation currently uses `len(text)//4`; future work: use provider usage if available.
- Summaries:
  - total USD → `get_total_usd()`
  - per-model and per-category breakdowns → `get_model_breakdown()`, `get_category_breakdown()`
- Budget alerts and UI integration per `docs/cost_tracker.md` and `docs/costs.md`.

---

## 9. Memory & Long Context

- In-object legacy: `Character.memories` with exponential decay and top-K injection.
- External MemoryManager (if present): relationships, events/reminders, prompt segment injection, processing + reflection APIs invoked by `graph.py`.
- Episodic memory: window overflow → `Summarizer` → `EpisodicStore.add()`; retrieval by `search(..., k=3)`.
- End-to-end strategy: see `docs/memory_algorithm.md` and `docs/long_context.md`.

---

## 10. Security & Privacy

- API keys loaded via `config.py`/env; never persisted to chat logs.
- Logs redact PII by default; only debug prints in local dev.
- iOS Keychain for user-supplied provider keys; CloudKit sync opt-in.
- Intimacy Mode requires explicit consent (see doc) and is logged separately if enabled.

---

## 11. UX Flows (brief)

- Create/Configure character (MVP: Eve/Atlas): adjust prompt, model, temperature.
- Chat:
  - Type → Router chooses speaker(s) → replies stream (future UI) → cost chip updates.
  - `@name` and plural cues steer routing.
- Group dynamics: optional cross-talk adds short parenthetical comments.
- Intimacy: toggle via command; auto-switch based on relationship+mood thresholds.
- Import/Export: JSON chat bundles (see `docs/PRD.md` MVP), character JSON (signed for iOS).

---

## 12. Outsourcing Work Packages

1) Router & Heuristics
- Deliverables: `Router.route()` completion with tests for mentions, names, plural expansion, LLM fallback.
- Acceptance: unit tests pass; JSON contract robust; error fallbacks exercised.

2) Character Prompt & Context
- Deliverables: deterministic `Character._build_prompt_with_memories()`; episodic search integration; event context block; snapshot tests.
- Acceptance: snapshot suite stable; bounded token budget; top-K logic consistent.

3) Cross-talk Node
- Deliverables: prompt template, “pass” path, merge logic, costs.
- Acceptance: integration tests show cross-talk only when multi-speaker; latency target < 2.5s.

4) MemoryManager Integration
- Deliverables: implement `analyze_message`, `process_conversation_update`, `reflect`, reminders API; `prompt_segment(char_id)`; persistence.
- Acceptance: golden conversations create expected memories; reflection updates weights; reminders appear in prompt.

5) Intimacy Agent
- Deliverables: `IntimateAgent.respond()` with model selection, safety fuse, category tagging; CLI commands handled.
- Acceptance: `/intimate` commands work; auto-switch triggers at thresholds; audit log entries present.

6) Cost Tracker Enhancements
- Deliverables: provider-accurate usage parsing; CSV export; budget alerts.
- Acceptance: error <2% vs reference; alerts fire reliably; export schema documented.

7) Summarizer & Episodic Store
- Deliverables: `Summarizer.instance().summarize()`; `EpisodicStore.add/search/recursive_compact` with tests.
- Acceptance: overflow triggers; retrieval relevant; long chat stays within budget.

8) iOS Integration (streaming later)
- Deliverables: World chat UI + settings; Core Data mapping of messages/costs; CloudKit sync.
- Acceptance: Test plan targets met; no crashes 48h; accessibility AA.

---

## 13. Milestones (aligned P1–P9)

- P1 LangGraph PoC: Router routes; two stubs reply; 100% RouterNode tests.
- P2 Memory Core: Memory CRUD, decay, reflection tests pass.
- P3 Cost Tracker: Cost recorded; budget alert unit test.
- P4 Persistence & Sync: Core Data save/fetch; CloudKit sync in sim.
- P5 LangGraph MVP: End-to-end CLI chat green; Intimacy Mode auto-switch passes integration tests; tag v0.1.0.
- P6 iOS UI PoC: Send/receive text via LangGraph on device.
- P7 Image & Vision: Vision tags appear in messages.
- P8 Background & Push: Push notification after idle.
- P9 MVP Polish: No crash in 48h beta; accessibility AA.

---

## 14. Risks & Mitigations

- Token estimation inaccuracy → integrate provider usage; add guard rails on max tokens.
- Intimacy trigger false positives → expose thresholds; audit & manual override.
- Memory drift/overgrowth → caps + decay + recursive compaction; tests.
- Provider instability → retries, backoff, graceful fallbacks.

---

## 15. Test Plan (link)

See `docs/test_plan.md`. Ensure additional cases for cross-talk, `/intimate` commands, and episodic retrieval relevance.

---

## 16. Acceptance (MVP)

- Deterministic prompt assembly with bounded context.
- Router selects ≤2 characters; plural cue expansion works.
- Intimacy Mode toggles by command and auto-triggers per thresholds.
- Episodic summaries created on overflow and retrieved for relevance.
- Cost tracking recorded with per-category breakdown; budget alert works.
- All unit/integration tests pass; performance targets met.
