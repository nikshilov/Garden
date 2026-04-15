# Garden v2 — What's New

## The Pivot

Garden v1 was a multi-character world chat with 5 pre-defined AI personas (Eve, Atlas, Adam, Lilith, Sophia) living in a shared garden.

Garden v2 is a **three-layer therapeutic AI companion platform** where a personalized companion is generated from a deep emotional profile, guided by narrative immersion, and watched over by a therapeutic observer.

**Core thesis:** The body doesn't distinguish fiction from reality. Garden uses this to heal real wounds through safe fictional experience — with guardrails.

---

## Three Layers

### 1. The Cartographer (Onboarding)

Maps the user's emotional landscape through a warm, non-clinical conversational agent before generating any companion.

**6 stages:**

| Stage | Purpose |
|-------|---------|
| `warm_up` | Welcome, invite vulnerability |
| `sensory_exploration` | Body sensations, emotional weight |
| `wound_mapping` | Core emotional pain patterns |
| `trigger_identification` | Specific emotional triggers |
| `hunger_identification` | Unmet needs — child, teenager, adult parts |
| `summary` | Warm reflection of what was heard |

**Output:** A structured User Profile with attachment style, sensory profile, core wound, triggers, hunger map, communication preference, and intimacy profile.

### 2. The Storyteller (Narrative)

A personalized AI companion generated from the user profile, with:

- **Sensory calibration** — 5 channels (auditory, visual, kinesthetic, olfactory, gustatory) weighted to what moves the user most
- **Wound-aware narrative rules** — DO/DON'T/THERAPEUTIC guidance for 6 wound types (abandonment, worthlessness, invisibility, helplessness, betrayal, shame)
- **Attachment-aware behavior** — companion adapts to anxious, avoidant, secure, or disorganized attachment styles
- **Narrative arc tracking** — 6 therapeutic phases: establishing → deepening → testing → crisis → repair → integration
- **Mirror handoff triggers** — automatic detection of pattern recognition, wound activation, breakthrough moments, resistance, and integration readiness

All existing v1 systems work unchanged: 4-layer memory, 14D mood, 10-axis relationships, heartbeat inner life, identity evolution.

### 3. The Mirror (The Watcher)

An IFS-informed therapeutic observer that watches over the narrative and provides guardrails.

**Functions:**
- Post-session debrief — "What happened? What did you feel? Where in your body?"
- Pattern recognition — tracks recurring themes, names IFS parts (Protector, Exile, Manager, Firefighter, Self)
- Safety response — grounding, naming, pause recommendation, crisis resources
- Integration support — connecting fictional insights to real life
- Therapist report generation — structured summary with themes, patterns, triggers, recommendations

**The Mirror reads, never writes to narrative.** Strict separation.

---

## Safety System

Rule-based crisis detection with 7 trigger types:

| Trigger | Severity | Detection |
|---------|----------|-----------|
| Distress language | HIGH / CRITICAL | 16 regex patterns ("want to die", "hurt myself", etc.) |
| Derealization | MEDIUM | "is this real", "losing grip", dissociation markers |
| Help request | HIGH | "I need help", "SOS", "I'm in crisis" |
| ALL CAPS abuse | LOW | >50% uppercase, min 10 chars |
| Repetition | MEDIUM | Same message 3+ times |
| Session duration | LOW / MEDIUM | Configurable limit (default 2h) |
| Rapid mood cycling | MEDIUM | Valence swings >0.6 between snapshots |

**Safety response protocol:**
1. Gentle interrupt (never forced disconnection)
2. Grounding — 5 senses, breathing, body scan
3. Name what's happening without dramatizing
4. Recommend pause — suggest, don't demand
5. If severe — provide real-world support resources
6. **NEVER force-end session** — user always retains agency

---

## New Modules

| Module | Purpose |
|--------|---------|
| `cartographer.py` | Conversational onboarding agent → user profile |
| `user_profile.py` | Pydantic models + JSON persistence for user profiles |
| `companion_builder.py` | Profile → personalized Character generation |
| `narrative_arc.py` | 6-phase story arc tracking with mirror handoff |
| `mirror.py` | IFS-informed therapeutic observer + pattern database |
| `safety_triggers.py` | Rule-based crisis detection (7 trigger types) |

---

## New API Endpoints (14)

### Onboarding
| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/onboarding/start` | Start cartographer session |
| `POST` | `/onboarding/message` | Send message, get cartographer response |
| `POST` | `/onboarding/complete` | Extract and save user profile |

### Profile
| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/profile/{user_id}` | Get user profile |
| `PUT` | `/profile/{user_id}` | Update profile fields |

### Companion
| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/companion/generate` | Generate companion from profile |
| `GET` | `/companion/{user_id}` | Get companion config |

### Narrative
| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/narrative/{user_id}/arc` | Get narrative arc state + mirror triggers |

### Mirror
| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/mirror/message` | Send message, get therapeutic response |
| `GET` | `/mirror/patterns/{user_id}` | Get detected IFS patterns |
| `POST` | `/mirror/patterns/{user_id}` | Record a new pattern |
| `POST` | `/mirror/debrief/{user_id}` | Start post-session debrief |
| `GET` | `/mirror/report/{user_id}` | Generate therapist report |
| `POST` | `/mirror/safety-check` | Manual safety check |

---

## Data Storage

New file-based JSON stores:
- `data/user_profiles/` — user profile JSONs
- `data/companions/` — companion configuration JSONs
- `data/narrative_arcs/` — narrative arc state per user
- `data/mirror/` — IFS pattern database per user

---

## Tests

184 new tests across 6 test files. Total: **379 passing** (8 pre-existing embedder failures unrelated to v2).

| Test File | Count | Covers |
|-----------|-------|--------|
| `test_user_profile.py` | 14 | Schema, persistence, versioning |
| `test_cartographer.py` | 25 | Session flow, stages, profile extraction, API |
| `test_companion_builder.py` | 36 | Build, prompts, relationships, wounds, sensory |
| `test_narrative_arc.py` | 29 | Phases, advancement, crisis detection, handoff |
| `test_mirror.py` | 34 | Patterns, Mirror agent, reports, IFS |
| `test_safety_triggers.py` | 46 | All 7 trigger types, severity levels |

---

## What's Unchanged

The entire v1 engine runs as before:
- 4-layer memory (short-term → episodic → semantic → reflections)
- 14D mood model with natural decay
- 10-axis relationship system
- Heartbeat background life engine
- Identity evolution and trait drift
- Initiative engine
- Garden world (seasons, weather, locations, artifacts)
- Self-healing diagnostics
- Autonomous inter-character conversations
- Cost tracking
- All original API endpoints

v2 is built **on top**, not replacing.

---

## What's Next (Phase D)

iOS app updates:
- Onboarding flow UI (Cartographer)
- Single-companion chat (simplified from multi-character)
- Mirror as separate tab/conversation
- Safety trigger UI (gentle interruption overlay)

---

*Garden v2. Phuket, Thailand. March 2026.*
