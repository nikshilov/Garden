"""Minimal FastAPI wrapper around Garden world chat graph.

Start with:
    cd backend
    uvicorn server:app --port 5050 --reload

The iOS client will POST {"text": "hi"} to http://localhost:5050/chat
and receive {"text": "reply"}.
"""
from __future__ import annotations

import logging
import os
import time
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Set, Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from dotenv import load_dotenv, find_dotenv
import httpx

# Ensure local imports work when running via `uvicorn server:app`
try:
    from garden_graph.graph import create_world_chat_graph, format_cost_summary
    from garden_graph.cost_tracker import CostTracker
    from garden_graph.memory.manager import MemoryManager
    from garden_graph.config import INTIMACY_MODEL_DEFAULT
    from garden_graph.heartbeat import Heartbeat
except ModuleNotFoundError as exc:
    raise RuntimeError(
        "Cannot import garden_graph modules. Make sure you are running `uvicorn` from the `backend/` directory "
        "so that it is on PYTHONPATH."
    ) from exc

# Initiative engine (Phase 5 — Voice: Reaching Out) — optional, graceful degradation
try:
    from garden_graph.initiative import InitiativeEngine
    _initiative_available = True
except ImportError:
    InitiativeEngine = None  # type: ignore[misc, assignment]
    _initiative_available = False
    logging.getLogger("garden.server").warning(
        "garden_graph.initiative not found — initiative features disabled"
    )

# Garden world (Phase 6 — Soil: Sense of Place) — optional, graceful degradation
try:
    from garden_graph.garden_world import GardenWorld
    _garden_world_available = True
except ImportError:
    GardenWorld = None  # type: ignore[misc, assignment]
    _garden_world_available = False
    logging.getLogger("garden.server").warning(
        "garden_graph.garden_world not found — garden world features disabled"
    )

# Health monitor (Phase 7 — Autonomy: Self-Healing Garden) — optional, graceful degradation
try:
    from garden_graph.health import HealthMonitor, SelfRepair, overall_status
    _health_available = True
except ImportError:
    HealthMonitor = None
    SelfRepair = None
    _health_available = False
    logging.getLogger("garden.server").warning(
        "garden_graph.health not found — health monitoring disabled"
    )

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("garden.server")

app = FastAPI(title="Garden Chat Backend", version="0.2.0")

# Load .env from project root (search upwards) for local development
load_dotenv(find_dotenv())

# --- Initialise global objects ------------------------------------------------

cost_tracker = CostTracker()
memory_manager = MemoryManager(autoload=True)

router_model = os.getenv("ROUTER_MODEL", "gpt-4o")

# Character models can be customised via env if desired (comma-separated list)
char_models_env = os.getenv("CHARACTER_MODELS", "eve:gpt-4o,atlas:gpt-4o,adam:gpt-4o,lilith:gpt-4o,sophia:gpt-4o")
character_models: Dict[str, str] = {
    pair.split(":")[0]: pair.split(":")[1] for pair in char_models_env.split(",") if ":" in pair
}

logger.info(f"Initialized with characters: {list(character_models.keys())}")

# Create the LangGraph graph once at startup
graph = create_world_chat_graph(
    router_model=router_model,
    character_models=character_models,
    cost_tracker=cost_tracker,
    memory_manager=memory_manager,
)

# --- Heartbeat (life between conversations) ---
heartbeat = Heartbeat(
    character_ids=list(character_models.keys()),
    memory_manager=memory_manager,
)

# --- Initiative engine (characters reaching out) ---
initiative_engine = None
if _initiative_available and InitiativeEngine is not None:
    initiative_engine = InitiativeEngine(memory_manager=memory_manager)
    logger.info("Initiative engine initialized")

# --- Garden world (sense of place) ---
garden_world = None
if _garden_world_available and GardenWorld is not None:
    garden_world = GardenWorld()
    logger.info("Garden world initialized")

