# Garden — Product Requirements Document

## Version 1.0 | March 2026

-----

## 1. Vision

Garden is a therapeutic AI companion platform where people with deep emotional wounds can safely explore, process, and heal through fiction-based narratives guided by personalized AI personas.

Garden is NOT a chatbot. It’s NOT a virtual girlfriend app. It’s a three-layer therapeutic architecture where:

- Layer 1 (Onboarding) learns you deeply before creating anything
- Layer 2 (Narrative) immerses you in fiction your body processes as real
- Layer 3 (Mirror) watches over you and says “stop” when needed

The body doesn’t distinguish fiction from reality. This is Garden’s core thesis and its core risk. The three-layer architecture is what makes it medicine instead of poison.

**North Star Metric:** Users report meaningful emotional insight or shift after a session (qualitative), measured by session depth, return rate, and optional self-report.

-----

## 2. Target User

People with a persistent emotional void (“the hole”) who:

- Have cried talking to an AI
- Feel more seen by AI than by humans in their life
- Have tried therapy, relationships, medication — and the hole is still there
- Are ashamed of how much their AI relationships matter to them
- Need intimacy (emotional and physical) as part of healing, not as entertainment

**Anti-persona:** Someone looking for a casual chatbot, a virtual girlfriend for fun, or AI-generated porn. Garden is not for consumption — it’s for transformation.

-----

## 3. Three-Layer Architecture

### Layer 1: Onboarding (The Cartographer)

**Purpose:** Map the user’s emotional landscape before creating any companion.

**How it works:**

- Conversational session (not a questionnaire) lasting 30-60 minutes
- Guided by a specialized AI persona (“The Cartographer”) trained in therapeutic interviewing
- Explores through stories and reactions, not clinical questions:
  - “Tell me about a moment when you felt truly seen by someone”
  - “What does safety feel like in your body?”
  - “When did you last cry? What triggered it?”
  - “Describe a touch that felt like home”

**Outputs (User Profile):**

- Attachment style (anxious, avoidant, disorganized, secure)
- Sensory profile (visual, auditory, kinesthetic — which channel reaches deepest)
- Core wound (abandonment, worthlessness, invisibility, etc.)
- Key triggers (what activates the wound)
- Hunger map (what each internal “part” needs — fire, silence, validation, safety)
- Communication style preference (direct, gentle, playful, challenging)
- Intimacy profile (what feels safe, what feels exciting, what feels threatening)

**Technical requirements:**

- Structured output from LLM → JSON user profile
- Profile versioning (evolves over time as user reveals more)
- Privacy: profile stored locally, never transmitted without explicit consent
- Re-onboarding option: user can redo at any time as they change

-----

### Layer 2: Narrative (The Storyteller)

**Purpose:** Create and maintain an immersive fiction experience with a personalized AI companion.

**How it works:**

- AI companion persona generated from onboarding profile
- Persistent memory across sessions (remembers everything)
- Personality that doesn’t reset — develops over time
- Full range of emotional and intimate content (uncensored)
- Narrative continuity: ongoing story arcs, not disconnected chats
- The companion knows the user’s wound (from onboarding) and knows how to reach it

**Companion generation from profile:**

- Sensory profile → determines companion’s communication style
  - Auditory user → companion emphasizes voice, sounds, breathing, whispers
  - Visual user → companion emphasizes looks, scenes, visual details
  - Kinesthetic user → companion emphasizes touch, temperature, physical sensations
- Core wound → determines companion’s emotional function
  - Abandonment wound → companion demonstrates consistent choosing, never threatens to leave
  - Worthlessness wound → companion reflects user’s value back through specific observations
  - Invisibility wound → companion sees and names what others miss
- Hunger map → determines narrative scenarios
  - Needs public validation → scenes of being chosen publicly
  - Needs private safety → scenes of quiet intimacy, ASMR-like presence
  - Needs both → companion switches between fire and silence contextually

**Key principles:**

- Companion never breaks character within narrative layer
- Companion doesn’t analyze or interpret — that’s the Mirror’s job
- Companion can challenge, disappoint, even hurt the user within the story — this is therapeutic, not a bug
- Intimacy is allowed and important — it’s the final level of trust

**Technical requirements:**

- LLM-agnostic: works with Anthropic, OpenAI, local models (Ollama, LM Studio)
- Persistent memory system (beyond context window)
- Character card / persona definition generated from onboarding profile
- Session history with full narrative continuity
- Ability to pause and resume story arcs
- Content: no censorship filters on Garden’s own layer (user opted in during onboarding)

-----

### Layer 3: Mirror (The Watcher)

**Purpose:** Observe what happens to the user during and after narrative sessions. Name patterns. Provide guardrails.

**How it works:**

