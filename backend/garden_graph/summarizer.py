"""Thin wrapper around a small LLM to produce TL;DR summaries.

The summarizer uses a lightweight model specified by the `SUMMARIZER_MODEL` environment variable.
If the variable is not set, it falls back to `gpt-4o-mini`.
"""
from __future__ import annotations

from typing import List, Dict
import os

from garden_graph.config import get_llm


# Resolve which model to use for summarisation once at import time
DEFAULT_SUMMARIZER_MODEL = os.getenv("SUMMARIZER_MODEL", "gpt-4o-mini")

class Summarizer:
    _instance = None

    def __init__(self, model: str = DEFAULT_SUMMARIZER_MODEL, temperature: float = 0.3):
        self.llm = get_llm(model, temperature=temperature)

    @classmethod
    def instance(cls) -> "Summarizer":
        if cls._instance is None:
            cls._instance = Summarizer()
        return cls._instance

    def summarize(self, messages: List[Dict[str, str]]) -> str:
        """messages: list like [{"role":"user|assistant", "content": "..."}, ...]"""
        # concatenate into simple prompt
        convo = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        prompt = (
            "Summarize the following conversation fragment in 1–2 sentences, 120 tokens max, keeping key facts and unresolved questions.\n\n" + convo
        )
        return self.llm.invoke(prompt).content.strip()