# --- Health monitor (self-healing garden) ---
health_monitor = None
self_repair = None
if _health_available and HealthMonitor is not None:
    health_monitor = HealthMonitor()
    self_repair = SelfRepair()
    logger.info("Health monitor initialized")

# Store pending initiatives for the notification system to pick up
_pending_initiatives: List[Dict] = []

# Default initiative settings
_initiative_settings: Dict[str, Any] = {
    "enabled": True,
    "check_interval_seconds": 3600,
    "quiet_hours_start": None,   # e.g. 23 (11pm)
    "quiet_hours_end": None,     # e.g. 8  (8am)
    "disabled_characters": [],   # character IDs that should not send initiatives
}


async def _initiative_loop():
    """Check for character initiatives periodically."""
    while True:
        interval = _initiative_settings.get("check_interval_seconds", 3600)
        await asyncio.sleep(interval)

        if not initiative_engine or not _initiative_settings.get("enabled", True):
            continue

        now = datetime.now(timezone.utc)

        # Respect quiet hours
        quiet_start = _initiative_settings.get("quiet_hours_start")
        quiet_end = _initiative_settings.get("quiet_hours_end")
        if quiet_start is not None and quiet_end is not None:
            current_hour = now.hour
            if quiet_start > quiet_end:  # wraps midnight, e.g. 23-8
                if current_hour >= quiet_start or current_hour < quiet_end:
                    continue
            else:
                if quiet_start <= current_hour < quiet_end:
                    continue

        disabled = set(_initiative_settings.get("disabled_characters", []))

        for char_id in character_models:
            if char_id in disabled:
                continue
            try:
                result = initiative_engine.evaluate(char_id, now)
                if result:
                    from garden_graph.config import get_llm
                    llm = get_llm(os.getenv("HEARTBEAT_MODEL", "gpt-4o-mini"), temperature=0.9)
                    message = initiative_engine.generate_message(result, llm)
                    if message:
                        _pending_initiatives.append({
                            "id": str(uuid.uuid4()),
                            "char_id": char_id,
                            "trigger": result.trigger,
                            "message": message,
                            "created_at": result.created_at,
                        })
                        logger.info(f"Initiative from {char_id}: {message[:50]}...")
            except Exception as e:
                logger.warning(f"Initiative check failed for {char_id}: {e}")


@app.on_event("startup")
async def on_startup():
    await heartbeat.start()
    if initiative_engine:
        asyncio.create_task(_initiative_loop())
        logger.info("Initiative loop started")
    logger.info("Garden is alive")


@app.on_event("shutdown")
async def on_shutdown():
    await heartbeat.stop()
    logger.info("Garden is sleeping")

# Telegram configuration (tokens and webhook secrets)
EVE_BOT_TOKEN = os.getenv("EVE_BOT_TOKEN", "")
ADAM_BOT_TOKEN = os.getenv("ADAM_BOT_TOKEN", "")
WEBHOOK_SECRET_EVE = os.getenv("WEBHOOK_SECRET_EVE", "")
WEBHOOK_SECRET_ADAM = os.getenv("WEBHOOK_SECRET_ADAM", "")

# --- Session Management ------------------------------------------------------

SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", str(24 * 3600)))


