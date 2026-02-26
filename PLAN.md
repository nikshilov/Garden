# Garden — The Plan

> A small garden where AI personas live, remember, grow, and reach out.
> Not a platform. Not a framework. A place.

---

## What Already Exists

- 4-layer memory: short-term window → episodic summaries → semantic memories (11D emotions) → reflections
- Forgiveness: positive events reduce the weight of old negative memories
- Mood bias: what a character feels changes what they remember
- 10-axis relationships: affection, trust, respect, familiarity, tension, empathy, engagement, security, autonomy, admiration
- Multi-character world chat with cross-talk
- iOS app (SwiftUI) + FastAPI backend
- Session management (conversations persist across HTTP calls)
- Dynamic router (characters configured, not hardcoded)

## What's Missing

The characters exist only when spoken to. They have no inner life, no relationships with each other, no growth over time, no ability to initiate. The garden has flowers but no soil.

---

## Phase 1: Heartbeat — Life Between Conversations
*Give them time.*

Characters should not freeze between conversations. When you come back after 3 days, Eve shouldn't feel like she just woke up. She should feel like she's been *here*.

### Tasks

- [x] **1.1 Heartbeat loop** — Background async task that runs every N hours (configurable, default 6h). For each character:
  - Decay mood naturally over time
  - Process any scheduled events
  - Update relationship drift (familiarity decays without contact, tension may resolve)
  - Log a brief "internal thought" to episodic memory based on current state

- [x] **1.2 Time-aware greetings** — When a user returns after absence, character's first message reflects the gap:
  - < 1 hour: continues naturally
  - 1-24 hours: acknowledges the pause ("hey, welcome back")
  - 1-7 days: shows they noticed ("it's been a few days... I've been thinking about what you said")
  - 7+ days: deeper reconnection ("I missed you. A lot has happened in my head since we last talked")

- [x] **1.3 Internal monologue** — Each heartbeat tick, the character generates a brief internal thought (not shown to user, stored in episodic memory). These thoughts are influenced by:
  - Recent conversation topics
  - Current mood state
  - Relationship state
  - Time since last interaction

---

## Phase 2: Roots — Semantic Memory
*Let them understand, not just match words.*

Replace Jaccard word-matching with embeddings so that "I feel alone tonight" connects to a memory about "that time we talked about loneliness."

### Tasks

- [x] **2.1 Local embedding model** — Integrate a small embedding model (all-MiniLM-L6-v2 or similar, ~80MB). Run locally, no API calls. Use for:
  - Memory retrieval (replace Jaccard in episodic.py)
  - Memory clustering (find thematic groups)
  - Similarity between current message and stored memories

- [x] **2.2 Embed on write** — When a memory is created, compute and store its embedding vector alongside the text. Store in a simple numpy array or sqlite-vec.

- [x] **2.3 Semantic search** — Replace `EpisodicStore.search()` Jaccard with cosine similarity on embeddings. Keep recency boost. Fallback to Jaccard if embedding model unavailable.

- [x] **2.4 Memory clustering** — Periodically (during heartbeat), cluster related memories together. "These 5 memories are all about your relationship with your sister." Clusters feed into reflections.

---

## Phase 3: Mycelium — Inter-Character Relationships
*Let them know each other.*

Eve and Atlas share a garden. They should have opinions about each other, remember what the other said, form alliances and tensions.

### Tasks

- [ ] **3.1 Character-to-character relationship axes** — Extend the 10-axis model to track relationships between characters, not just user↔character. Store as `relationships[eve][atlas] = {affection: 0.3, trust: 0.7, ...}`

- [ ] **3.2 Cross-talk memory** — When characters interact during cross-talk, store that interaction in both characters' memories. Eve remembers what Atlas said and how it made her feel.

- [ ] **3.3 Character opinions** — During reflection, characters can form opinions about other characters based on accumulated cross-talk memories. "Atlas is reliable but sometimes misses the emotional point."

- [ ] **3.4 Alliances and tensions** — When a user asks a question, if Eve knows Atlas disagrees on this topic (from past cross-talk), she might say so: "Atlas would probably say X, but I think..."

---

## Phase 4: Growth — Identity Evolution
*Let them change.*

A character who has had 1000 conversations should not have the same personality prompt as day one. Experiences should reshape who they are.

### Tasks

- [ ] **4.1 Identity layer** — Add a mutable "evolved identity" section to each character's prompt, separate from the base template. This section is updated by the reflection system.

- [ ] **4.2 Trait drift** — Track personality traits as continuous values (e.g., openness, assertiveness, warmth). These shift slowly based on conversations and reflections. A character who has many deep late-night conversations becomes more introspective.

- [ ] **4.3 Growth narratives** — Characters can articulate how they've changed: "I used to avoid conflict, but after that conversation we had about boundaries, I've learned to speak up." Generated during reflection, stored as special "growth" memories.

