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

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

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

# --- Initialise global objects ------------------------------------------------

cost_tracker = CostTracker()
memory_manager = MemoryManager(autoload=True)

router_model = os.getenv("ROUTER_MODEL", "gpt-4o")

# Character models can be customised via env if desired (comma-separated list)
char_models_env = os.getenv("CHARACTER_MODELS", "eve:gpt-4o,atlas:gpt-4o")
character_models: Dict[str, str] = {
    pair.split(":")[0]: pair.split(":")[1] for pair in char_models_env.split(",") if ":" in pair
}

# Create the LangGraph graph once at startup
graph = create_world_chat_graph(
    router_model=router_model,
    character_models=character_models,
    cost_tracker=cost_tracker,
    memory_manager=memory_manager,
)

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

# --- Run with `python server.py` for convenience ------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "5050"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
