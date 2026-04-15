"""Narrative Arc Tracker — tracks emotional trajectory of ongoing story.

Phase B of Garden v2.  Maintains the arc of the user-companion relationship
over time, advancing through phases that mirror therapeutic relationship
development.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("garden.narrative_arc")


# ---------------------------------------------------------------------------
# Arc phases
# ---------------------------------------------------------------------------

class ArcPhase(str, Enum):
    """Narrative arc phases — mirrors therapeutic relationship development."""
    establishing = "establishing"    # Building initial rapport and safety
    deepening = "deepening"          # Growing trust, sharing more
    testing = "testing"              # User tests boundaries, authenticity
    crisis = "crisis"                # Emotional rupture or challenge
    repair = "repair"                # Working through the crisis
    integration = "integration"      # Deeper understanding, stable bond


# Phase ordering for advancement logic
_PHASE_ORDER = list(ArcPhase)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ArcEvent:
    """A single event in the narrative arc timeline."""
    timestamp: str
    phase: str
    event_type: str        # e.g. "message", "milestone", "phase_change", "mirror_trigger"
    description: str
    emotional_intensity: float = 0.0   # 0.0 to 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "phase": self.phase,
            "event_type": self.event_type,
            "description": self.description,
            "emotional_intensity": self.emotional_intensity,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArcEvent":
        return cls(
            timestamp=data["timestamp"],
            phase=data["phase"],
            event_type=data["event_type"],
            description=data["description"],
            emotional_intensity=data.get("emotional_intensity", 0.0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PhaseTransition:
    """Records a phase transition with context."""
    from_phase: str
    to_phase: str
    timestamp: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_phase": self.from_phase,
            "to_phase": self.to_phase,
            "timestamp": self.timestamp,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PhaseTransition":
        return cls(
            from_phase=data["from_phase"],
            to_phase=data["to_phase"],
            timestamp=data["timestamp"],
            reason=data["reason"],
        )


# ---------------------------------------------------------------------------
# Phase advancement thresholds
# ---------------------------------------------------------------------------

# Minimum events per phase before advancement is considered
PHASE_MIN_EVENTS: Dict[ArcPhase, int] = {
    ArcPhase.establishing: 3,
    ArcPhase.deepening: 5,
    ArcPhase.testing: 3,
    ArcPhase.crisis: 2,
    ArcPhase.repair: 3,
    ArcPhase.integration: 5,
}

# Average intensity thresholds for phase advancement
PHASE_INTENSITY_THRESHOLD: Dict[ArcPhase, float] = {
    ArcPhase.establishing: 0.3,    # enough warmth to move on
    ArcPhase.deepening: 0.5,       # emotional depth reached
    ArcPhase.testing: 0.6,         # tension has been present
    ArcPhase.crisis: 0.7,          # crisis intensity peaked
    ArcPhase.repair: 0.4,          # intensity settling
    ArcPhase.integration: 0.3,     # stable, grounded
}

# Keywords/signals that suggest crisis entry
CRISIS_SIGNALS = [
    "angry", "hurt", "betrayed", "disappointed", "frustrated",
    "don't trust", "you don't understand", "leave me alone",
    "this isn't working", "confused", "lost", "broken",
]

# Signals that suggest repair is happening
REPAIR_SIGNALS = [
    "sorry", "understand", "forgive", "trying", "appreciate",
    "thank you", "I see", "you're right", "let's try",
    "I was wrong", "together",
]

# Mirror handoff triggers — moments where a therapist/mirror companion
# could add value
MIRROR_TRIGGERS = [
    "pattern_recognition",    # User repeating a behavioral pattern
    "wound_activation",       # Core wound triggered
    "breakthrough_moment",    # Significant insight
    "resistance",             # User resisting growth
    "integration_ready",      # Ready for deeper work
]


# ---------------------------------------------------------------------------
# NarrativeArc class
# ---------------------------------------------------------------------------

class NarrativeArc:
    """Tracks and manages the emotional trajectory of a user's story."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.current_phase: ArcPhase = ArcPhase.establishing
        self.key_events: List[ArcEvent] = []
        self.intensity_curve: List[float] = []  # rolling intensity values
        self.phase_transitions: List[PhaseTransition] = []
        self.created_at: str = datetime.now(timezone.utc).isoformat()
        self.updated_at: str = self.created_at

        # Per-phase event counters
        self._phase_event_counts: Dict[str, int] = {p.value: 0 for p in ArcPhase}

    # --- Core API ---

    def update_arc(self, session_event: Dict[str, Any]) -> ArcEvent:
        """Process a session event and update the arc state.

        Args:
            session_event: Dict with keys:
                - description (str): what happened
                - emotional_intensity (float): 0.0-1.0
                - event_type (str, optional): defaults to "message"
                - metadata (dict, optional): extra data

        Returns:
            The created ArcEvent.
        """
        now = datetime.now(timezone.utc).isoformat()
        intensity = max(0.0, min(1.0, session_event.get("emotional_intensity", 0.0)))

        event = ArcEvent(
            timestamp=now,
            phase=self.current_phase.value,
            event_type=session_event.get("event_type", "message"),
            description=session_event.get("description", ""),
            emotional_intensity=intensity,
            metadata=session_event.get("metadata", {}),
        )

        self.key_events.append(event)
        self.intensity_curve.append(intensity)
        self._phase_event_counts[self.current_phase.value] += 1
        self.updated_at = now

        # Check for crisis signals in description
        desc_lower = event.description.lower()
        if self.current_phase in (ArcPhase.establishing, ArcPhase.deepening, ArcPhase.testing):
            if any(signal in desc_lower for signal in CRISIS_SIGNALS) and intensity > 0.6:
                self._transition_to(ArcPhase.crisis, f"Crisis signal detected: {event.description[:80]}")

        # Check for repair signals during crisis
        if self.current_phase == ArcPhase.crisis:
            if any(signal in desc_lower for signal in REPAIR_SIGNALS):
                self._transition_to(ArcPhase.repair, f"Repair signal detected: {event.description[:80]}")

        # Check for natural phase advancement
        if self.should_advance_phase():
            next_phase = self._get_next_phase()
            if next_phase:
                self._transition_to(next_phase, f"Natural advancement after {self._phase_event_counts[self.current_phase.value]} events")

        return event

    def get_current_phase(self) -> ArcPhase:
        """Return the current arc phase."""
        return self.current_phase

    def should_advance_phase(self) -> bool:
        """Determine if the current phase should advance based on thresholds."""
        phase = self.current_phase
        event_count = self._phase_event_counts.get(phase.value, 0)
        min_events = PHASE_MIN_EVENTS.get(phase, 3)

        if event_count < min_events:
            return False

        # Calculate average intensity for current phase events
        phase_events = [e for e in self.key_events if e.phase == phase.value]
        if not phase_events:
            return False

        avg_intensity = sum(e.emotional_intensity for e in phase_events) / len(phase_events)
        threshold = PHASE_INTENSITY_THRESHOLD.get(phase, 0.3)

        return avg_intensity >= threshold

    def get_mirror_handoff_triggers(self) -> List[str]:
        """Return any active mirror handoff triggers based on current state.

        Mirror handoff triggers indicate moments where a therapeutic mirror
        companion could add value to the interaction.
        """
        triggers: List[str] = []

        if not self.key_events:
            return triggers

        recent = self.key_events[-5:]

        # Pattern recognition: repeated high-intensity events
        if len(recent) >= 3:
            high_intensity = [e for e in recent if e.emotional_intensity > 0.7]
            if len(high_intensity) >= 2:
                triggers.append("pattern_recognition")

        # Wound activation: crisis phase with high intensity
        if self.current_phase == ArcPhase.crisis:
            triggers.append("wound_activation")

        # Breakthrough: transition from crisis to repair
        if self.phase_transitions:
            last_transition = self.phase_transitions[-1]
            if last_transition.from_phase == ArcPhase.crisis.value and last_transition.to_phase == ArcPhase.repair.value:
                triggers.append("breakthrough_moment")

        # Resistance: in testing phase with consistently high tension
        if self.current_phase == ArcPhase.testing:
            testing_events = [e for e in self.key_events if e.phase == ArcPhase.testing.value]
            if len(testing_events) >= 3:
                avg = sum(e.emotional_intensity for e in testing_events[-3:]) / 3
                if avg > 0.6:
                    triggers.append("resistance")

        # Integration ready: stable low intensity in repair/integration
        if self.current_phase in (ArcPhase.repair, ArcPhase.integration):
            if len(recent) >= 3:
                avg = sum(e.emotional_intensity for e in recent) / len(recent)
                if avg < 0.3:
                    triggers.append("integration_ready")

        return triggers

    # --- Internal helpers ---

    def _transition_to(self, new_phase: ArcPhase, reason: str) -> None:
        """Record a phase transition."""
        now = datetime.now(timezone.utc).isoformat()
        transition = PhaseTransition(
            from_phase=self.current_phase.value,
            to_phase=new_phase.value,
            timestamp=now,
            reason=reason,
        )
        self.phase_transitions.append(transition)
        self.current_phase = new_phase
        self.updated_at = now

        logger.info(
            f"[{self.user_id}] Arc phase transition: "
            f"{transition.from_phase} -> {transition.to_phase} ({reason})"
        )

    def _get_next_phase(self) -> Optional[ArcPhase]:
        """Get the next phase in the natural progression."""
        try:
            idx = _PHASE_ORDER.index(self.current_phase)
            if idx < len(_PHASE_ORDER) - 1:
                return _PHASE_ORDER[idx + 1]
        except ValueError:
            pass
        return None

    # --- Serialization ---

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "current_phase": self.current_phase.value,
            "key_events": [e.to_dict() for e in self.key_events],
            "intensity_curve": self.intensity_curve,
            "phase_transitions": [t.to_dict() for t in self.phase_transitions],
            "phase_event_counts": self._phase_event_counts,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NarrativeArc":
        arc = cls(user_id=data["user_id"])
        arc.current_phase = ArcPhase(data["current_phase"])
        arc.key_events = [ArcEvent.from_dict(e) for e in data.get("key_events", [])]
        arc.intensity_curve = data.get("intensity_curve", [])
        arc.phase_transitions = [PhaseTransition.from_dict(t) for t in data.get("phase_transitions", [])]
        arc._phase_event_counts = data.get("phase_event_counts", {p.value: 0 for p in ArcPhase})
        arc.created_at = data.get("created_at", "")
        arc.updated_at = data.get("updated_at", "")
        return arc


# ---------------------------------------------------------------------------
# Persistence — JSON file per user in data/narrative_arcs/
# ---------------------------------------------------------------------------

def _get_arcs_dir() -> str:
    """Return (and create) the directory for narrative arc storage."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "narrative_arcs")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def save_arc(arc: NarrativeArc) -> str:
    """Save a narrative arc to disk.  Returns the file path."""
    dir_path = _get_arcs_dir()
    file_path = os.path.join(dir_path, f"{arc.user_id}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(arc.to_dict(), f, ensure_ascii=False, indent=2)
    logger.info(f"Saved narrative arc for {arc.user_id} to {file_path}")
    return file_path


def load_arc(user_id: str) -> Optional[NarrativeArc]:
    """Load a narrative arc from disk.  Returns None if not found."""
    dir_path = _get_arcs_dir()
    file_path = os.path.join(dir_path, f"{user_id}.json")
    if not os.path.exists(file_path):
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return NarrativeArc.from_dict(data)
