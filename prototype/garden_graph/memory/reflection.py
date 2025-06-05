"""Reflection subsystem – condenses fading memories into long-term traits.

This is an initial draft that will evolve across phases.
"""
from __future__ import annotations

import json
import uuid
import datetime as _dt
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence

# --------------------------------------------------
@dataclass
class ReflectionRecord:
    id: str
    created_at: str  # ISO
    source_mem_ids: List[str]
    summary: str
    traits_delta: Dict[str, float]

    @classmethod
    def create(
        cls,
        source_mem_ids: Sequence[str],
        summary: str,
        traits_delta: Dict[str, float] | None = None,
    ) -> "ReflectionRecord":
        return cls(
            id=str(uuid.uuid4()),
            created_at=_dt.datetime.now(_dt.timezone.utc).isoformat(),
            source_mem_ids=list(source_mem_ids),
            summary=summary,
            traits_delta=traits_delta or {},
        )

# --------------------------------------------------
class ReflectionManager:
    """Manages reflection records per character."""

    FILE_TEMPLATE = "reflections_{char}.json"
    # reflect after every N new memories (quick heuristic)
    REFLECTION_THRESHOLD = 10

    def __init__(self, data_dir: Path):
        self._base_dir = data_dir
        self._reflections: Dict[str, List[ReflectionRecord]] = {}
        self._mem_counter: Dict[str, int] = {}

    # ---------- persistence ----------
    def _filepath(self, char: str) -> Path:
        return self._base_dir / self.FILE_TEMPLATE.format(char=char)

    def load(self, char: str):
        fp = self._filepath(char)
        if fp.exists():
            with fp.open("r", encoding="utf-8") as f:
                data = json.load(f)
            self._reflections[char] = [ReflectionRecord(**r) for r in data]
        else:
            self._reflections[char] = []

    def save(self, char: str):
        fp = self._filepath(char)
        fp.parent.mkdir(parents=True, exist_ok=True)
        with fp.open("w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in self._reflections.get(char, [])], f, ensure_ascii=False, indent=2)

    # ---------- API ----------
    def on_new_memory(self, char: str):
        self._mem_counter[char] = self._mem_counter.get(char, 0) + 1

    def maybe_reflect(self, char: str, top_memories: Sequence["MemoryRecord"], llm=None):
        if self._mem_counter.get(char, 0) < self.REFLECTION_THRESHOLD:
            return None
        self._mem_counter[char] = 0  # reset counter
        # simplistic summary for now – concatenate event_texts
        summary = "; ".join(m.event_text for m in top_memories)[:300]
        reflection = ReflectionRecord.create([m.id for m in top_memories], summary)
        self._reflections.setdefault(char, []).append(reflection)
        self.save(char)
        return reflection

    def last_summaries(self, char: str, n: int = 3) -> List[str]:
        return [r.summary for r in self._reflections.get(char, [])[-n:]]
