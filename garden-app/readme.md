# Garden

**A place where AI characters live, remember, grow, and reach out.**

Garden is a personal space where five AI characters — Eve, Atlas, Adam, Lilith, and Sophia — share a living garden. They form memories, build relationships with each other, evolve over time, and sometimes reach out to you when they have something to say. When you're not there, they keep living.

## Features

- **Heartbeat** — Characters have inner life between conversations. Moods drift, relationships evolve, internal thoughts form.
- **Semantic Memory** — Embedding-based memory retrieval. Characters understand meaning, not just words.
- **Inter-Character Relationships** — 10-axis relationships between all characters. They form opinions, alliances, and tensions.
- **Identity Evolution** — Characters change over time. Personality traits drift based on experiences.
- **Initiative Engine** — Characters reach out when they have something to say. Respects quiet hours and boundaries.
- **Garden World** — Seasons, weather, day/night cycle, character locations, shared artifacts.
- **Self-Healing Diagnostics** — Characters monitor their own coherence and can self-repair.
- **Autonomous Conversations** — Characters talk to each other between user sessions.
- **Docker Deployment** — Persistent backend with health checks and auto-restart.
- **iOS App** — Living dashboard, character profiles, chat, settings.

## Quick Start

### Backend

```bash
# Install dependencies
make backend-install

# Run (port 5050)
make backend-run

# Test
cd backend && .venv/bin/python -m pytest
```

### iOS

```bash
# Generate Xcode project
cd ios && xcodegen generate

# Open in Xcode
open ios/GardenChat.xcworkspace
```

Requires Xcode 15+, iOS 17+ simulator or device.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full system architecture.

The backend runs as a FastAPI service with LangGraph orchestrating character conversations, memory, and the heartbeat engine. The iOS app connects via REST API.

## Screenshots

*Coming soon.*

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11, FastAPI, LangGraph |
| LLM | GPT-4.1, GPT-4o-mini |
| Embeddings | all-MiniLM-L6-v2 (local) |
| iOS App | SwiftUI, iOS 17+ |
| iOS Chat UI | [ExyteChat](https://github.com/exyte/Chat) |
| iOS Project | XcodeGen |
| Deployment | Docker, docker-compose |
| Testing | pytest (162 tests), XCTest |