class Session:
    """Tracks conversation state across multiple HTTP requests."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.message_history: List[Dict] = []
        self.created_at = time.time()
        self.last_accessed = time.time()

    def is_expired(self) -> bool:
        return (time.time() - self.last_accessed) > SESSION_TTL_SECONDS

    def touch(self):
        self.last_accessed = time.time()


_sessions: Dict[str, Session] = {}


def _get_or_create_session(session_id: Optional[str] = None) -> Session:
    """Retrieve an existing session or create a new one."""
    # Clean up expired sessions
    expired = [sid for sid, s in _sessions.items() if s.is_expired()]
    for sid in expired:
        del _sessions[sid]

    if session_id and session_id in _sessions:
        session = _sessions[session_id]
        session.touch()
        return session

    new_id = session_id or str(uuid.uuid4())
    session = Session(new_id)
    _sessions[new_id] = session
    logger.info(f"Created new session: {new_id}")
    return session


# Helper to build new state dict for each request

def _initial_state() -> Dict[str, Any]:
    return {
        "user_message": "",
        "message_history": [],
        "active_characters": set(),
        "selected_characters": set(),
        "character_responses": {},
        "final_response": None,
        "intimacy_mode": False,
        "intimate_model": INTIMACY_MODEL_DEFAULT,
        "costs": {},
    }

# --- Request/response models --------------------------------------------------

class ChatRequest(BaseModel):
    text: str
    character_id: str | None = None
    session_id: str | None = None

class ChatResponse(BaseModel):
    text: str
    session_id: str
    cost_total_usd: float
    budget_limit: float = 0.0
    budget_exceeded: bool = False
    budget_remaining: float = 0.0

# --- Routes -------------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/heartbeat/status")
async def heartbeat_status():
    return {
        "running": heartbeat._running,
        "interval_hours": float(os.getenv("HEARTBEAT_INTERVAL_HOURS", "6")),
        "characters": heartbeat.character_ids,
    }

@app.post("/heartbeat/tick")
async def manual_heartbeat_tick():
    """Manually trigger a heartbeat tick (for testing/debugging)."""
    await heartbeat.tick()
    return {"ok": True, "message": "Heartbeat tick completed"}

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    # Session management - persist conversation across requests
    session = _get_or_create_session(req.session_id)

    state = _initial_state()
    state["user_message"] = req.text

    # Load message history from session
    state["message_history"] = list(session.message_history)

    if req.character_id:
        state["active_characters"] = {req.character_id}
        state["selected_characters"] = {req.character_id}
    state["message_history"].append({"role": "user", "content": req.text})

    try:
        result = await graph.ainvoke(state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Extract reply
    reply: Optional[str] = result.get("final_response")
    if not reply and result.get("character_responses"):
        reply = "\n".join(result["character_responses"].values())

    if not reply:
        raise HTTPException(status_code=500, detail="No response from characters")

    # Update session with new message history
    session.message_history = result.get("message_history", state["message_history"])

    # Calculate budget status
    total_cost = cost_tracker.get_total_usd()
    budget_limit = cost_tracker.budget_limit
    budget_exceeded = budget_limit > 0 and total_cost > budget_limit
    budget_remaining = max(0.0, budget_limit - total_cost) if budget_limit > 0 else 0.0

    return ChatResponse(
        text=reply,
        session_id=session.session_id,
        cost_total_usd=total_cost,
        budget_limit=budget_limit,
        budget_exceeded=budget_exceeded,
        budget_remaining=budget_remaining
    )

# --- Session API Routes -------------------------------------------------------

@app.get("/sessions")
async def list_sessions():
    """List active (non-expired) sessions."""
    active = {
        sid: {
            "created_at": s.created_at,
            "last_accessed": s.last_accessed,
            "message_count": len(s.message_history),
        }
        for sid, s in _sessions.items()
        if not s.is_expired()
    }
    return {"sessions": active}

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a specific session."""
    if session_id in _sessions:
        del _sessions[session_id]
        return {"ok": True, "deleted": session_id}
    raise HTTPException(status_code=404, detail="Session not found")

# --- Telegram Webhook Handlers -----------------------------------------------

async def _invoke_graph_for_persona(text: str, persona_id: str) -> str:
    state = _initial_state()
    state["user_message"] = text
    state["active_characters"] = {persona_id}
    state["selected_characters"] = {persona_id}
    state["message_history"].append({"role": "user", "content": text})

    result = await graph.ainvoke(state)
    reply: Optional[str] = result.get("final_response")
    if not reply and result.get("character_responses"):
        reply = "\n".join(result["character_responses"].values())
    return reply or ""

