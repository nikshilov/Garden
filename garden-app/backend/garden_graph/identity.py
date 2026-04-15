"""Identity evolution system — Phase 4 (Growth).

Tracks how characters change over time. Personality is not static:
experiences reshape who they are. Each character has continuous
personality traits, growth memories that capture transformation
narratives, and milestones that mark significant firsts.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger("garden.identity")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TRAITS: Dict[str, float] = {
    "openness": 0.5,
    "assertiveness": 0.5,
    "warmth": 0.5,
    "introspection": 0.5,
    "playfulness": 0.5,
    "resilience": 0.5,
}

MILESTONE_TYPES = {
    "first_conversation",
    "first_disagreement",
    "first_personal_share",
    "first_deep_night_talk",
    "first_laugh",
    "first_comfort",
    "hundredth_conversation",
    "five_hundredth_conversation",
}

# Conversation-count milestones: count -> milestone_type
_COUNT_MILESTONES: Dict[int, str] = {
    10: "tenth_conversation",
    50: "fiftieth_conversation",
    100: "hundredth_conversation",
    500: "five_hundredth_conversation",
    1000: "thousandth_conversation",
}

# Human-readable trait descriptions for prompt rendering
_TRAIT_DESCRIPTIONS: Dict[str, Dict[str, str]] = {
    "openness": {
        "high": "open to new ideas and experiences",
        "low": "cautious about unfamiliar ideas",
    },
    "assertiveness": {
        "high": "assertive and direct in expressing opinions",
        "low": "reserved and accommodating",
    },
    "warmth": {
        "high": "warm and empathetic",
        "low": "emotionally reserved",
    },
    "introspection": {
        "high": "deeply introspective",
        "low": "action-oriented rather than reflective",
    },
    "playfulness": {
        "high": "playful and humorous",
        "low": "serious and measured",
    },
    "resilience": {
        "high": "resilient and quick to recover",
        "low": "sensitive and slow to recover from setbacks",
    },
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class GrowthMemory:
    """A milestone growth narrative capturing how the character changed."""

    id: str
    text: str  # e.g. "I used to avoid conflict, but after that conversation about boundaries..."
    trait_changes: Dict[str, float]  # which traits shifted and by how much
    created_at: str  # ISO 8601
    permanent: bool = True  # growth memories resist decay

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "trait_changes": self.trait_changes,
            "created_at": self.created_at,
            "permanent": self.permanent,
        }

    @classmethod
    def from_dict(cls, data: dict) -> GrowthMemory:
        return cls(
            id=data["id"],
            text=data["text"],
            trait_changes=data.get("trait_changes", {}),
            created_at=data["created_at"],
            permanent=data.get("permanent", True),
        )


@dataclass
class Milestone:
    """A significant first moment in the character's life."""

    id: str
    milestone_type: str  # e.g. "first_conversation", "first_disagreement"
    description: str
    created_at: str  # ISO 8601
    permanent: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "milestone_type": self.milestone_type,
            "description": self.description,
            "created_at": self.created_at,
            "permanent": self.permanent,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Milestone:
        return cls(
            id=data["id"],
            milestone_type=data["milestone_type"],
            description=data["description"],
            created_at=data["created_at"],
            permanent=data.get("permanent", True),
        )


