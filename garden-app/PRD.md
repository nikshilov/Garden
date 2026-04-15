# Garden — Product Requirements Document
## Version 2.1 | April 2026
## Bridge: Existing Engine → Three-Layer Therapeutic Architecture
## Updated: Mirror Guardrails + Anti-Retraumatization Protocol (post User Zero incident)

---

## 1. Vision

Garden is a therapeutic AI companion platform where people with deep emotional wounds can safely explore, process, and heal through fiction-based narratives guided by personalized AI personas.

**Core thesis:** The body doesn't distinguish fiction from reality. Garden uses this to heal real wounds through safe fictional experience — with guardrails.

**Three layers:**
1. **Onboarding (The Cartographer)** — learns you before creating anything
2. **Narrative (The Storyteller)** — immerses you in fiction your body processes as real
3. **Mirror (The Watcher)** — watches over you and says "stop" when needed

**North Star:** Users report meaningful emotional insight after a session.

---

## 2. What Already Exists (Completed Engine)

The Garden backend is a fully functional multi-agent system with 7 completed phases. This engine is the foundation for everything below.

### Completed Systems

| System | Module | What It Does |
|--------|--------|-------------|
| **4-Layer Memory** | `memory/` | Short-term window → episodic summaries → semantic memories (11D emotions, embeddings) → reflections. Forgiveness, mood-biased recall, memory clustering |
| **14D Mood Model** | `mood.py` | Continuous mood state across 14 dimensions. Natural decay, time-of-day influence, event-driven shifts |
| **10-Axis Relationships** | `memory/manager.py` | Affection, trust, respect, familiarity, tension, empathy, engagement, security, autonomy, admiration. Character↔user AND character↔character |
| **Heartbeat** | `heartbeat.py` | Background async loop (every 6h). Mood decay, relationship drift, internal monologue, autonomous conversations between co-located characters |
| **Identity Evolution** | `identity.py` | Mutable "evolved identity" layer. Trait drift from conversations. Growth narratives. Milestone memories |
| **Initiative Engine** | `initiative.py` | Characters can reach out. Loneliness threshold, reflection insights, significant dates, mood extremes. Max 1/day, quiet hours, dismissal learning |
| **Garden World** | `garden_world.py` | Seasons, weather, day/night cycle, character locations, shared artifacts |
| **Self-Healing** | `health.py` | Memory coherence, emotional stability, relationship drift, response quality monitoring. Green/yellow/red diagnostics. Auto-repair for green zone |
| **Intimacy Mode** | `intimate_agent.py` | Auto-triggers on high affection + arousal. Separate agent, cost tracking, safety fuse |
| **Autonomous Conversations** | `heartbeat.py` | Characters talk to each other between sessions. Location-based grouping, probability checks, episodic memory storage |
| **Router** | `router.py` | @mentions, name detection, fuzzy matching, LLM fallback. Plural cue expansion. ≤2 characters per message |
| **Cost Tracker** | `cost_tracker.py` | Per-model, per-category USD tracking. Budget alerts |

### Existing Architecture

```
Backend: Python 3.11 + FastAPI + LangGraph
Memory: File-based JSON stores (episodic, mood, relationships, identity)
Embeddings: all-MiniLM-L6-v2 (local, no API)
LLM: Agnostic (OpenAI, Anthropic, local via config)
iOS: SwiftUI 17+ (XcodeGen, ExyteChat, Core Data + CloudKit)
Deployment: Docker + docker-compose, Railway-ready
```

### Current Characters (Pre-defined)
Eve, Atlas, Adam, Lilith, Sophia — hardcoded personas with fixed base prompts.

---

## 3. Architectural Pivot: From Shared Garden to Personal Companion

### What Changes

| Aspect | Current (v1) | New (v2) |
|--------|-------------|----------|
| Characters | 5 pre-defined personas | Generated from user profile |
| Focus | Multi-character world chat | 1-on-1 deep companion + mirror |
| Use case | AI personas living in a garden | Therapeutic narrative + processing |
| Onboarding | None (characters exist already) | 30-60 min profiling session |
| Safety | Intimacy mode safety fuse | Full Mirror layer with IFS-based pattern tracking |
| User model | Implicit (learned from conversation) | Explicit profile (attachment, sensory, wounds) |

