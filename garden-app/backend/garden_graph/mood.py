"""Lightweight random mood generator and tracker for characters.

The system uses the same 11 Plutchik/Valence‐Arousal‐Dominance axes already
present in the memory sentiment analysis but limits the magnitude to a
moderate range (−0.4 … +0.4).  A mood is intended as a *temporary bias* that
slowly decays over the course of a (simulated) day.
"""
from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field

logger = logging.getLogger("garden.mood")
from datetime import datetime, timedelta, timezone
from typing import Dict

# Base axes + extended traits
EMOTION_AXES = [
    "joy",
    "trust",
    "fear",
    "surprise",
    "sadness",
    "disgust",
    "anger",
    "anticipation",
    "valence",
    "arousal",
    "dominance",
    # Extended traits
    "flirt",      # playfully romantic disposition
    "playfulness",
    "shadow",     # underlying brooding / cynicism

]


@dataclass
class MoodState:
    """Holds current mood vector and timestamp when it was set."""

    vector: Dict[str, float] = field(default_factory=dict)
    set_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def decay(self, half_life_hours: float = 12.0) -> "MoodState":
        """Return a decayed copy of this mood according to half-life."""
        hrs = (datetime.now(timezone.utc) - self.set_at).total_seconds() / 3600.0
        factor = 0.5 ** (hrs / half_life_hours)
        decayed_vec = {k: v * factor for k, v in self.vector.items()}
        return MoodState(vector=decayed_vec, set_at=self.set_at)

    @property
    def valence(self) -> float:
        return self.vector.get("valence", 0.0)


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def generate_mood(previous_valence: float | None = None, sigma: float = 0.25) -> MoodState:
    """Generate a random daily mood vector.

    previous_valence – recent average valence to bias today’s mood.
    sigma            – standard deviation for gaussian noise.
    """
    rng = random.Random()
    vector: Dict[str, float] = {}

    bias = previous_valence or 0.0

    for axis in EMOTION_AXES:
        if axis == "valence":
            base = bias * 0.3  # small bias towards yesterday’s tone
        elif axis == "arousal":
            base = 0.0
        else:
            base = 0.0
        value = base + rng.gauss(0, sigma)
        vector[axis] = max(-0.4, min(0.4, value))
    return MoodState(vector=vector)

# Adjective mapping for prompt rendering
AXIS_ADJECTIVE = {
    "joy": "joyful",
    "trust": "trusting",
    "fear": "fearful",
    "surprise": "surprised",
    "sadness": "sad",
    "disgust": "disgusted",
    "anger": "angry",
    "anticipation": "anticipatory",
    "flirt": "flirty",
    "playfulness": "playful",
    "shadow": "brooding",
}
