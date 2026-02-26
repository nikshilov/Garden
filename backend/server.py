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
except ModuleNotFoundError as exc:
    raise RuntimeError(
        "Cannot import garden_graph modules. Make sure you are running `uvicorn` from the `backend/` directory "
        "so that it is on PYTHONPATH."
    ) from exc

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

# --- Run with `python server.py` for convenience ------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "5050"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