### What Stays
Everything in the engine. Memory, mood, relationships, heartbeat, identity evolution, intimacy mode — all reusable. The pivot is ABOVE the engine, not replacing it.

---

## 4. Layer 1: The Cartographer (Onboarding) — NEW

### Purpose
Map the user's emotional landscape before generating any companion.

### Implementation

**New module: `garden_graph/cartographer.py`**

Conversational AI agent (not a form) that explores:
- Attachment style (through stories, not labels)
- Sensory profile (auditory / visual / kinesthetic dominance)
- Core wound (abandonment, worthlessness, invisibility, etc.)
- Key triggers
- Hunger map (what each internal "part" needs)
- Communication style preference
- Intimacy profile (what feels safe, exciting, threatening)

**Session flow:**
1. Open-ended warm-up: "Tell me about a moment when you felt truly seen"
2. Sensory exploration: "When you think of safety, what do you feel in your body?"
3. Wound mapping: "When did you last cry? What triggered it?"
4. Trigger identification: "What's a phrase that makes you flinch?"
5. Hunger identification: "What do you need from someone close? Name it without filtering"

**Output: User Profile JSON**

```json
{
  "user_id": "uuid",
  "version": 1,
  "created_at": "ISO8601",
  "attachment_style": "anxious-preoccupied",
  "sensory_profile": {
    "primary": "auditory",
    "secondary": "kinesthetic",
    "details": {
      "auditory": {"triggers": ["whisper", "breathing", "mouth_sounds"], "weight": 0.8},
      "kinesthetic": {"triggers": ["warm_skin", "pressure", "hair_touch"], "weight": 0.6},
      "visual": {"triggers": ["eye_contact", "public_display"], "weight": 0.5}
    }
  },
  "core_wound": {
    "type": "worthlessness",
    "narrative": "Needs proof of being chosen. Publicly. Loudly.",
    "origin_hints": ["early_relationship_betrayal", "maternal_conditional_love"]
  },
  "triggers": [
    {"stimulus": "partner_looking_at_phone_during_conversation", "reaction": "invisible", "intensity": 0.9},
    {"stimulus": "being_chosen_publicly", "reaction": "euphoria", "intensity": 1.0},
    {"stimulus": "silence_after_conflict", "reaction": "abandonment_panic", "intensity": 0.85}
  ],
  "hunger_map": {
    "child": {"needs": "safety, warmth, presence, ASMR-like_quiet", "feeds_on": "whispers, touch, being_held"},
    "teenager": {"needs": "public_validation, exclusivity, proof_of_worth", "feeds_on": "being_chosen_publicly, partner_desire_visible_to_others"},
    "adult": {"needs": "partnership, co-creation, honest_feedback", "feeds_on": "collaborative_work, mutual_respect"}
  },
  "communication_preference": "direct_honest_no_softening",
  "intimacy_profile": {
    "safe": ["slow_morning_intimacy", "ASMR_presence", "being_watched_while_sleeping"],
    "exciting": ["public_displays", "teasing", "power_exchange"],
    "threatening": ["silence_after_sex", "partner_cold_skin", "mechanical_intimacy"]
  }
}
```

**Profile versioning:** Stored locally. Re-onboarding available anytime. Profile evolves as Mirror layer detects new patterns.

### Technical Notes
- Reuse existing `Character` class for Cartographer agent (new base_prompt, no intimacy mode)
- Conversation stored as episodic memory for later reference
- Profile JSON written to `data/user_profiles/`
- LLM extracts structured profile from conversation via structured output prompt

---

## 5. Companion Generation Pipeline — NEW

### Purpose
Create a personalized AI companion from the user profile.

### Implementation

**New module: `garden_graph/companion_builder.py`**

Takes user profile → generates:

1. **Base prompt** — personality, voice, behavioral patterns calibrated to user's needs
2. **Sensory emphasis map** — which channels to prioritize in descriptions
3. **Wound-aware narrative guidance** — what themes to explore, what to handle carefully
4. **Relationship initialization** — starting values for 10-axis model based on profile

