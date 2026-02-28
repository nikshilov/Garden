# Garden — Project Conventions

Garden is a system where AI characters (Eve, Atlas, Adam, Lilith, Sophia) live in a shared garden with 4-layer memory, 10-axis relationships, a 14D mood model, heartbeat-driven inner life, inter-character relationships, identity evolution, initiative engine, garden world model, self-healing diagnostics, and an iOS companion app.

## Repository Structure

```
backend/          Python 3.11 + FastAPI + LangGraph backend
ios/              SwiftUI iOS 17+ app (XcodeGen-managed)
docs/             Architecture, PRD, progress, algorithm docs
PLAN.md           7-phase plan + post-plan additions
docker-compose.yml  Docker deployment
```

## Backend

### Run

```bash
cd backend && ../.venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 5050 --reload
# or: make backend-run
```

### Test

```bash
cd backend && .venv/bin/python -m pytest
```

### Key Modules

| Module | Purpose |
|--------|---------|
| `server.py` | FastAPI app, all HTTP endpoints |
| `garden_graph/graph.py` | LangGraph world chat graph |
| `garden_graph/character.py` | Character node logic |
| `garden_graph/router.py` | Message routing |
| `garden_graph/memory/` | 4-layer memory system (manager, episodic, semantic, reflections) |
| `garden_graph/mood.py` | 14D mood model |
| `garden_graph/heartbeat.py` | Background life engine + autonomous conversations |
| `garden_graph/initiative.py` | Characters reaching out (Phase 5) |
| `garden_graph/garden_world.py` | Garden state, seasons, weather, locations, artifacts |
| `garden_graph/health.py` | Self-diagnostics and self-repair |
| `garden_graph/identity.py` | Identity evolution and trait drift |
| `garden_graph/cost_tracker.py` | Token and USD cost tracking |

## iOS

### Build

```bash
cd ios && xcodegen generate && xcodebuild -workspace GardenChat.xcworkspace -scheme GardenChat -sdk iphonesimulator -destination 'id=D5F3CC94-881F-42D4-BAD7-4DB0F46F0152' build
# or: make ios  (generates Xcode project only)
```

### Target Structure

- **GardenCore** — framework with API client, models, config
- **GardenChat** — main app (SwiftUI views, view models, stores)
- **External dependency**: [ExyteChat](https://github.com/exyte/Chat) >= 2.6.3

### Key Views

| View | Purpose |
|------|---------|
| `DashboardView` | Garden state, character presences, initiatives, artifacts |
| `CharacterDetailView` | Character profile, health diagnostics |
| `SettingsView` | Backend URL, initiative controls |
| `ContentView` | Tab-based root navigation |
| `ChatsListView` | Chat list with world + 1-on-1 |
| `ArtifactDetailView` | Full-screen artifact reading |
| `OnboardingView` | First-launch experience |

## Key Conventions

- **Character IDs** are lowercase: `eve`, `atlas`, `adam`, `lilith`, `sophia`
- **Chat IDs**: `character_{id}` for 1-on-1 chats, `world` for group chat
- **iOS uses XcodeGen** — run `xcodegen generate` after adding/removing Swift files
- Character model has optional presence fields: `location`, `activity`, `energy`

## API (port 5050)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/chat` | Send a message, get character replies |
| `GET` | `/garden/state` | Garden world state (season, weather, time) |
| `GET` | `/garden/artifacts` | List garden artifacts |
| `GET` | `/initiatives/pending` | Pending character initiatives |
| `GET` | `/health/diagnostics` | Character health diagnostics |
| `POST` | `/health/repair/{char_id}` | Trigger self-repair for a character |
| `GET` | `/health` | Basic health check |
| `GET` | `/characters` | List all characters |
| `GET` | `/garden/conversations` | Recent inter-character conversations |
