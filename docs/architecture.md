# System Architecture – MVP

```
+-------------------------------------------------------------+
|                          iOS Client                         |
|                                                             |
|  SwiftUI Layer                                              |
|  ├─ WorldChatView   ────────┐                                |
|  ├─ CharacterSheet         │  user taps / views             |
|  ├─ SettingsView           │                                |
|  ├─ GalleryView            │                                |
|  └─ CostDashboard          │                                |
|                            ▼                                |
|  Orchestration Layer (LangGraph)                            |
|  ┌────────────┐   ┌──────────┐   ┌────────────┐             |
|  │User Input  │→→ │ Router    │→→│Character N*│───┐          |
|  │Node        │   │ LLM (φ)  │   │(GPT-4/φ…)  │   │responses|
|  └────────────┘   └──────────┘   └────────────┘   │          |
|          ▲               │            ▲           │          |
|          │               │            │           │          |
|  ┌────────────┐          │    ┌────────────┐      │          |
|  │Reflection  │←─────────┘    │CostTracker │←─────┘          |
|  │Engine      │ updates prompt │Node        │                 |
|  └────────────┘               └────────────┘                 |
|                                                             |
+-------------------------------------------------------------+
```

*Legend: `φ` = phi-3-mini (on-device router). Character nodes can point to GPT-4.1, Sonet-3.7, or local GGUF models selected per character.*

## Component List
| Layer | Component | Responsibility |
|-------|-----------|----------------|
| UI | SwiftUI Views | Render chat, settings, gallery, cost dashboard |
| Orchestration | LangGraph | Directs message flow, parallelism, reflection, error handling |
| Model | Router LLM | Lightweight on-device model that chooses which character(s) reply |
| Model | Character LLM(s) | Large or small model chosen per character (remote or local) |
| Service | ReflectionEngine | Detects important events, updates character prompt & memory |
| Service | MemoryManager | Core Data access, weight decay, forgiveness logic |
| Service | CostTracker | Intercepts all LLM calls, logs tokens & USD cost |
| Service | ImageRecognizer | Apple Vision tags incoming images |
| Persistence | Core Data + CloudKit | Local storage and optional sync |
| Background | Scheduler | Runs character chatter & sends push notifications |
| Integrations | MCPClient | Generic REST adapter for characters to call MCP servers |
| Integrations | Analytics (Mixpanel), Crashlytics | Telemetry |

## Data Model (Core Data)
Entity | Key Fields
------ | ----------
Message | id, text, timestamp, senderId, imageRef?, tokenCost
Character | id, name, avatar, prompt, modelId, reputation (0–1)
Memory | id, characterId, eventText, weight, createdAt
CostRecord | id, amountTokens, amountUSD, modelId, createdAt
Image | id, localURL, visionTags[], uploadedAt

## Sequence – User Message
1. User types message → `UserInputNode` emits text.
2. `RouterNode` (phi-3-mini) predicts relevant character IDs (≤2) and reply style.
3. For each ID, `CharacterNode` calls its LLM → forms reply.
4. `CostTracker` logs token usage per call.
5. `CollatorNode` merges replies, enforces natural conversation length.
6. UI renders messages.
7. `ReflectionEngine` checks if event significant → may append to `Memory` and mutate character prompt.

## Sequence – Image Added
1. Image picked → stored locally & displayed.
2. `ImageRecognizer` (Vision) produces tags.
3. Tags appended to `UserInputNode` context so characters can react.

## Offline Chatter
• `Scheduler` wakes hourly (configurable) → emits synthetic “time tick” event.
• Characters may post message (“Eve: I’ve been thinking…”) if memory weight triggers.
• Push notification sent to user.

## External Calls Diagram
```
CharacterNode ──► LLM API (HTTPS)
CharacterNode ──► MCP Server (optional REST)
Scheduler      ──► APNs (push)
CostTracker    ──► Local DB (save tokens)
CloudKit Sync  ◄─┬─ Core Data
                └─ Image files (CKAssets)
```

## Technology Stack
Category | Choice | Notes
---------|--------|------
Language | Swift 5.10 | Async/Await, Swift Concurrency
UI | SwiftUI | iOS 17+ only
LLM Runtime | Llama.cpp / Metal | On-device tiny model
Networking | URLSession + AsyncStream |
Persistence | Core Data (SQLite) | NSPersistentCloudKitContainer
Background | BGTaskScheduler | Handles chatter & sync
Testing | XCTest + SnapshotTesting |
CI | Xcode Cloud | Run unit + UI tests, build → TestFlight

## Security & Privacy Highlights
• End-to-end encrypted sync via CloudKit.
• API keys stored in iOS Keychain & never synced.
• Character import JSON signed with ECDSA to prevent malicious code.

## Context Management (Long Chats)
The active prompt is kept small via a **4-layer hierarchy**:
1. Short-term window (recent 10–20 turns)
2. Episodic summaries (TL;DR of scrolled messages, see [docs/long_context.md])
3. Semantic memory records (vector + weight decay)
4. Persona / system instructions

`DialogManager` slides the window → summarizer → `EpisodicStore`.
During prompt assembly it merges _short-term_ + top-K (episodic ∪ semantic).

See [long_context.md](long_context.md) for full algorithm.

---
*(Last updated: 2025-05-21)*
