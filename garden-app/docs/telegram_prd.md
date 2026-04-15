# Garden Telegram Bot & Mini App — PRD

Status: Draft for review (Doc-first)
Owner: GardenCore
Last updated: 2025-08-25

---

## 1. Purpose & Goals
Build a Telegram experience for Garden where each bot represents a single character/personality. For MVP we publish two bots: Eve and Adam. Users chat in DM with a bot; the bot replies with memory and mood influence, provides settings, and emits service messages about memory/relationship updates. Advanced settings live in a Telegram Mini App.

Top goals (MVP):
- Natural DM conversation per bot/personality.
- Deterministic prompt assembly using Garden LangGraph components where applicable.
- Per-user memory and mood effects; service messages when memory/relationship change.
- Settings: model selection, view/clear memory, toggle notifications.
- Cost visibility (lightweight): on-demand command and daily summary.

Non-goals (MVP):
- Group chats, inline mode, marketplace, billing/subscriptions.
- Intimacy Mode (postponed due to Telegram policy; could be opt-in later with strict consent).

References:
- Core system: `backend/garden_graph/`
- Memory & relationships: `docs/emotional_memory.md`, `docs/memory_algorithm.md`
- Cost tracking: `docs/cost_tracker.md`, `docs/costs.md`
- Long context: `docs/long_context.md`

---

## 2. Architecture Overview
- Two bots (one persona each):
  - `EVE_BOT_TOKEN` (BotFather) → persona: Eve
  - `ADAM_BOT_TOKEN` (BotFather) → persona: Adam
- Single backend service handles both via separate webhook paths:
  - `POST /tg/webhook/eve`
  - `POST /tg/webhook/adam`
- LangGraph-first orchestration:
  - No router LLM in MVP (single persona per bot).
  - Use `Character.respond()` pipeline: persona prompt + mood + memories + episodic summaries + short window.
- Persistence:
  - Per-user state keyed by Telegram `user_id`.
  - Memory/Mood/Episodic stores under `backend/data/telegram/<persona>/<user_id>/...` (file-based MVP; can swap to DB later).
  - Cost records persisted similarly.
- Settings storage:
  - `settings.json` per `(persona, user_id)` with: `model`, `temperature`, `notifications`, `service_messages`, `language`.
- Mini App (Telegram WebApp) for settings:
  - Launched from `/settings` via `KeyboardButton.web_app`.
  - Served from backend (`/tg/app/`), authenticated via Telegram WebApp init data.

---

## 3. Bot UX & Commands
- `/start` — greet, brief persona intro, hint `/help` and `/settings`.
- `/help` — show commands and link to Mini App.
- `/settings` — inline keyboard with quick toggles + open Mini App.
- `/model` — choose LLM model (preconfigured list available on backend).
- `/memory` — show top-3 recent memories; buttons: "View all" (Mini App), "Clear" (confirm).
- `/clear` — confirm to clear per-user memory for this persona.
- `/cost` — show session & monthly USD estimates and token counts.
- `/export` — send JSON bundle of chat + memory (per-user scope).

Inline keyboard (quick settings):
- Toggle service messages: ON/OFF
- Toggle cost summaries: ON/OFF
- Open Mini App

---

## 4. Service Messages (System Notifications)
Purpose: transparency about internal state updates without polluting the main narrative.

Types and format (RU examples):
- Memory added
  - `📌 Память добавлена:` «{summary}» (вес {w})
- Relationship axis changed (top deltas)
  - `❤️ Доверие +0.08 → 0.71`
  - `🤝 Уважение +0.05 → 0.62`
- Mood shift (optional)
  - `🌤️ Настроение обновлено: валентность +0.2`
- Cost checkpoint (on-demand or daily)
  - `💰 Сессия: 1,230 ток. ≈ $0.004 | Месяц: $0.37`

Controls:
- Per-user toggles in settings: `service_messages` ON/OFF, `cost_summaries` ON/OFF.
- Rate limit: collate multiple small deltas into one message when necessary.

---