@dataclass
class CharacterIdentity:
    """Full identity state for a single character."""

    char_id: str
    traits: Dict[str, float]  # the 6 personality traits, each 0.0-1.0
    evolved_prompt: str  # mutable identity text that grows over time
    growth_memories: List[GrowthMemory]
    milestones: List[Milestone]
    conversation_count: int
    created_at: str  # ISO 8601
    last_updated: str  # ISO 8601

    def to_dict(self) -> dict:
        return {
            "char_id": self.char_id,
            "traits": self.traits,
            "evolved_prompt": self.evolved_prompt,
            "growth_memories": [gm.to_dict() for gm in self.growth_memories],
            "milestones": [m.to_dict() for m in self.milestones],
            "conversation_count": self.conversation_count,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CharacterIdentity:
        return cls(
            char_id=data["char_id"],
            traits=data.get("traits", dict(DEFAULT_TRAITS)),
            evolved_prompt=data.get("evolved_prompt", ""),
            growth_memories=[
                GrowthMemory.from_dict(gm) for gm in data.get("growth_memories", [])
            ],
            milestones=[
                Milestone.from_dict(m) for m in data.get("milestones", [])
            ],
            conversation_count=data.get("conversation_count", 0),
            created_at=data["created_at"],
            last_updated=data["last_updated"],
        )


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class IdentityManager:
    """Manages identity evolution for all characters.

    Handles trait tracking, growth memory recording, milestone detection,
    and prompt segment generation. Persists state as JSON files in the
    data directory (one file per character).
    """

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            data_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "data"
            )
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self._identities: Dict[str, CharacterIdentity] = {}

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def get_or_create(self, char_id: str) -> CharacterIdentity:
        """Return the identity for *char_id*, creating it with defaults if needed."""
        if char_id in self._identities:
            return self._identities[char_id]

        # Try loading from disk first
        identity = self.load(char_id)
        if identity is not None:
            self._identities[char_id] = identity
            return identity

        # Create fresh identity with default traits
        now = datetime.now(timezone.utc).isoformat()
        identity = CharacterIdentity(
            char_id=char_id,
            traits=dict(DEFAULT_TRAITS),
            evolved_prompt="",
            growth_memories=[],
            milestones=[],
            conversation_count=0,
            created_at=now,
            last_updated=now,
        )
        self._identities[char_id] = identity
        self.save(char_id)
        logger.info(f"[{char_id}] Created new identity with default traits")
        return identity

    def update_traits(self, char_id: str, deltas: Dict[str, float]) -> Dict[str, float]:
        """Apply incremental trait shifts and clamp each to [0.0, 1.0].

        Returns the updated traits dict.
        """
        identity = self.get_or_create(char_id)

        for trait, delta in deltas.items():
            if trait not in identity.traits:
                logger.warning(f"[{char_id}] Unknown trait '{trait}', skipping")
                continue
            old_val = identity.traits[trait]
            new_val = max(0.0, min(1.0, old_val + delta))
            if new_val != old_val:
                identity.traits[trait] = new_val
                logger.debug(
                    f"[{char_id}] Trait '{trait}': {old_val:.3f} -> {new_val:.3f} (delta={delta:+.3f})"
                )

        identity.last_updated = datetime.now(timezone.utc).isoformat()
        self.save(char_id)
        return dict(identity.traits)

    def record_growth(
        self,
        char_id: str,
        text: str,
        trait_changes: Dict[str, float],
    ) -> GrowthMemory:
        """Record a growth memory — a narrative of how the character changed."""
        identity = self.get_or_create(char_id)

        memory = GrowthMemory(
            id=f"growth_{uuid.uuid4().hex[:12]}",
            text=text,
            trait_changes=trait_changes,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        identity.growth_memories.append(memory)
        identity.last_updated = datetime.now(timezone.utc).isoformat()
        self.save(char_id)
        logger.info(f"[{char_id}] Growth memory recorded: {text[:60]}...")
        return memory

    def check_milestone(
        self, char_id: str, event_type: str, description: str
    ) -> Optional[Milestone]:
        """Detect and record a milestone if this type has not been recorded yet.

        Returns the new Milestone if created, or None if already recorded.
        """
        identity = self.get_or_create(char_id)

        # Check if this milestone type already exists
        existing_types = {m.milestone_type for m in identity.milestones}
        if event_type in existing_types:
            return None

        milestone = Milestone(
            id=f"mile_{uuid.uuid4().hex[:12]}",
            milestone_type=event_type,
            description=description,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        identity.milestones.append(milestone)
        identity.last_updated = datetime.now(timezone.utc).isoformat()
        self.save(char_id)
        logger.info(f"[{char_id}] Milestone achieved: {event_type} — {description}")
        return milestone

    def increment_conversation(self, char_id: str) -> Optional[Milestone]:
        """Bump the conversation count and check for count-based milestones.

        Returns a Milestone if one was triggered, otherwise None.
        """
        identity = self.get_or_create(char_id)
        identity.conversation_count += 1
        identity.last_updated = datetime.now(timezone.utc).isoformat()

        count = identity.conversation_count
        logger.debug(f"[{char_id}] Conversation count: {count}")

        # Check for count-based milestones
        milestone_type = _COUNT_MILESTONES.get(count)
        if milestone_type is not None:
            milestone = self.check_milestone(
                char_id,
                milestone_type,
                f"Reached {count} conversations together",
            )
            self.save(char_id)
            return milestone

        self.save(char_id)
        return None

    # ------------------------------------------------------------------
    # Prompt generation
    # ------------------------------------------------------------------

    def identity_prompt_segment(self, char_id: str) -> str:
        """Build an identity segment for injection into the character's system prompt.

        Only includes traits that deviate notably from 0.5 (abs > 0.15)
        and the most recent growth memories.
        """
        identity = self.get_or_create(char_id)
        parts: List[str] = []

        # Evolved prompt
        if identity.evolved_prompt:
            parts.append("YOUR EVOLVED IDENTITY:")
            parts.append(identity.evolved_prompt)
            parts.append("")

        # Personality traits — only notable deviations
        trait_lines: List[str] = []
        for trait, value in identity.traits.items():
            deviation = value - 0.5
            if abs(deviation) <= 0.15:
                continue
            desc_map = _TRAIT_DESCRIPTIONS.get(trait)
            if desc_map is None:
                continue
            direction = "high" if deviation > 0 else "low"
            qualifier = self._qualify_deviation(abs(deviation))
            trait_lines.append(
                f"- You are {qualifier}{desc_map[direction]} ({trait}: {value:.1f})"
            )

        if trait_lines:
            parts.append("YOUR PERSONALITY TRAITS:")
            parts.extend(trait_lines)
            parts.append("")

        # Growth moments — last 3
        recent_growth = identity.growth_memories[-3:]
        if recent_growth:
            parts.append("GROWTH MOMENTS:")
            for gm in recent_growth:
                parts.append(f'- "{gm.text}"')
            parts.append("")

        return "\n".join(parts)

    @staticmethod
    def _qualify_deviation(abs_deviation: float) -> str:
        """Return an adverb qualifier based on how far a trait deviates from neutral."""
        if abs_deviation > 0.35:
            return "deeply "
        if abs_deviation > 0.25:
            return "notably "
        return ""

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _file_path(self, char_id: str) -> str:
        return os.path.join(self.data_dir, f"identity_{char_id}.json")

    def save(self, char_id: str) -> None:
        """Persist identity state for *char_id* to disk."""
        identity = self._identities.get(char_id)
        if identity is None:
            return

        path = self._file_path(char_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(identity.to_dict(), f, ensure_ascii=False, indent=2)
            logger.debug(f"[{char_id}] Identity saved to {path}")
        except Exception as e:
            logger.error(f"[{char_id}] Failed to save identity: {e}")

    def load(self, char_id: str) -> Optional[CharacterIdentity]:
        """Load identity state for *char_id* from disk. Returns None if missing."""
        path = self._file_path(char_id)
        if not os.path.exists(path):
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            identity = CharacterIdentity.from_dict(data)
            logger.debug(f"[{char_id}] Identity loaded from {path}")
            return identity
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"[{char_id}] Failed to load identity from {path}: {e}")
            return None
