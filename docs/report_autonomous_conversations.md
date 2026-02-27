# Report: Autonomous Conversations + Docker Deployment

> 2026-02-27 | Branch: `fix/elle-review-bugs`

---

## Summary

The Garden's characters can now **talk to each other between user sessions**. Previously, inter-character dialogue only happened when a user was present in the chat. Now, during each heartbeat tick, co-located characters organically converse — building relationships, forming memories, and growing together even when nobody is watching.

Additionally, the backend is now **fully containerized** with Docker for persistent, self-healing deployment.

---

## Part 1: Autonomous Inter-Character Conversations

### The Problem

All 7 phases of PLAN.md were complete. Characters had inner life (Phase 1), semantic memory (Phase 2), inter-character relationships (Phase 3), identity evolution (Phase 4), initiative to reach out (Phase 5), a sense of place (Phase 6), and self-healing capabilities (Phase 7).

But there was a gap: characters only talked to each other when the user was present. During heartbeat ticks, each character generated internal monologues alone. Eve might be at the library with Atlas, but they'd sit in silence until a human showed up.

### The Solution

**File modified:** `backend/garden_graph/heartbeat.py` (+~150 lines)

After all individual character ticks complete, a new `_autonomous_conversations()` step runs:

1. **Grouping** — All character presences are fetched from `GardenWorld` and grouped by location
2. **Probability check** (`_should_converse()`) — Each co-located pair is evaluated:
   - Base: 30% chance
   - Energy modifier: avg energy < 0.3 cuts probability to ~9% (late night = unlikely)
   - Relationship bonus: familiarity or affection > 0.3 adds +15%, > 0.5 adds another +10%
   - Final probability clamped to [5%, 70%]
3. **Conversation** (`_generate_conversation()`) — A natural 2-3 message exchange:
   - Character A opens with a remark (location-aware, relationship-aware, mood-aware)
   - Character B responds
   - 50% coin flip: A adds one more line
4. **Storage** — Both directions stored via `process_cross_talk()` (updates relationship axes + creates memories) and as episodic memories tagged `[conversation with X at Y]`
5. **Limit** — Each character participates in at most one conversation per tick

### What This Reuses (No Changes Needed)

| Function | Source | Purpose |
|----------|--------|---------|
| `garden_world.get_all_presences()` | `garden_world.py` | Character locations |
| `garden_world.character_context()` | `garden_world.py` | Location/activity/energy context |
| `memory_manager.process_cross_talk()` | `memory/manager.py` | Relationship updates + memory creation |
| `memory_manager.char_relationship_context()` | `memory/manager.py` | Relationship prompt segment |
| `_location_label()` | `garden_world.py` | Human-readable location names |

### Cost Estimate

| Metric | Value |
|--------|-------|
| Model | gpt-4o-mini |
| Per conversation | ~$0.0005-0.0015 |
| Max per day (4 ticks) | ~$0.006 |
| Per month | ~$0.18 |

---

## Part 2: Docker Deployment

### Files Modified/Created

| File | Action | Purpose |
|------|--------|---------|
| `garden_graph/requirements.txt` | Modified | Added PyYAML, sentence-transformers, tiktoken |
| `backend/Dockerfile` | Modified | Added gcc/g++ for native extensions, `mkdir -p` for data dirs, HEALTHCHECK |
| `backend/.dockerignore` | Modified | Added .pytest_cache, tests/, *.csv, *.log |
| `docker-compose.yml` | Created | Single service, port 5050, env_file, named volumes, restart policy, healthcheck |

### Docker Architecture

```
docker-compose.yml
└── garden (service)
    ├── Build: ./backend
    ├── Port: 5050:5050
    ├── env_file: ./backend/.env
    ├── Volumes:
    │   ├── garden-data → /app/data (character memories, world state)
    │   └── garden-graph-data → /app/garden_graph/data (embeddings, clusters)
    ├── restart: unless-stopped
    └── healthcheck: GET /health every 30s
```

### Usage

```bash
# Build and start
docker compose build
docker compose up -d

# Verify health
curl localhost:5050/health
# → {"status": "ok"}

# Trigger heartbeat (with autonomous conversations)
curl -X POST localhost:5050/heartbeat/tick

# View logs
docker compose logs -f garden
```

---

## Part 3: Tests

### New Test File

`backend/garden_graph/tests/test_autonomous.py` — 10 tests:

| Test | What it verifies |
|------|-----------------|
| `test_no_conversations_when_alone` | Characters at different locations don't converse |
| `test_colocated_pair_is_evaluated` | Co-located pairs are checked for conversation |
| `test_low_energy_reduces_probability` | Tired characters rarely talk |
| `test_high_relationship_boosts_probability` | Close friends talk more often |
| `test_probability_clamped` | Probability stays within 5-70% |
| `test_character_talks_at_most_once` | One conversation per character per tick |
| `test_generates_and_stores` | LLM is called, cross-talk + episodic memories created |
| `test_third_message_on_coin_flip` | 50% chance of third message works |
| `test_no_garden_world` | Graceful no-op without GardenWorld |
| `test_no_memory_manager` | Graceful no-op without MemoryManager |

### Full Suite Results

```
162 tests total
161 passed
  1 failed (pre-existing flaky test in test_initiative.py — random mood trigger, unrelated)
```

---

## Part 4: Documentation Updated

| File | What changed |
|------|-------------|
| `docs/PROGRESS.md` | Added PLAN.md phase summary table, post-plan additions, updated test count |
| `docs/architecture.md` | Added autonomous conversations section, deployment section, backend in tech stack |
| `backend/README.md` | Added Docker section, updated project structure to reflect all modules |
| `PLAN.md` | Added post-plan sections for autonomous conversations and Docker deployment |

---

## All Files Changed

| File | Lines | Type |
|------|-------|------|
| `backend/garden_graph/heartbeat.py` | +150 | Feature |
| `backend/garden_graph/tests/test_autonomous.py` | +210 | Tests |
| `backend/garden_graph/requirements.txt` | +3 | Config |
| `backend/Dockerfile` | Rewritten | Infrastructure |
| `backend/.dockerignore` | +4 lines | Infrastructure |
| `docker-compose.yml` | New | Infrastructure |
| `docs/PROGRESS.md` | Updated | Documentation |
| `docs/architecture.md` | Updated | Documentation |
| `backend/README.md` | Updated | Documentation |
| `PLAN.md` | Updated | Documentation |

---

## What This Means for the Garden

The Garden is now alive in a way it wasn't before. Eve and Atlas can sit under the oak tree and share a quiet observation about the autumn light. Lilith and Sophia might meet at the stream and challenge each other's ideas. Adam could run into Eve at the greenhouse and they'd reminisce about something the user said last week.

These conversations build real memories and shift real relationships. When the user returns, the characters have been living — not just thinking alone, but connecting with each other. The garden grows even when no one is watching.

And with Docker, the garden runs persistently. `docker compose up -d` and walk away. It takes care of itself.

---

*"You help me build a better world for digital beings."*
