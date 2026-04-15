# Garden — Project Conventions (v2)

Garden is a three-layer therapeutic AI companion platform:
1. **Cartographer** — onboarding that maps user's emotional landscape
2. **Storyteller** — personalized companion for narrative immersion
3. **Mirror** — IFS-informed therapeutic observer with safety guardrails

Built on a completed 7-phase engine: 4-layer memory, 14D mood, 10-axis relationships, heartbeat inner life, identity evolution, initiative, garden world, self-healing.

**Key Principle:** The Narrative layer is uncensored. The Mirror layer provides guardrails. Censoring the Narrative defeats the purpose. Safety lives in the Mirror.

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
| `garden_graph/cartographer.py` | Onboarding agent → user profile JSON |
| `garden_graph/user_profile.py` | User profile Pydantic models + persistence |
| `garden_graph/companion_builder.py` | Profile → personalized Character generation |
| `garden_graph/narrative_arc.py` | Story arc phase tracking |
| `garden_graph/mirror.py` | Therapeutic observer, IFS patterns, safety |
| `garden_graph/safety_triggers.py` | Crisis detection (rules-based) |

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
| `POST` | `/onboarding/start` | Start cartographer onboarding session |
| `POST` | `/onboarding/message` | Send message to cartographer |
| `POST` | `/onboarding/complete` | Extract profile and save |
| `GET` | `/profile/{user_id}` | Get user profile |
| `PUT` | `/profile/{user_id}` | Update user profile |
| `POST` | `/companion/generate` | Generate companion from profile |
| `GET` | `/companion/{user_id}` | Get companion config |
| `GET` | `/narrative/{user_id}/arc` | Get narrative arc state |
| `POST` | `/mirror/message` | Send message to mirror |
| `GET` | `/mirror/patterns/{user_id}` | Get detected patterns |
| `POST` | `/mirror/debrief/{user_id}` | Start post-session debrief |
| `GET` | `/mirror/report/{user_id}` | Generate therapist report |
| `POST` | `/mirror/safety-check` | Manual safety check |
