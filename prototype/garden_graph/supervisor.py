"""AI Producer / Supervisor module.

Provides two core capabilities:
1. Message valuation – personalise significance + action recommendations.
2. Prompt-refresh suggestion once accumulated emotional energy exceeds a
   configurable threshold.

The module reuses `MemoryManager` for sentiment/significance logic and
`EventScheduler` for scheduling prompt-refresh suggestions.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, Dict, Any

from garden_graph.config import (
    MEM_SIGNIFICANCE_THRESHOLD,
    EMOTIONAL_IMPACT_THRESHOLD,
    PROMPT_REFRESH_ENERGY_THRESHOLD,
    HIGHLIGHT_IMPACT_THRESHOLD,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from garden_graph.memory.manager import MemoryManager, MemoryRecord

Action = Literal["save", "ignore", "highlight"]


class Supervisor:
    """Supervises a single `MemoryManager` instance."""

    def __init__(self, memory_manager: MemoryManager) -> None:
        self.mm = memory_manager

    # ------------------------------------------------------------------
    # Message valuation
    # ------------------------------------------------------------------
    def evaluate_message(self, character_id: str, text: str, *, llm=None) -> Dict[str, Any]:
        """Return personalised valuation for *text*.

        Returns::
            {
              "score": float,           # -2 … 2 significance
              "action": "save" | "ignore" | "highlight",
              "reason": str,
            }
        """
        score, category, _ = self.mm._analyze_message_llm(character_id, text, llm=llm)  # pylint: disable=protected-access
        abs_score = abs(score)

        if abs_score < MEM_SIGNIFICANCE_THRESHOLD:
            return {"score": score, "action": "ignore", "reason": "below threshold"}
        if abs_score >= HIGHLIGHT_IMPACT_THRESHOLD:
            return {"score": score, "action": "highlight", "reason": f"strong impact ({category})"}
        return {"score": score, "action": "save", "reason": "normal significance"}

    # ------------------------------------------------------------------
    # Prompt-refresh suggestion logic
    # ------------------------------------------------------------------
    def get_energy(self, character_id: str, *, days: int = 30) -> float:
        """Calculate accumulated emotional energy over recent *days*."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        energy = 0.0
        for rec in self.mm._records.values():  # pylint: disable=protected-access
            if rec.character_id != character_id or rec.archived or rec.created_at < cutoff:
                continue
            energy += abs(rec.sentiment) * rec.effective_weight()
        return energy

    def maybe_schedule_prompt_refresh(self, character_id: str) -> bool:
        """If energy exceeds threshold – schedule prompt refresh event.

        Returns True if event scheduled.
        """
        energy = self.get_energy(character_id)
        if energy < PROMPT_REFRESH_ENERGY_THRESHOLD:
            return False

        description = "Emotional memory threshold reached – consider updating system prompt."
        # Use MemoryManager's scheduler directly
        event_id = self.mm.scheduler.schedule_event(
            character_id=character_id,
            event_time=datetime.now(timezone.utc) + timedelta(minutes=1),
            description=description,
            reminder_minutes=0,
        )
        return bool(event_id)
