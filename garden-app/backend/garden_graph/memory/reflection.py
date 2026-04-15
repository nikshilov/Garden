"""Reflection subsystem – condenses fading memories into long-term traits.

Phase 4 (Growth — Identity Evolution): reflections now use the LLM to
generate real personality-shift analyses and first-person growth narratives.
"""
from __future__ import annotations

import json
import logging
import uuid
import datetime as _dt
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

logger = logging.getLogger("garden.memory.reflection")

# --------------------------------------------------
@dataclass
class ReflectionRecord:
    id: str
    created_at: str  # ISO
    source_mem_ids: List[str]
    summary: str
    traits_delta: Dict[str, float]
    growth_narrative: Optional[str] = None

    @classmethod
    def create(
        cls,
        source_mem_ids: Sequence[str],
        summary: str,
        traits_delta: Dict[str, float] | None = None,
        growth_narrative: Optional[str] = None,
    ) -> "ReflectionRecord":
        return cls(
            id=str(uuid.uuid4()),
            created_at=_dt.datetime.now(_dt.timezone.utc).isoformat(),
            source_mem_ids=list(source_mem_ids),
            summary=summary,
            traits_delta=traits_delta or {},
            growth_narrative=growth_narrative,
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

    # Valid personality traits for delta computation
    PERSONALITY_TRAITS = frozenset([
        "openness", "assertiveness", "warmth",
        "introspection", "playfulness", "resilience",
    ])

    # ---------- API ----------
    def on_new_memory(self, char: str):
        self._mem_counter[char] = self._mem_counter.get(char, 0) + 1

    def maybe_reflect(self, char: str, top_memories: Sequence["MemoryRecord"], llm=None):
        """Trigger a reflection if enough new memories have accumulated.

        When *llm* is provided (any callable accepting a prompt string and
        returning a string), the reflection is generated via LLM analysis of
        the recent memories, producing a real summary, traits_delta, and a
        first-person growth narrative.  When *llm* is ``None`` the method
        falls back to simple concatenation (Phase-1 behaviour).
        """
        if self._mem_counter.get(char, 0) < self.REFLECTION_THRESHOLD:
            return None
        self._mem_counter[char] = 0  # reset counter

        mem_ids = [m.id for m in top_memories]

        if llm is not None:
            reflection = self._reflect_with_llm(char, top_memories, mem_ids, llm)
            if reflection is not None:
                self._reflections.setdefault(char, []).append(reflection)
                self.save(char)
                return reflection
            # LLM path failed — fall through to simple path
            logger.warning("LLM reflection failed for %s; using simple fallback", char)

        # Fallback: simplistic summary (Phase 1 behaviour)
        summary = "; ".join(m.event_text for m in top_memories)[:300]
        reflection = ReflectionRecord.create(mem_ids, summary)
        self._reflections.setdefault(char, []).append(reflection)
        self.save(char)
        return reflection

    # ---------- LLM-powered reflection ----------
    def _reflect_with_llm(
        self,
        char: str,
        top_memories: Sequence["MemoryRecord"],
        mem_ids: List[str],
        llm,
    ) -> Optional[ReflectionRecord]:
        """Build a reflection prompt, call the LLM, and parse its JSON reply."""
        memory_lines = "\n".join(f"- {m.event_text}" for m in top_memories)
        prompt = (
            "You are a reflection engine for an AI character. Analyze these recent memories\n"
            "and determine:\n"
            "1. A brief summary of the themes (1-2 sentences)\n"
            "2. How these experiences might subtly shift the character's personality traits\n"
            "\n"
            "Memories:\n"
            f"{memory_lines}\n"
            "\n"
            "Personality traits to consider (current values not needed, just direction of change):\n"
            "- openness, assertiveness, warmth, introspection, playfulness, resilience\n"
            "\n"
            'Return JSON: {"summary": "...", "traits_delta": {"trait": delta, ...}, "growth_narrative": "..."}\n'
            "The growth_narrative should be a first-person statement about how the character\n"
            'has changed, like: "I\'ve become more comfortable with silence after those late\n'
            'night conversations."\n'
            "Deltas should be small: -0.05 to +0.05\n"
        )

        try:
            raw_response = llm(prompt)
            parsed = self._parse_llm_response(raw_response)
            if parsed is None:
                return None

            summary = parsed.get("summary", "")
            traits_delta = self._sanitize_traits_delta(parsed.get("traits_delta", {}))
            growth_narrative = parsed.get("growth_narrative")

            logger.info(
                "LLM reflection for %s: traits_delta=%s", char, traits_delta,
            )

            return ReflectionRecord.create(
                mem_ids,
                summary,
                traits_delta=traits_delta,
                growth_narrative=growth_narrative,
            )
        except Exception:
            logger.exception("Error during LLM reflection for %s", char)
            return None

    @staticmethod
    def _parse_llm_response(raw: str) -> Optional[Dict]:
        """Extract a JSON object from the LLM's response string."""
        # The model may wrap JSON in markdown fences; strip them.
        text = raw.strip()
        if text.startswith("```"):
            # Remove opening fence (possibly ```json)
            text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[: -3]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM reflection JSON: %.200s", text)
            return None

    def _sanitize_traits_delta(self, raw_delta: Dict) -> Dict[str, float]:
        """Clamp deltas to [-0.05, +0.05] and drop unknown traits."""
        sanitized: Dict[str, float] = {}
        for trait, value in raw_delta.items():
            trait_lower = trait.lower().strip()
            if trait_lower not in self.PERSONALITY_TRAITS:
                logger.debug("Ignoring unknown trait %r in reflection delta", trait)
                continue
            try:
                clamped = max(-0.05, min(0.05, float(value)))
            except (TypeError, ValueError):
                continue
            sanitized[trait_lower] = round(clamped, 4)
        return sanitized

    # ---------- growth narrative ----------
    def generate_growth_narrative(self, reflection: ReflectionRecord) -> Optional[str]:
        """Return the growth narrative from a reflection, or None.

        This is the text that should be stored as a GrowthMemory in the
        identity system.
        """
        if reflection.growth_narrative:
            return reflection.growth_narrative
        # For older reflections without a narrative, return None
        return None

    # ---------- queries ----------
    def all_reflections(self, char: str) -> List[ReflectionRecord]:
        """Return every reflection for *char* (for the identity system)."""
        return list(self._reflections.get(char, []))

    def last_summaries(self, char: str, n: int = 3) -> List[str]:
        return [r.summary for r in self._reflections.get(char, [])[-n:]]
