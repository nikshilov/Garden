"""User Profile schema and persistence for Garden v2.

Stores the emotional landscape mapped by the Cartographer during onboarding.
Profiles are saved as JSON files in data/user_profiles/.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("garden.user_profile")

# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class SensoryDetail(BaseModel):
    """Detail for a single sensory channel."""
    triggers: List[str] = Field(default_factory=list)
    weight: float = 0.5


class SensoryProfile(BaseModel):
    """Which sensory channels dominate the user's emotional processing."""
    primary: str = "kinesthetic"
    secondary: str = "auditory"
    details: Dict[str, SensoryDetail] = Field(default_factory=dict)


class CoreWound(BaseModel):
    """The user's primary emotional wound."""
    type: str = ""
    narrative: str = ""
    origin_hints: List[str] = Field(default_factory=list)


class Trigger(BaseModel):
    """A specific emotional trigger."""
    stimulus: str
    reaction: str = ""
    intensity: float = 0.5


class HungerPart(BaseModel):
    """What one internal 'part' (IFS-informed) needs."""
    needs: str = ""
    feeds_on: str = ""


class HungerMap(BaseModel):
    """Map of internal parts and their emotional hungers."""
    child: HungerPart = Field(default_factory=HungerPart)
    teenager: HungerPart = Field(default_factory=HungerPart)
    adult: HungerPart = Field(default_factory=HungerPart)


class IntimacyProfile(BaseModel):
    """What feels safe, exciting, or threatening around intimacy."""
    safe: List[str] = Field(default_factory=list)
    exciting: List[str] = Field(default_factory=list)
    threatening: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-level profile
# ---------------------------------------------------------------------------


class UserProfile(BaseModel):
    """Full user profile produced by the Cartographer."""
    user_id: str
    version: int = 1
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    attachment_style: str = ""
    sensory_profile: SensoryProfile = Field(default_factory=SensoryProfile)
    core_wound: CoreWound = Field(default_factory=CoreWound)
    triggers: List[Trigger] = Field(default_factory=list)
    hunger_map: HungerMap = Field(default_factory=HungerMap)
    communication_preference: str = ""
    intimacy_profile: IntimacyProfile = Field(default_factory=IntimacyProfile)


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _profiles_dir() -> str:
    """Return (and create) the user_profiles data directory."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "user_profiles")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _profile_path(user_id: str) -> str:
    return os.path.join(_profiles_dir(), f"{user_id}.json")


def save_profile(profile: UserProfile) -> str:
    """Persist a UserProfile to disk. Returns the file path."""
    path = _profile_path(profile.user_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile.model_dump(), f, ensure_ascii=False, indent=2)
    logger.info(f"Saved profile for user {profile.user_id} to {path}")
    return path


def load_profile(user_id: str) -> Optional[UserProfile]:
    """Load a UserProfile from disk. Returns None if not found."""
    path = _profile_path(user_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return UserProfile(**data)
    except Exception as e:
        logger.error(f"Failed to load profile for {user_id}: {e}")
        return None


def update_profile(user_id: str, updates: dict) -> Optional[UserProfile]:
    """Apply partial updates to an existing profile.

    Returns the updated profile or None if the profile does not exist.
    """
    profile = load_profile(user_id)
    if profile is None:
        return None

    # Apply updates via model_copy (Pydantic v2)
    updated = profile.model_copy(update=updates)
    # Bump version on every update
    updated.version = profile.version + 1
    save_profile(updated)
    return updated