async def _send_telegram_message(bot_token: str, chat_id: int | str, text: str) -> None:
    if not bot_token:
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    timeout = httpx.Timeout(10.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            await client.post(url, json=payload)
        except Exception:
            pass

def _extract_message(update: Dict[str, Any]) -> Dict[str, Any] | None:
    return update.get("message") or update.get("edited_message")

@app.post("/tg/eve/webhook")
async def tg_eve_webhook(request: Request) -> Dict[str, bool]:
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if WEBHOOK_SECRET_EVE and secret != WEBHOOK_SECRET_EVE:
        raise HTTPException(status_code=403, detail="Invalid secret token")

    update = await request.json()
    msg = _extract_message(update)
    if not msg:
        return {"ok": True}

    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip() or "/start"

    try:
        reply = await _invoke_graph_for_persona(text, persona_id="eve")
        if not reply:
            reply = "Привет!"
        await _send_telegram_message(EVE_BOT_TOKEN, chat_id, reply)
    except Exception:
        pass

    return {"ok": True}

@app.post("/tg/adam/webhook")
async def tg_adam_webhook(request: Request) -> Dict[str, bool]:
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if WEBHOOK_SECRET_ADAM and secret != WEBHOOK_SECRET_ADAM:
        raise HTTPException(status_code=403, detail="Invalid secret token")

    update = await request.json()
    msg = _extract_message(update)
    if not msg:
        return {"ok": True}

    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip() or "/start"

    try:
        reply = await _invoke_graph_for_persona(text, persona_id="adam")
        if not reply:
            reply = "Привет!"
        await _send_telegram_message(ADAM_BOT_TOKEN, chat_id, reply)
    except Exception:
        pass

    return {"ok": True}

# --- Garden World Endpoints (Phase 6 — Soil: Sense of Place) ------------------

@app.get("/garden/state")
async def get_garden_state():
    """Return the current garden world state (season, weather, ambiance, presences)."""
    if not garden_world:
        raise HTTPException(status_code=501, detail="Garden world not available")

    state = garden_world.get_state()
    presences = garden_world.get_all_presences()
    return {
        "state": state.to_dict(),
        "presences": [p.to_dict() for p in presences],
    }


@app.get("/garden/artifacts")
async def get_garden_artifacts(creator_id: Optional[str] = None, limit: int = 10):
    """Return recent garden artifacts (poems, theories, sketches, etc.)."""
    if not garden_world:
        raise HTTPException(status_code=501, detail="Garden world not available")

    artifacts = garden_world.get_artifacts(creator_id=creator_id, limit=limit)
    return {"artifacts": [a.to_dict() for a in artifacts]}


@app.post("/garden/update")
async def update_garden_state():
    """Manually trigger a garden world state update (for testing/debugging)."""
    if not garden_world:
        raise HTTPException(status_code=501, detail="Garden world not available")

    state = garden_world.update()
    return {"ok": True, "state": state.to_dict()}


# --- Initiative Endpoints (Phase 5 — Voice: Reaching Out) ---------------------

@app.get("/initiatives/pending")
async def get_pending_initiatives():
    """Return pending initiative messages for the notification system to pick up."""
    return {"initiatives": _pending_initiatives}


@app.post("/initiatives/dismiss/{initiative_id}")
async def dismiss_initiative(initiative_id: str):
    """Dismiss (remove) a pending initiative notification."""
    global _pending_initiatives
    original_len = len(_pending_initiatives)
    _pending_initiatives = [i for i in _pending_initiatives if i["id"] != initiative_id]
    if len(_pending_initiatives) == original_len:
        raise HTTPException(status_code=404, detail="Initiative not found")
    logger.info(f"Initiative {initiative_id} dismissed")
    return {"ok": True, "dismissed": initiative_id}


@app.get("/initiatives/settings")
async def get_initiative_settings():
    """Return current initiative settings."""
    return {"settings": _initiative_settings, "available": _initiative_available}


class InitiativeSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    check_interval_seconds: Optional[int] = None
    quiet_hours_start: Optional[int] = None
    quiet_hours_end: Optional[int] = None
    disabled_characters: Optional[List[str]] = None


@app.post("/initiatives/settings")
async def update_initiative_settings(req: InitiativeSettingsUpdate):
    """Update initiative settings (quiet hours, disabled characters, etc.)."""
    if req.enabled is not None:
        _initiative_settings["enabled"] = req.enabled
    if req.check_interval_seconds is not None:
        _initiative_settings["check_interval_seconds"] = max(60, req.check_interval_seconds)
    if req.quiet_hours_start is not None:
        _initiative_settings["quiet_hours_start"] = req.quiet_hours_start
    if req.quiet_hours_end is not None:
        _initiative_settings["quiet_hours_end"] = req.quiet_hours_end
    if req.disabled_characters is not None:
        _initiative_settings["disabled_characters"] = req.disabled_characters
    logger.info(f"Initiative settings updated: {_initiative_settings}")
    return {"ok": True, "settings": _initiative_settings}


@app.post("/initiatives/check")
async def check_initiatives():
    """Manually trigger initiative evaluation for all characters (testing/debugging)."""
    if not initiative_engine:
        raise HTTPException(
            status_code=501,
            detail="Initiative engine not available. Install garden_graph.initiative module.",
        )

    results = []
    now = datetime.now(timezone.utc)
    disabled = set(_initiative_settings.get("disabled_characters", []))

    for char_id in character_models:
        if char_id in disabled:
            continue
        try:
            result = initiative_engine.evaluate(char_id, now)
            if result:
                from garden_graph.config import get_llm
                llm = get_llm(os.getenv("HEARTBEAT_MODEL", "gpt-4o-mini"), temperature=0.9)
                message = initiative_engine.generate_message(result, llm)
                if message:
                    initiative_data = {
                        "id": str(uuid.uuid4()),
                        "char_id": char_id,
                        "trigger": result.trigger,
                        "message": message,
                        "created_at": result.created_at,
                    }
                    _pending_initiatives.append(initiative_data)
                    results.append(initiative_data)
        except Exception as e:
            logger.warning(f"Initiative check failed for {char_id}: {e}")
            results.append({"char_id": char_id, "error": str(e)})

    return {"checked": len(character_models), "initiatives": results}


# --- Health Endpoints (Phase 7 — Autonomy: Self-Healing Garden) ---------------

@app.get("/health/diagnostics")
async def get_diagnostics(char_id: Optional[str] = None):
    """Run health diagnostics for one or all characters."""
    if not health_monitor:
        raise HTTPException(status_code=501, detail="Health monitor not available")

    if char_id:
        checks = health_monitor.check_all(char_id)
        status = overall_status(checks)
        return {
            "character": char_id,
            "status": status.value,
            "checks": [
                {
                    "category": c.category,
                    "status": c.status.value,
                    "message": c.message,
                    "auto_fixable": c.auto_fixable,
                }
                for c in checks
            ],
        }

    # All characters
    all_results = health_monitor.check_all_characters(list(character_models.keys()))
    summary = {}
    for cid, checks in all_results.items():
        status = overall_status(checks)
        summary[cid] = {
            "status": status.value,
            "checks": [
                {
                    "category": c.category,
                    "status": c.status.value,
                    "message": c.message,
                    "auto_fixable": c.auto_fixable,
                }
                for c in checks
            ],
        }
    return {"diagnostics": summary}


@app.post("/health/repair/{char_id}")
async def repair_character(char_id: str):
    """Run auto-repair for a character's fixable issues."""
    if not health_monitor or not self_repair:
        raise HTTPException(status_code=501, detail="Health monitor not available")

    checks = health_monitor.check_all(char_id)
    repairs = self_repair.repair_all(char_id, checks)

    # Re-run diagnostics to show new state
    new_checks = health_monitor.check_all(char_id)
    new_status = overall_status(new_checks)

    return {
        "character": char_id,
        "repairs_applied": repairs,
        "new_status": new_status.value,
        "checks": [
            {
                "category": c.category,
                "status": c.status.value,
                "message": c.message,
            }
            for c in new_checks
        ],
    }


# --- Run with `python server.py` for convenience ------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "5050"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