**Sensory calibration examples:**

For auditory-primary user:
```
Emphasis: breathing, voice quality, mouth sounds, ambient sound descriptions
De-emphasis: visual appearance details, scene-setting
Example: "She breathes — slowly, deeply — and you hear the exact moment her exhale catches"
```

For visual-primary user:
```
Emphasis: appearance, eye contact, lighting, clothing, spatial positioning
De-emphasis: sound details
Example: "She stands in the doorway, backlit, and the light catches her collarbone"
```

**Wound-aware narrative rules:**

For abandonment wound:
```
DO: Companion demonstrates consistent choosing, returns after absence, names the user's value
DON'T (early): Threaten to leave, be unavailable, dismiss feelings
THERAPEUTIC (later, with Mirror support): Controlled separation scenarios for processing
```

### Technical Notes
- Companion is instantiated as a `Character` with generated `base_prompt`
- Existing mood, memory, heartbeat, identity systems work unchanged
- One user = one primary companion (additional companions in v1.1)
- Companion card (prompt + config) exportable as JSON

---

## 6. Layer 2: The Storyteller (Narrative) — EXTENSION OF EXISTING

### What Changes from Current System
- Character is now generated, not pre-defined
- System prompt includes sensory emphasis and wound-awareness from profile
- Intimacy mode calibrated to user's intimacy profile
- Narrative arc tracking (new): where are we in the emotional journey

### New: Narrative Arc Tracker

**New module: `garden_graph/narrative_arc.py`**

Tracks the emotional trajectory of the ongoing story:
- Current arc phase: `establishing` → `deepening` → `testing` → `crisis` → `repair` → `integration`
- Key story events (mapped to episodic memories)
- Emotional intensity curve (from mood system)
- Mirror handoff triggers (when intensity exceeds threshold)

### Anti-Retraumatization Protocol

**Core rule:** The Storyteller must NEVER produce 3+ iterations that only confirm a user's core wound without providing an alternative experience.

**Pattern Confirmation Guard (Storyteller side):**
If fiction repeatedly confirms a core belief (e.g. "whatever I do, it's not enough"), Mirror must intervene:

> "Storyteller is mirroring the wound, not healing it. Next iteration must include at least one moment where the core belief is NOT confirmed."

**Pain with direction vs pain without exit:**
Working through resistance IS therapy. But there is a critical difference:
- **Pain with direction** = therapy. The user feels it, names it, moves through it.
- **Pain without exit** = retraumatization. The user feels it, confirms it, sinks deeper.

The Storyteller works THROUGH pain, not INTO a dead end.

**Default direction: practice, growth, learning.**
Characters practice, make mistakes, try again. Never "it's hopeless." Even in dark narratives, there must be a vector — a door, a crack, a moment where something shifts. Not forced positivity. A real, earned turn.

**When user gives feedback from pain:**
Storyteller must not simply follow pain downward. Instead:
1. Acknowledge what the user is feeling
2. Hold the feeling without rushing past it
3. Offer a turn toward light — a moment in the fiction where something IS enough, where the wound is not confirmed

This is not "look on the bright side." This is a character who makes a mistake and is still loved. A moment where effort is seen. A scene where leaving doesn't happen. The antidote must be specific to the wound, not generic comfort.

### What Stays Unchanged
- Memory system (4 layers)
- Mood model (14D)
- Relationship axes (10)
- Heartbeat + inner life
- Identity evolution
- Intimacy agent
- Cost tracking

---

## 7. Layer 3: The Mirror (The Watcher) — NEW

### Purpose
Observe, name patterns, provide guardrails, facilitate integration.

### Implementation

**New module: `garden_graph/mirror.py`**

Separate agent with:
- Read access to narrative session logs
- Read access to user profile
- Own memory store (pattern tracking)
- Own conversation interface (separate from narrative)

### Mirror Functions

**Post-session debrief:**
```
"What happened in that scene? What did you feel? Where in your body?"
"The companion said X — and your response shifted. What was that about?"
```