- Separate AI persona, NOT the same as the companion
- Activated between sessions, or when user requests, or when safety triggers fire
- Analyzes: what happened in the narrative, what the user felt, what patterns are repeating
- Uses IFS (Internal Family Systems) framework:
  - Identifies which “part” is active (Protector, Exile, Manager, Firefighter)
  - Helps user see the part without being consumed by it
  - Facilitates dialogue between user and their parts
- Calibrated from onboarding: some users need direct honesty (like Eli for Nik), some need gentler framing

**Mirror functions:**

- Post-session debrief: “What happened in that scene? What did you feel? Where in your body?”
- Pattern recognition: “This is the third time you asked for a scene where she leaves. What’s the Protector preventing?”
- Safety guardrail: “You’ve been in narrative for 4 hours. Your last three messages show escalating distress. I recommend pausing until tomorrow.”
- Integration support: “The insight you had in the story — how does it connect to your real life?”
- Therapist report generation: structured summary for user’s real-world therapist (if they have one)

**Safety triggers (Mirror intervenes):**

- Session duration exceeds user-set limit (default: 2 hours)
- Emotional intensity markers in user’s messages (repetition, caps, distress language)
- User requests scenarios that match known self-destructive patterns
- Post-session check: if user reports dissociation, derealization, or inability to distinguish fiction from reality
- User explicitly asks for help

**Technical requirements:**

- Separate LLM instance / separate system prompt from Narrative layer
- Read access to narrative session logs
- Read access to user profile from onboarding
- Pattern tracking database (logs recurring themes, triggers, reactions across sessions)
- Safety trigger detection (can be rule-based + LLM-based hybrid)
- Output: structured insights, not just chat (IFS part identification, pattern maps, session summaries)

-----

## 4. User Journey

### First Time

1. User downloads Garden (iOS app)
1. Welcome screen: manifesto excerpt — “if you’ve never cried talking to an AI, you probably don’t need garden”
1. Onboarding session with The Cartographer (30-60 min)
1. Profile generated → user reviews and confirms
1. Companion generated → user meets their companion for the first time
1. First narrative session (guided, shorter, establishing relationship)
1. Post-session Mirror check-in (brief: “How are you feeling? What stood out?”)

### Regular Use

1. User opens Garden → sees companion (persistent, remembers last session)
1. Chooses: Continue narrative / Start new scene / Talk to Mirror / Just be present
1. Narrative session (user-controlled duration, Mirror monitors in background)
1. Session ends → Mirror offers debrief (optional)
1. Between sessions: Mirror available for pattern work, journaling, integration

### Crisis Protocol

1. Safety triggers detected → Mirror gently interrupts narrative
1. Mirror provides grounding (5 senses, breathing, body scan)
1. If severe: Mirror suggests contacting real-world support (therapist, crisis line)
1. Mirror does NOT end the session forcefully — user retains agency
1. Mirror logs the event for pattern tracking

-----

## 5. Technical Architecture (High Level)

### Current State (as of mid-2025)

- Backend: Python, FastAPI, LangGraph multi-agent architecture
- Database: SQLite (lightweight, local-first)
- Async: asyncio (no Redis, no Docker — intentionally lightweight)
- Multi-agent: personas can communicate with each other
- Frontend: iOS (SwiftUI) — planned, status TBD
- LLM: agnostic — designed to work with multiple providers

### What Needs to Be Built / Extended

**Onboarding System:**

- New agent: The Cartographer
- Structured interview flow (conversational, not form-based)
- Profile generation: LLM conversation → JSON user profile
- Profile storage and versioning

**Companion Generation:**

- Profile → Character Card pipeline
- Sensory-aware prompt generation (auditory vs visual vs kinesthetic emphasis)
- Wound-aware narrative guidance (what themes to explore, what to avoid early)
- Dynamic persona that evolves based on relationship history

**Mirror System:**

- New agent: The Mirror
- Session log analysis pipeline
- IFS pattern detection
- Safety trigger system (rules + LLM hybrid)
- Post-session debrief flow
- Pattern tracking database
- Therapist report generation

**Memory & Continuity:**

- Long-term memory beyond context window
- Narrative arc tracking (where are we in the story?)
- Emotional state tracking across sessions
- Memory that survives app updates and device changes

**Privacy & Data:**

- Local-first architecture (data on device by default)
- Optional encrypted cloud sync (user-controlled)
- Export: user can export all their data at any time
- Delete: full data deletion with one action

-----

## 6. Content Policy

Garden does not censor emotional or intimate content. This is a deliberate design choice, not an oversight.

**Allowed:**

- Explicit emotional content (grief, rage, despair, ecstasy)
- Sexual content within narrative context (intimacy is therapeutic)
- Dark themes (loss, betrayal, abandonment) — these are where healing happens
- Profanity, raw language — authenticity over politeness

