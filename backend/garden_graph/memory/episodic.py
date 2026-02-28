"""Episodic memory store – JSON persistence + embedding-based semantic search.
Each character has its own file: data/episodic_<char>.json

Phase 2 (Roots): records now carry an optional 384-dim embedding vector.
Search uses cosine similarity when embeddings are available, falling back
to Jaccard word-overlap for legacy records or when the embedder is missing.
"""
from __future__ import annotations

import json
import logging
import math
import os
import uuid
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("garden.memory.episodic")
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from collections import Counter

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(_DATA_DIR, exist_ok=True)


@dataclass
class EpisodicRecord:
    id: str
    summary: str
    token_count: int
    created_at: str  # ISO string
    embedding: Optional[List[float]] = field(default=None, repr=False)

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
        records = [
            EpisodicRecord(
                id=d["id"],
                summary=d["summary"],
                token_count=d["token_count"],
                created_at=d["created_at"],
                embedding=d.get("embedding"),
            )
            for d in data
        ]
        self._cache[char] = records
        return records

    def _save(self, char: str) -> None:
        path = self._path(char)
        with open(path, "w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in self._cache.get(char, [])], f, ensure_ascii=False, indent=2)

    # ---------------- embedding helpers ---------------- #
    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors (pure Python)."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _recency_score(created_at: str) -> float:
        """Linear decay over 30 days: 1.0 for brand-new, 0.0 at >= 30 days."""
        now = datetime.now(timezone.utc)
        try:
            age_days = (now - datetime.fromisoformat(created_at)).total_seconds() / 86_400
        except Exception:
            age_days = 0
        return max(0.0, 1.0 - age_days / 30)

    # ---------------- public API ---------------- #
    def add(self, char: str, summary: str) -> EpisodicRecord:
        rec = EpisodicRecord.create(summary)
        # Phase 2: compute embedding if embedder is available
        try:
            from garden_graph.memory.embedder import get_embedder
            embedder = get_embedder()
            if embedder:
                rec.embedding = embedder.encode(summary).tolist()
        except Exception:
            logger.debug("Embedder unavailable on add(); skipping embedding", exc_info=True)
        lst = self._load(char)
        lst.append(rec)
        self._save(char)
        return rec

    def search(self, char: str, query: str, k: int = 5) -> List[EpisodicRecord]:
        """Search episodic memory. Uses embedding cosine similarity when
        available, falling back to Jaccard word-overlap otherwise."""
        records = self._load(char)
        if not records:
            return []

        # Try semantic search first
        try:
            from garden_graph.memory.embedder import get_embedder
            embedder = get_embedder()
        except Exception:
            embedder = None

        embedded_records = [r for r in records if r.embedding is not None]
        if embedder and embedded_records:
            return self._search_semantic(embedder, query, embedded_records, k)
        # Fallback to Jaccard
        return self._search_jaccard(records, query, k)

    def last_n(self, char: str, n: int = 5) -> List[EpisodicRecord]:
        return self._load(char)[-n:]

    def backfill_embeddings(self, char: str, batch_size: int = 20) -> int:
        """Compute embeddings for records that lack one. Returns the count of
        newly embedded records. Intended to be called during heartbeat to
        gradually upgrade legacy memories.

        Args:
            char: character id
            batch_size: max records to process per call (avoids long blocking)
        """
        try:
            from garden_graph.memory.embedder import get_embedder
            embedder = get_embedder()
        except Exception:
            return 0
        if not embedder:
            return 0

        records = self._load(char)
        count = 0
        for rec in records:
            if count >= batch_size:
                break
            if rec.embedding is not None:
                continue
            try:
                rec.embedding = embedder.encode(rec.summary).tolist()
                count += 1
            except Exception:
                logger.warning("Failed to embed record %s", rec.id, exc_info=True)
        if count > 0:
            self._save(char)
            logger.info("Backfilled %d embeddings for character '%s'", count, char)
        return count

    # ---------------- private search strategies ---------------- #
    def _search_semantic(self, embedder: Any, query: str, records: List[EpisodicRecord], k: int) -> List[EpisodicRecord]:
        """Rank records by cosine similarity of embeddings + recency boost."""
        try:
            q_vec = embedder.encode(query).tolist()
        except Exception:
            logger.warning("Embedder failed on query; falling back to Jaccard", exc_info=True)
            return self._search_jaccard(records, query, k)

        scored: List[tuple[float, EpisodicRecord]] = []
        for r in records:
            if r.embedding is None:
                continue
            sim = self._cosine_similarity(q_vec, r.embedding)
            recency = self._recency_score(r.created_at)
            score = 0.6 * sim + 0.4 * recency
            scored.append((score, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:k]]

    @staticmethod
    def _search_jaccard(records: List[EpisodicRecord], query: str, k: int) -> List[EpisodicRecord]:
        """Fallback search: Jaccard on lowercase word sets + recency boost."""
        q_set = set(query.lower().split())
        now = datetime.now(timezone.utc)
        scored: List[tuple[float, EpisodicRecord]] = []
        for r in records:
            s_set = set(r.summary.lower().split())
            if not s_set:
                continue
            inter = len(q_set & s_set)
            union = len(q_set | s_set)
            jaccard = inter / union if union else 0.0
            try:
                age_days = (now - datetime.fromisoformat(r.created_at)).total_seconds() / 86_400
            except Exception:
                age_days = 0
            recency_boost = max(0.0, 1.0 - age_days / 30)
            score = 0.6 * jaccard + 0.4 * recency_boost
            scored.append((score, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:k]]