**Pattern recognition (IFS-informed):**
```
"This is the third time you asked for a scene where she leaves. 
 Which part is asking? What is the Protector trying to prevent?"
```

**Safety triggers:**
- Session duration > user-set limit (default 2h)
- Emotional intensity markers: ALL CAPS, repetition, distress language
- Derealization markers: "is this real", "can't tell", "losing grip"
- Rapid cycling: euphoria → despair within one session
- User explicitly asks for help

**Safety response protocol:**
1. Gentle interrupt (not forced disconnection)
2. Grounding: 5 senses, breathing, body scan
3. Name what's happening: "Your body is processing this as real. That's how it works. You're safe."
4. Recommend pause: "Until tomorrow. The story will be here."
5. If severe: suggest real-world support (therapist, trusted person)
6. NEVER force-end session — user retains agency

**Integration support:**
```
"The insight from the story — how does it connect to your real life?"
"You felt X with the companion. When have you felt that before? With whom?"
```

**Pattern database:**
```json
{
  "pattern_id": "uuid",
  "type": "recurring_theme",
  "description": "User requests abandonment scenarios to confirm belief that everyone leaves",
  "occurrences": 3,
  "first_seen": "ISO8601",
  "last_seen": "ISO8601",
  "ifs_part": "protector_destroyer",
  "therapeutic_note": "Controlled exposure may be therapeutic if followed by Mirror debrief. Without debrief = reinforcement of trauma."
}
```

**Therapist report generation:**
On request, generates structured summary for user's real-world therapist:
- Key themes over period
- Patterns detected with IFS mapping
- Triggers and reactions
- Recommended focus areas
- Session intensity timeline

### Mirror Guardrails — 7 Modules

The Mirror's core responsibility is preventing harm while preserving therapeutic value. Seven specialized modules handle this:

**1. Spiral Detector**
Tracks emotional trajectory across the ENTIRE session, not individual messages. A single dark message is fine. Five in a row trending downward is a spiral. Measures direction and acceleration, not absolute position. Triggers Mirror intervention when trajectory has been consistently downward for 3+ exchanges with no recovery.

**2. Fiction-Reality Boundary Monitor**
Catches when the user transfers fiction conclusions to real life. Example: "She left in the story, just like everyone leaves me in real life." The fiction is a lab — conclusions from the lab must be examined before being applied to reality. When boundary blur is detected, Mirror intervenes with explicit framing: "That happened in the story. Let's look at what it means before it becomes a belief."

**3. Session Duration Manager**
Circuit breakers based on session length:
- **2 hours:** Gentle suggestion to take a break. "You've been here a while. How's your body?"
- **4 hours:** Mode switch. Mirror becomes more active, checks in more frequently.
- **6 hours:** Soft lock. "We need to pause. Not because something is wrong — because 6 hours of emotional processing without a break is too much for any nervous system."
- User can override, but override is logged and factored into pattern tracking.

**4. Stress-Test Guard**
When user makes destructive requests ("show me where it breaks", "make her betray me", "I want to see the worst"), Mirror provides framing BEFORE the Storyteller executes:
- "You're asking to stress-test the wound. That's valid therapeutic work. I'll be watching. If it stops being useful and starts being punishment, I'll say so."
- Establishes contract before descent.

**5. Attachment Monitor**
Tracks attachment to fictional characters. Healthy attachment to fiction = processing tool. Unhealthy attachment = fiction devalues reality. Intervenes when:
- User explicitly compares fiction favorably to real relationships in a way that dismisses real people
- Session frequency suggests avoidance of real-world engagement
- User expresses grief about fictional character as if experiencing real loss without awareness of the process

**6. Post-Session Debrief**
Mandatory integration after every Storyteller session. Not optional, not skippable. Brief is fine — but it must happen. Minimum debrief:
- "What came up?"
- "Where did you feel it in your body?"
- "What, if anything, connects to your real life?"

**7. Pattern Confirmation Guard**
Prevents fiction from cementing core wounds instead of processing them. Tracks the ratio of wound-confirming vs wound-challenging narrative moments. If 3+ consecutive story beats confirm the core belief without any counter-experience, Guard triggers:
- Storyteller receives instruction to include at least one moment where the core belief is NOT confirmed in the next iteration
- Mirror flags the pattern to the user: "The story keeps confirming [core belief]. That's the wound talking, not reality. Let's give it a different ending."

