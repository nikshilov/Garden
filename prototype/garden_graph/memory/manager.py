"""In-memory MemoryManager implementation for Phase P2 (MVP).

Follows docs/memory_algorithm.md.  Datastore is a simple dict keyed by
UUID.  Easy to unit-test and can be swapped for persistent storage later.
"""
from __future__ import annotations

import uuid, math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

DECAY_LAMBDA = 0.05        # ≈ half-life 13.9 days
MIN_ACTIVE_WEIGHT = 0.05   # below this we archive


@dataclass
class MemoryRecord:
    id: str
    character_id: str
    event_text: str
    weight: float          # initial weight w0
    sentiment: int         # –2 .. +2
    created_at: datetime
    last_touched: datetime
    archived: bool = False

    # ------- helpers -------
    def effective_weight(self, now: Optional[datetime] = None) -> float:
        """Compute w(t) = w0 * exp(-λ·Δdays)."""
        now = now or datetime.now(timezone.utc)
        days = (now - self.last_touched).total_seconds() / 86_400.0
        return self.weight * math.exp(-DECAY_LAMBDA * days)


def _initial_weight(sentiment: int, user_flag: bool = False) -> float:
    w0 = abs(sentiment) * 0.3
    if user_flag:
        w0 += 0.4
    return max(0.1, min(1.0, w0))


class MemoryManager:
    """Lightweight in-memory manager for the MVP."""

    def __init__(self) -> None:
        self._records: Dict[str, MemoryRecord] = {}

    # ---------------- CRUD ----------------
    def create(self, *, character_id: str, event_text: str, sentiment: int, user_flag: bool = False) -> MemoryRecord:
        rec_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        rec = MemoryRecord(
            id=rec_id,
            character_id=character_id,
            event_text=event_text[:500],
            weight=_initial_weight(sentiment, user_flag),
            sentiment=sentiment,
            created_at=now,
            last_touched=now,
        )
        self._records[rec_id] = rec
        self._enforce_cap(character_id)
        return rec

    def get(self, rec_id: str) -> Optional[MemoryRecord]:
        return self._records.get(rec_id)

    def update(self, rec_id: str, *, weight: Optional[float] = None, **fields) -> bool:
        rec = self._records.get(rec_id)
        if not rec:
            return False
        if weight is not None:
            rec.weight = max(0.0, min(1.0, weight))
        for k, v in fields.items():
            if hasattr(rec, k):
                setattr(rec, k, v)
        rec.last_touched = datetime.now(timezone.utc)
        return True

    def delete(self, rec_id: str) -> bool:
        return self._records.pop(rec_id, None) is not None

    # -------------- queries --------------
    def all_active(self, character_id: str) -> List[MemoryRecord]:
        return [r for r in self._records.values() if r.character_id == character_id and not r.archived]

    def top_k(self, character_id: str, k: int = 3) -> List[MemoryRecord]:
        now = datetime.now(timezone.utc)
        return sorted(self.all_active(character_id), key=lambda r: r.effective_weight(now), reverse=True)[:k]

    # ------------ decay & cap ------------
    def decay_all(self) -> None:
        now = datetime.now(timezone.utc)
        for rec in self._records.values():
            if rec.archived:
                continue
            if rec.effective_weight(now) < MIN_ACTIVE_WEIGHT:
                rec.archived = True

    def _enforce_cap(self, character_id: str, cap: int = 200) -> None:
        active = self.all_active(character_id)
        if len(active) <= cap:
            return
        active.sort(key=lambda r: (r.last_touched, r.weight))
        for rec in active[:-cap]:
            rec.archived = True

    # -------- reflection stub --------
    def reflect_stub(self, character_id: str, context: str) -> List[Tuple[str, float]]:
        """Dummy reflection: nudges weights by ±0.1 for top-3 memories."""
        updates = []
        for rec in self.top_k(character_id):
            delta = 0.1 if rec.sentiment >= 0 else -0.1
            rec.weight = max(0.0, min(1.0, rec.weight + delta))
            rec.last_touched = datetime.now(timezone.utc)
            updates.append((rec.id, rec.weight))
        return updates

    # -------- prompt helper --------
    def prompt_segment(self, character_id: str, k: int = 3) -> str:
        recs = self.top_k(character_id, k)
        if not recs:
            return ""
        lines = ["Relevant memories:"]
        for r in recs:
            lines.append(f"• [{r.event_text}] (w={r.effective_weight():.2f})")
        return "\n".join(lines)

    # -------- export --------
    def to_dict(self) -> Dict[str, Dict]:
        return {rid: asdict(r) for rid, r in self._records.items()}
