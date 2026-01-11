"""Minimal FastAPI wrapper around Garden world chat graph.

Start with:
    cd backend
    uvicorn server:app --port 5050 --reload

The iOS client will POST {"text": "hi"} to http://localhost:5050/chat
and receive {"text": "reply"}.
"""
from __future__ import annotations

import os
import asyncio
from typing import Any, Dict, Set, Optional

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
    # Helpful message if PYTHONPATH mis-configured
    raise RuntimeError(
        "Cannot import garden_graph modules. Make sure you are running `uvicorn` from the `backend/` directory "
        "so that it is on PYTHONPATH."
    ) from exc

app = FastAPI(title="Garden Chat Backend", version="0.1.0")

# Load .env from project root (search upwards) for local development
load_dotenv(find_dotenv())

# --- Initialise global objects ------------------------------------------------

cost_tracker = CostTracker()
memory_manager = MemoryManager(autoload=True)

router_model = os.getenv("ROUTER_MODEL", "gpt-4o")

# Character models can be customised via env if desired (comma-separated list)
char_models_env = os.getenv("CHARACTER_MODELS", "eve:gpt-4o,atlas:gpt-4o")
character_models: Dict[str, str] = {
    pair.split(":")[0]: pair.split(":")[1] for pair in char_models_env.split(",") if ":" in pair
}

# Ensure 'adam' is available by default for Telegram persona
if "adam" not in character_models:
    character_models.setdefault("adam", character_models.get("eve", "gpt-4o"))

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

class ChatResponse(BaseModel):
    text: str
    cost_total_usd: float

# --- Routes -------------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    state = _initial_state()
    state["user_message"] = req.text
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
        # Fallback: join character responses
        reply = "\n".join(result["character_responses"].values())

    if not reply:
        raise HTTPException(status_code=500, detail="No response from characters")

    return ChatResponse(text=reply, cost_total_usd=cost_tracker.get_total_usd())

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
            # Best-effort send; avoid raising to keep webhook 200
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
        # Do not fail webhook delivery
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