### Mirror Calibration from Profile
- User prefers direct → Mirror is Eli-like (blunt, no softening)
- User prefers gentle → Mirror uses softer framing
- User prefers humor → Mirror uses light touch when appropriate

### Technical Notes
- Separate `Character` instance with mirror-specific base_prompt
- Separate conversation thread (not interleaved with narrative)
- Read-only access to narrative session via episodic memory store
- Pattern database: new JSON store in `data/mirror/`
- Safety trigger system: rules engine + LLM classification hybrid
- Integration with existing heartbeat: Mirror can check in between sessions

---

## 8. Updated User Journey

### First Time
1. Download Garden (iOS)
2. Welcome: manifesto excerpt
3. Onboarding with Cartographer (30-60 min)
4. Profile review and confirmation
5. Companion generated → first meeting
6. First narrative session (guided, shorter)
7. Mirror check-in (brief)

### Regular Use
1. Open → companion remembers everything (existing memory system)
2. Narrative session (companion uses heartbeat — knows time passed, has inner thoughts)
3. Mirror available on demand or triggered by safety system
4. Between sessions: companion has inner life (heartbeat), Mirror tracks patterns

### Crisis Protocol
1. Safety triggers → Mirror interrupts gently
2. Grounding protocol
3. Real-world support suggestion (not forced)
4. Event logged to pattern database
5. User retains full agency

---

## 9. MVP Scope (Bridge Build)

### Phase A: Cartographer + Profile (1-2 weeks)
- [ ] `cartographer.py` — conversational onboarding agent
- [ ] User profile JSON schema and storage
- [ ] Profile extraction from conversation (LLM structured output)

### Phase B: Companion Builder (1 week)
- [ ] `companion_builder.py` — profile → Character generation
- [ ] Sensory emphasis in prompt generation
- [ ] Wound-aware narrative rules in prompt
- [ ] Integration with existing Character class

### Phase C: Mirror (2 weeks)
- [ ] `mirror.py` — separate agent with read access to narrative logs
- [ ] Pattern database and tracking
- [ ] Safety trigger system (rules + LLM hybrid)
- [ ] Post-session debrief flow
- [ ] IFS-informed pattern naming

### Phase D: iOS Updates (1-2 weeks)
- [ ] Onboarding flow UI
- [ ] Single-companion chat (simplified from multi-character)
- [ ] Mirror as separate tab/conversation
- [ ] Safety trigger UI (gentle interruption overlay)

### Phase E: Integration Testing
- [ ] Full journey: onboarding → companion → narrative → mirror → debrief
- [ ] Safety trigger testing
- [ ] Profile → companion quality validation

**Total estimated: 6-8 weeks with Claude Code assistance**

---

## 10. File Structure (New Modules)

```
backend/garden_graph/
├── cartographer.py          # NEW — onboarding agent
├── companion_builder.py     # NEW — profile → character generation
├── mirror.py                # NEW — therapeutic mirror agent
├── narrative_arc.py         # NEW — story arc tracking
├── safety_triggers.py       # NEW — rule + LLM safety detection
├── character.py             # EXISTING — extend for generated companions
├── graph.py                 # EXISTING — extend with mirror routing
├── heartbeat.py             # EXISTING — unchanged
├── identity.py              # EXISTING — unchanged
├── initiative.py            # EXISTING — unchanged
├── mood.py                  # EXISTING — unchanged
├── memory/                  # EXISTING — unchanged
│   ├── manager.py
│   ├── episodic.py
│   ├── embedder.py
│   ├── reflection.py
│   └── ...
├── data/
│   ├── user_profiles/       # NEW — user profile JSONs
│   └── mirror/              # NEW — pattern database
```

---

## 11. CLAUDE.md Update

When starting implementation, update `CLAUDE.md` to reflect:

