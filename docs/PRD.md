# Multi-Agent World Chat – MVP

## Goal
Build an iOS application where a user chats in a single “world” with multiple AI characters. Each character owns its prompt and a weighted emotional memory that shapes future replies. The first public milestone (MVP) aims to prove:
1. Natural, concise multi-character dialogue orchestrated by an on-device router LLM.
2. Emotional memory that updates after important events and influences tone.
3. Transparent token/​USD cost tracking.
4. Local Core Data persistence with optional iCloud sync.

## Personas (MVP)
| Persona | Motivation |
|---------|------------|
| **Chatty Explorer** | Enjoys casual conversation with unique AI beings. |
| **Role-Player** | Wants to test story ideas with adaptive characters. |
| **Cost-Conscious Power User** | Experiments with multiple LLM models and tracks spend. |

## Scope (MVP)
Feature | In / Out
---|---
World chat timeline (text + images) | **In**
Two built-in AI characters (Eve & Atlas) | **In**
Router LLM (phi-3-mini) | **In**
Optional high-end per-character models (GPT-4.1, Sonet-3.7) | **In** (user key)
Weighted emotional memory per character | **In**
Reflection after event → prompt update | **In** (simple heuristic)
Token & USD counter | **In**
Import / export chat (.json) | **In** (manual share sheet)
Import / export character (.json) | **In** (signed, local only)
Local Core Data + CloudKit sync | **In** (opt-in)
Push notifications for character pings | **In**
Custom themes | **Out** (only default “Ethereal”) 
Public backend / social sharing | **Out** for MVP
Subscriptions & billing | **Out**

## Success Metrics
• 90% of test chats < 3 sec total response latency.
• 80% of users perceive character memory (“Eve remembers my insult”).
• Router selects ≤ 2 characters for >95% of messages.
• MVP average chat cost <$0.01 per 50 messages (default models).

## Assumptions
• Users run iOS 17+ on A15 chip or newer (to fit tiny model).
• User supplies API keys for remote or high-end models (OpenAI GPT-4.1, Sonet-3.7, Anthropic, etc.).

## Risks & Mitigations
Risk | Mitigation
---- | ----------
Memory weight tuning too complex | Start with linear decay + unit tests.
Router mis-routes questions | Provide manual “@character” override.
Cost spikes with image recognition | Use on-device Vision framework only.
High-end LLM usage becomes expensive | Default to small model; show budget alerts.

## Open Questions
1. Minimum offline background-chatter frequency?
2. Exact animation style for “ethereal” look?
3. Legal wording for memory storage & privacy consent?

---
*(Last updated: 2025-05-21)*