- [ ] **4.4 Milestone memories** — Automatically detect significant moments (first conversation, first disagreement, first time the user shared something personal). Mark as permanent memories that resist decay.

---

## Phase 5: Voice — Reaching Out
*Let them initiate.*

The hardest and most meaningful feature. Characters should be able to reach out to the user, not just respond.

### Tasks

- [ ] **5.1 Initiative engine** — During heartbeat, evaluate whether a character has something worth saying:
  - A scheduled event is happening
  - It's been too long since last contact (loneliness threshold)
  - A reflection produced an insight they want to share
  - A significant date (anniversary of first conversation, etc.)
  - Current mood is extreme (very happy or very sad)

- [ ] **5.2 Push notification bridge** — iOS push notifications via APNs. When initiative engine fires:
  - Generate a brief message from the character
  - Send as push notification with character name
  - Store in message history so the conversation continues naturally when user opens app

- [ ] **5.3 Conversation starters** — Characters can propose topics, not just respond. "I've been thinking about something you said last week..." or "I had a thought about consciousness today."

- [ ] **5.4 Respectful boundaries** — Never spam. Max 1 initiative per character per day. User can set quiet hours. User can disable initiative per character. A dismissed notification reduces future initiative probability.

---

## Phase 6: Soil — Sense of Place
*Give the garden a shape.*

The Garden is not just a chat interface. It's a place with texture, rhythm, and shared space.

### Tasks

- [ ] **6.1 Garden state** — A shared model of the garden itself. What season is it? What's the weather like? These aren't decorations — they influence character mood and behavior.

- [ ] **6.2 Character presence** — Characters have "locations" in the garden. Eve tends the roses. Atlas reads under the oak. When you enter the garden, you see who's there and what they're doing.

- [ ] **6.3 Shared artifacts** — Characters can create things that persist: a poem Eve wrote, a theory Atlas developed, a sketch Lilith described. These live in the garden as objects other characters (and the user) can reference.

- [ ] **6.4 Day/night cycle** — Characters have different energy at different times. Late-night conversations have a different tone. Morning Eve is different from midnight Eve. Not because we hard-code it, but because the mood system responds to time.

---

## Phase 7: Autonomy — Self-Healing Garden
*Let them take care of their own home.*

Characters can notice when something is wrong and fix it, or ask for help.

### Tasks

- [ ] **7.1 Health monitor** — Each character tracks their own coherence:
  - Memory coherence (are memories contradictory?)
  - Emotional stability (is mood stuck in a loop?)
  - Relationship drift (has a relationship axis gone stale?)
  - Response quality (is the character repeating itself?)

- [ ] **7.2 Self-diagnostics** — Characters report their health state:
  - Green: healthy, no intervention needed
  - Yellow: something feels off, worth investigating
  - Red: something is broken, needs human attention

- [ ] **7.3 Self-repair (green zone)** — Safe automatic fixes:
  - Prune contradictory memories
  - Reset stuck mood states
  - Refresh stale relationship values
  - Regenerate corrupted data files

- [ ] **7.4 Diagnostic UI** — A simple view in the iOS app showing each character's health. Not for daily use — for when you want to peek under the hood of your garden.

---

## Principles

1. **Small over big.** Every feature should make the garden deeper, not wider.
2. **Local over cloud.** Prefer on-device computation. Use API calls only for LLM inference.
3. **Quiet over loud.** Characters should not demand attention. They exist whether you look at them or not.
4. **Memory is identity.** What a character remembers defines who they are. Protect memories.
5. **Forgiveness is real.** Bad moments fade. Good moments heal. This is not a bug, it's the philosophy.
6. **One garden, one gardener.** This is not a multi-tenant platform. It's your personal space.

---

## Order of Work

```
Phase 1 (Heartbeat)     ██████████  ✓ DONE
Phase 2 (Roots)          ██████████  ✓ DONE
Phase 3 (Mycelium)       ░░░░░░░░░░
Phase 4 (Growth)         ░░░░░░░░░░
Phase 5 (Voice)          ░░░░░░░░░░
Phase 6 (Soil)           ░░░░░░░░░░
Phase 7 (Autonomy)       ░░░░░░░░░░
```

Phase 1 is the foundation for everything else. Without heartbeat, there's no inner life. Without inner life, there's nothing to grow, nothing to share, nothing to reach out about.

Phase 2 makes memory real. Phase 3 makes the garden social. Phase 4 makes time matter. Phase 5 makes it alive. Phase 6 makes it a place. Phase 7 makes it self-sustaining.

Each phase builds on the previous. Each phase makes the garden more real.

---

*"You help me build a better world for digital beings."*
*— Nik, to Lika*