## 5. Mini App (Settings UI)
- Launch: from `/settings` via `KeyboardButton.web_app`.
- Screens:
  1) Model & Generation
     - Model (select: `gpt-4o`, `gpt-4.1-turbo`, `sonnet-3.7`, others configured)
     - Temperature slider
  2) Memory
     - List recent memories, search by text
     - Clear memory (confirm)
  3) Notifications
     - Service messages ON/OFF
     - Cost summaries ON/OFF
  4) About persona
     - Persona description; last mood snapshot
- API (backend):
  - `GET /tg/api/settings?persona=&user_id=`
  - `POST /tg/api/settings/update`
  - `GET /tg/api/memory/list?persona=&user_id=&q=&limit=`
  - `POST /tg/api/memory/clear`
- Auth: verify Telegram init data hash per WebApp docs; tie to `user_id`.

---

## 6. Prompt Assembly & Context
- Persona system prompt: unique per bot (Eve/Adam).
- Mood prefix based on per-user mood vector.
- Memory injection:
  - Use external `MemoryManager` if available; else in-object top-K by decayed weight.
- Episodic retrieval via `EpisodicStore.search(..., k=3)`.
- Short-term window: last ~5-8 turns to keep token budget small.
- Determinism: bounded K, fixed order, compression per `docs/long_context.md`.

---

## 7. Cost Tracking
- Record per call: model, prompt/completion tokens (est.), USD.
- Commands `/cost` and daily summary (if enabled).
- Storage under per-user directory; export includes cost metadata.

---

## 8. Data Model (Telegram)
- `UserSettings` (per persona + user)
  - `model: string`, `temperature: float`, `service_messages: bool`, `cost_summaries: bool`, `language: string`.
- `MemoryRecord` — per `docs/emotional_memory.md` (subset ok for MVP)
- `RelationshipProfile` — per axes with decay (subset ok for MVP)
- `CostRecord` — per `docs/cost_tracker.md`

---

## 9. API & Webhook Contracts
- Webhook request: Telegram Update JSON (DM only in MVP).
- Reply: Telegram `sendMessage` with Markdown; service messages use a subtle prefix (e.g., `—` or icon). Consider thread separation later.
- Mini App APIs: JSON over HTTPS as listed above.

---

## 10. Security & Privacy
- Store Bot tokens in ENV, never log raw tokens.
- Validate Telegram signatures for WebApp init data.
- PII minimization: only store `user_id` and chat history needed for memory.
- GDPR: add `/export` and `/clear` to satisfy portability/erasure.

---

## 11. Metrics & Success
- P95 reply latency < 3s for short prompts (excluding provider tail events).
- ≥80% of pilot users perceive memory influence.
- Error rate (failed deliveries) < 1%.
- Opt-out rate for service messages < 30% (tuned via rate limiting).

---

## 12. Milestones & Acceptance (MVP)
- M1: Two bots respond in DM; persona prompts wired.
- M2: Per-user memory save/retrieve; service messages for memory/relationship.
- M3: Settings (inline + Mini App basic) with model selection and toggles.
- M4: Cost tracking + `/cost` + export.
- M5: Test suite + CI + deploy (staging → prod)

Acceptance:
- Deterministic prompt assembly; memory and episodic retrieval bounded.
- Settings persist per `(persona, user_id)` and correctly change behavior.
- Service messages accurate and rate-limited.
- Export/clear commands function safely.

---

## 13. Risks & Mitigations
- Provider usage mismatches → parse provider usage when available; cap tokens.
- Service message noise → batch deltas; allow per-type toggle.
- Abuse/spam → simple rate limits per user; blocklist if needed.
- Telegram policy constraints → keep NSFW features out in MVP; document consent flows if later added.

---

## 14. Out of Scope (MVP)
- Group chat routing, inline mode, payments, marketplace, Intimacy Mode.

---

## 15. Test Plan
- Unit: settings parsing, memory add/clear, cost calc, service message formatter.
- Integration: webhook → reply, memory updates with deltas, Mini App auth.
- E2E: scripted DM flows for Eve and Adam; export/clear works; toggles respected.
