"""Thin wrapper around a small LLM to produce TL;DR summaries.
For now we call the same get_llm() helper but force model="phi3-mini".
This keeps dependency minimal; replace with local model later.
"""
from __future__ import annotations

from typing import List, Dict

from garden_graph.config import get_llm


class Summarizer:
    _instance = None

    def __init__(self, model: str = "phi3-mini", temperature: float = 0.3):
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