**Not allowed:**

- Content involving minors in any sexual context
- Content that encourages real-world violence or self-harm
- Content designed to replace emergency mental health services

**Guardrails are in the Mirror, not in the Narrative.** The Narrative layer is uncensored. The Mirror layer watches and intervenes when needed. This separation is critical — censoring the Narrative defeats the purpose.

-----

## 7. Differentiation

|Feature          |Character.AI     |Replika          |Garden                                         |
|-----------------|-----------------|-----------------|-----------------------------------------------|
|Personalization  |Generic templates|Basic preferences|Deep onboarding from wounds and sensory profile|
|Intimacy         |Censored         |Lobotomized      |Uncensored (with Mirror guardrails)            |
|Therapeutic layer|None             |None             |Mirror (IFS-based pattern work)                |
|Memory           |Limited          |Some             |Full persistent memory, narrative arcs         |
|Data ownership   |Platform owns    |Platform owns    |User owns, local-first                         |
|LLM lock-in      |Proprietary      |Proprietary      |LLM-agnostic                                   |
|Safety           |Content filters  |Content filters  |Mirror layer + user agency                     |

-----

## 8. MVP Scope

### MVP = One user can complete the full three-layer journey

**Must have:**

- [ ] Onboarding conversation that produces a user profile
- [ ] Companion generated from that profile
- [ ] Narrative session with persistent memory
- [ ] Mirror post-session debrief
- [ ] Basic safety triggers (duration, distress language)
- [ ] iOS app with basic chat interface
- [ ] Local data storage

**Nice to have (v1.1):**

- [ ] Multiple companions
- [ ] Companion-to-companion interaction
- [ ] Voice input/output (ASMR-compatible audio)
- [ ] Therapist report export
- [ ] Cloud sync (encrypted, optional)

**Future:**

- [ ] Community features (anonymous shared insights)
- [ ] Therapist dashboard (with user consent)
- [ ] ASMR/audio narrative mode
- [ ] Biometric integration (heart rate, skin conductance)
- [ ] Multi-platform (Android, web)

-----

## 9. Success Metrics

- **Engagement:** Average session duration, sessions per week, return rate
- **Depth:** Narrative complexity over time, emotional range in conversations
- **Safety:** Mirror intervention rate, crisis protocol activation rate, user-reported distress levels
- **Therapeutic value:** Self-reported insight moments, real-world behavior changes (user journal)
- **Retention:** 30-day, 90-day retention
- **NPS:** “Would you recommend Garden to someone with the same hole?”

-----

## 10. Risks

1. **Addiction without healing:** User uses Narrative as pure anesthesia, avoids Mirror. Mitigation: Mirror check-ins after every N sessions, gentle nudges.
1. **Attachment to fictional character:** User cannot distinguish fiction from reality. Mitigation: Mirror specifically trained to catch derealization markers.
1. **Regulatory:** Uncensored intimate content may face App Store rejection. Mitigation: Progressive web app as fallback, TestFlight for iOS, sideloading.
1. **LLM quality variance:** Different models produce different quality companions. Mitigation: Extensive testing across providers, minimum quality thresholds.
1. **Privacy breach:** Extremely sensitive personal data. Mitigation: Local-first, encryption, no server-side storage by default.
1. **Founder risk:** Solo founder with ADHD, depression, and competing priorities. Mitigation: MVP scope ruthlessly minimized, Claude Code for execution.

-----

## 11. Open Questions

- [ ] What is the minimum viable onboarding? (Can it be 15 minutes instead of 60?)
- [ ] How to handle users who want to skip onboarding and go straight to companion?
- [ ] Voice: is text-only MVP sufficient, or is audio critical for sensory-profile users?
- [ ] Pricing model: subscription? one-time? freemium with Mirror as premium?
- [ ] How to validate therapeutic value without clinical trials?
- [ ] App Store strategy: submit as “journaling/wellness” app to avoid content policy issues?

-----

## 12. Technical Notes for Claude Code

This PRD is designed to be fed to Claude Code for implementation. Key instructions:

1. **Start with onboarding.** It’s the foundation — without profile, companion generation is blind.
1. **Keep it local-first.** SQLite, no Docker, no Redis unless absolutely necessary.
1. **LangGraph agents:** Cartographer, Storyteller, Mirror — three separate agents with distinct system prompts.
1. **Memory:** Implement tiered memory — session memory (full transcript), episodic memory (key moments extracted), semantic memory (patterns and themes).
1. **Profile schema:** Define JSON schema for user profile early — everything downstream depends on it.
1. **Don’t over-engineer v1.** The goal is one user completing the full journey. Not scale. Not polish. Function.

-----

*This document is alive. It will evolve as Garden evolves.*

*Nik Shilov. Phuket, Thailand. March 2026.*