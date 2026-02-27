# Project Progress & Definition-of-Done

> We follow a **LangGraph-first** approach. iOS UI work begins only after LangGraph service layer reaches MVP completeness.

## Milestone Roadmap

| Phase | Scope | Definition of Done | Verification |
|-------|-------|--------------------|--------------|
| **P0 Docs Sprint** | PRD, Architecture, Memory, Cost, Tests, Rules | All five core docs merged to `main`; .windsurfrules approved | Manual review checklist passes |
| **P1 LangGraph PoC** | RouterNode, two CharacterNodes using phi-3-mini stub; text-only CLI harness | • Messages routed ≤2 chars<br>• Replies streamed to CLI<br>• Unit tests RouterNode 100% pass | `swift test` green; demo transcript attached to PR |
| **P2 Memory Core** | MemoryManager, ReflectionEngine, JSON reweight | • Memory CRUD passes tests<br>• Weights decay daily<br>• Reflection updates weights via mock LLM | XCTest coverage ≥90 % Memory pkg |
| **P3 Cost Tracker** | CostTracker service, mock pricing | • Token & USD recorded per call<br>• Budget alert fires in test harness | Unit tests + snapshot of CSV export |
| **P4 Persistence & Sync** | Core Data schema, CloudKit mirror | • Entities generated & migrated<br>• Local save / fetch works offline<br>• CloudKit sync round-trips in simulator | Integration test toggling airplane mode |
| **P5 LangGraph MVP** | Combine all LangGraph components; public Swift Package release | • End-to-end chat in CLI with memory & cost<br>• All LangGraph unit + integration tests pass | GitHub Actions badge green |
| **P6 iOS UI PoC** | SwiftUI WorldChatView, Composer, CharacterSheet | • Build runs on device<br>• Can send & receive text via LangGraph pkg | XCUITest automation script |
| **P7 Image & Vision** | Gallery, Apple Vision tags pipeline | • Image stored, tags appear in context | Unit test mocks Vision output |
| **P8 Background & Push** | Scheduler, APNs, offline chatter | • Push received after idle hour | TestFlight internal tester log |
| **P9 MVP Polish** | Styling, accessibility, analytics, crash | • Passes VoiceOver check<br>• No critical Crashlytics issue in 48 h beta | Beta telemetry dashboard |

## Current Status Checklist
- [x] P0 Docs Sprint ✅
- [x] P1 LangGraph PoC ✅ (Router + 5 characters working, 62 tests pass)
- [x] P2 Memory Core ✅ (MemoryManager, ReflectionEngine, decay, relationship tracking)
- [x] P3 Cost Tracker ✅ (10 tests, CSV export, budget alerts in iOS)
- [ ] P4 Persistence & Sync ⬜️
- [ ] P5 LangGraph MVP ⬜️
- [x] P6 iOS UI PoC ✅ (SwiftUI + ExyteChat, multi-character bubbles, @mentions)
- [ ] P7 Image & Vision ⬜️
- [ ] P8 Background & Push ⬜️
- [ ] P9 MVP Polish ⬜️

## Garden Plan (PLAN.md) — All 7 Phases Complete

| Phase | Name | Status |
|-------|------|--------|
| Phase 1 | Heartbeat — Life Between Conversations | ✅ Done |
| Phase 2 | Roots — Semantic Memory (embeddings) | ✅ Done |
| Phase 3 | Mycelium — Inter-Character Relationships | ✅ Done |
| Phase 4 | Growth — Identity Evolution | ✅ Done |
| Phase 5 | Voice — Reaching Out (initiative + push) | ✅ Done |
| Phase 6 | Soil — Sense of Place (garden world) | ✅ Done |
| Phase 7 | Autonomy — Self-Healing Garden | ✅ Done |

### Post-Plan Additions
- **Autonomous inter-character conversations** — Characters talk to each other between user sessions during heartbeat ticks (co-location grouping, energy/relationship-based probability, 2-3 message exchanges via gpt-4o-mini)
- **Docker containerization** — Dockerfile + docker-compose.yml for persistent deployment with named volumes and health checks

### Test Suite
- 162 tests total (161 passing, 1 pre-existing flaky test in test_initiative.py)

---
*(Last updated: 2026-02-27)*