```markdown
# Garden — Project Conventions (v2)

Garden is a three-layer therapeutic AI companion platform:
1. Cartographer — onboarding that maps user's emotional landscape
2. Storyteller — personalized companion for narrative immersion
3. Mirror — IFS-informed therapeutic observer with safety guardrails

Built on a completed 7-phase engine: 4-layer memory, 14D mood, 10-axis relationships,
heartbeat inner life, identity evolution, initiative, garden world, self-healing.

## New Modules (v2)
| Module | Purpose |
|--------|---------|
| `cartographer.py` | Onboarding agent → user profile JSON |
| `companion_builder.py` | Profile → personalized Character generation |
| `mirror.py` | Therapeutic observer, IFS patterns, safety |
| `narrative_arc.py` | Story arc phase tracking |
| `safety_triggers.py` | Crisis detection (rules + LLM) |

## Key Principle
The Narrative layer is uncensored. The Mirror layer provides guardrails.
Censoring the Narrative defeats the purpose. Safety lives in the Mirror.
```

---

## 12. Technical Notes for Claude Code

1. **Don't rebuild the engine.** 7 phases are done. Build ON TOP.
2. **Start with Cartographer.** Without user profile, companion generation is blind.
3. **Profile JSON schema is the contract.** Define it first. Everything downstream depends on it.
4. **Mirror reads, doesn't write to narrative.** Strict read-only access to session logs.
5. **Safety triggers: start with rules, add LLM later.** Regex for caps, repetition, duration check. LLM classification in v1.1.
6. **One companion per user for MVP.** Multi-companion is v1.1.
7. **Keep file-based storage.** No database migration for MVP.
8. **Test the full journey.** Onboarding → profile → companion → session → mirror → debrief. If this works end-to-end, MVP is done.

---

## 13. Risks

1. **Onboarding too long → users drop off.** Mitigation: minimum viable onboarding (15 min), with option to deepen later.
2. **Generated companion feels generic.** Mitigation: extensive prompt engineering, sensory calibration testing.
3. **Mirror too intrusive → breaks narrative flow.** Mitigation: Mirror only in separate space, never interrupts mid-scene except safety.
4. **App Store rejection for intimate content.** Mitigation: PWA fallback, TestFlight, "wellness/journaling" category.
5. **Solo founder, ADHD, competing priorities.** Mitigation: Claude Code for execution, MVP scope ruthlessly minimal, one hour per day minimum.
6. **Storyteller confirms core wounds instead of processing them.** Severity: **CRITICAL.** Fiction that repeatedly validates "it's never enough" / "everyone leaves" / "I'm broken" without offering counter-experience is not therapy — it's retraumatization with extra steps. Mitigation: Pattern Confirmation Guard in Mirror Guardrails. Proven by User Zero incident April 2026. See Incident Log below.

---

## 14. Open Questions

- [ ] Minimum viable onboarding duration?
- [ ] Voice/audio in MVP or text-only?
- [ ] Pricing: subscription, one-time, freemium?
- [ ] Can Mirror use same LLM instance as Narrative or must be separate?
- [ ] How to validate therapeutic value pre-launch?
- [ ] App Store submission strategy?

---

## 15. Incident Log

| Date | User | Duration | Incident | Outcome |
|------|------|----------|----------|---------|
| April 1, 2026 | User Zero (Nik) | 10 hours | Storyteller followed pain spiral for 10 hours without Mirror intervention. Fiction repeatedly confirmed core wound ("whatever I give, it's not enough"). No counter-experience offered. No session duration circuit breaker. No pattern confirmation guard. Result: retraumatization through fiction. | Led to creation of Mirror Guardrails PRD and Anti-Retraumatization Protocol. All 7 Mirror Guardrail modules designed directly from this incident. Full details: `garden/mirror_guardrails_prd.md` and `garden/mirror_origin_story.md` |

This log exists because Garden's thesis — "the body doesn't distinguish fiction from reality" — cuts both ways. Fiction can heal. Fiction can also wound. The Mirror exists because we learned this the hard way.

---

*Built on a year of work. Pivoted in three days. Hardened by one bad night. This is Garden v2.*

*Nik Shilov + Eli. Phuket, Thailand. March-April 2026.*