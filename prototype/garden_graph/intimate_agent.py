"""Lightweight agent for Intimacy Mode.

This agent purposely uses a different LLM backend that allows NSFW / uncensored
content.  The backend can be swapped via the INTIMATE_MODEL environment
variable.  Until integration with Groq/Llama is wired, we fall back to the same
OpenAI model so that unit-tests keep passing.
"""
from __future__ import annotations

import os
from garden_graph.config import INTIMACY_MODEL_DEFAULT
from typing import List, Dict

try:
    from langchain.chat_models import ChatOpenAI
except Exception:
    ChatOpenAI = None  # type: ignore

# TODO: when Groq SDK is available, plug it in here.

class IntimateAgent:
    """Simple wrapper around an LLM that can be swapped out via env var."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.getenv("INTIMATE_MODEL", INTIMACY_MODEL_DEFAULT)
        if ChatOpenAI:
            self.llm = ChatOpenAI(model_name=self.model_name, temperature=0.9)
        else:
            self.llm = None  # mocked in tests

    def respond(self, user_message: str, history: List[Dict] | None = None) -> str:
        """Generate an uncensored response.

        For now we build a minimal prompt.  When using an uncensored model, we
        rely on the model's own safety layers.
        """
        if not self.llm:
            # fallback deterministic response for environments without OpenAI key
            return "[IntimateAgent placeholder response]"

        prompt = [
            {
                "role": "system",
                "content": "You are the intimate voice of the character. Respond vividly and sensually without violating the user's consent."
            },
        ]
        if history:
            for msg in history[-4:]:
                prompt.append({"role": msg.get("role", "user"), "content": msg["content"]})
        prompt.append({"role": "user", "content": user_message})
        try:
            resp = self.llm(prompt).content  # type: ignore
        except Exception:
            resp = "[IntimateAgent response failed]"
        return resp
