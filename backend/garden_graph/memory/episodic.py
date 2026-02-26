"""Episodic memory store – lightweight JSON + naive similarity search.
Each character has its own file: data/episodic_<char>.json
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, asdict

logger = logging.getLogger("garden.memory.episodic")
from datetime import datetime, timezone
from typing import List, Dict, Any
from collections import Counter

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(_DATA_DIR, exist_ok=True)


@dataclass
class EpisodicRecord:
    id: str
    summary: str
    token_count: int
    created_at: str  # ISO string

    @classmethod
    def create(cls, summary: str) -> "EpisodicRecord":
        from tiktoken import get_encoding  # optional runtime import
        try:
            enc = get_encoding("cl100k_base")
            tokens = len(enc.encode(summary))
        except Exception:
            # Fallback to word count × 1.3 ≈ tokens
            tokens = int(len(summary.split()) * 1.3)
        return cls(id=str(uuid.uuid4()), summary=summary, token_count=tokens, created_at=datetime.now(timezone.utc).isoformat())


class EpisodicStore:
    """Persist and search episodic summaries."""

    WINDOW_SIZE = 20  # default short-term size used elsewhere

    def __init__(self):
        # cache in-memory
        self._cache: Dict[str, List[EpisodicRecord]] = {}

    # ---------------- persistence helpers ---------------- #
    def _path(self, char: str) -> str:
        return os.path.join(_DATA_DIR, f"episodic_{char}.json")

    def _load(self, char: str) -> List[EpisodicRecord]:
        if char in self._cache:
            return self._cache[char]
        path = self._path(char)
        if not os.path.exists(path):
            self._cache[char] = []
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        records = [EpisodicRecord(**d) for d in data]
        self._cache[char] = records
        return records

    def _save(self, char: str) -> None:
        path = self._path(char)
        with open(path, "w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in self._cache.get(char, [])], f, ensure_ascii=False, indent=2)

    # ---------------- public API ---------------- #
    def add(self, char: str, summary: str) -> EpisodicRecord:
        rec = EpisodicRecord.create(summary)
        lst = self._load(char)
        lst.append(rec)
        self._save(char)
        return rec

    # very naive similarity: Jaccard on lowercase word sets + recency boost
    def search(self, char: str, query: str, k: int = 5) -> List[EpisodicRecord]:
        records = self._load(char)
        if not records:
            return []
        q_set = set(query.lower().split())
        now = datetime.now(timezone.utc)
        scored = []
        for r in records:
            s_set = set(r.summary.lower().split())
            if not s_set:
                continue
            inter = len(q_set & s_set)
            union = len(q_set | s_set)
            jaccard = inter / union if union else 0.0
            # recency in days
            try:
                age_days = (now - datetime.fromisoformat(r.created_at)).total_seconds() / 86_400
            except Exception:
                age_days = 0
            recency_boost = max(0.0, 1.0 - age_days / 30)  # linear decay 30 days
            score = 0.6 * jaccard + 0.4 * recency_boost
            scored.append((score, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:k]]

    def last_n(self, char: str, n: int = 5) -> List[EpisodicRecord]:
        return self._load(char)[-n:]
