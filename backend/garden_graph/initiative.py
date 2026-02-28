"""Initiative engine — Phase 5 (Voice).

Gives characters the ability to reach out to the user on their own.
During heartbeat, each character evaluates whether they have something
worth saying. The engine checks triggers in priority order and enforces
boundary rules (cooldowns, quiet hours, per-character disable).
"""
from __future__ import annotations

import json
import logging
import os
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

logger = logging.getLogger("garden.initiative")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
SETTINGS_PATH = os.path.join(DATA_DIR, "initiative_settings.json")
LAST_SEEN_PATH = os.path.join(DATA_DIR, "last_seen_times.json")
MOOD_PATH = os.path.join(DATA_DIR, "mood_states.json")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_INITIATIVES_PER_DAY = 1
COOLDOWN_HOURS = 24

# Loneliness thresholds (days since last contact)
LONELINESS_MILD_DAYS = 3
LONELINESS_MODERATE_DAYS = 7
LONELINESS_STRONG_DAYS = 14

# Mood valence threshold for extreme-mood trigger
MOOD_EXTREME_THRESHOLD = 0.3

# Dismiss decay: after N dismissals, reduce initiative probability
DISMISS_DECAY_BASE = 0.7  # probability multiplier per dismiss


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class InitiativeResult:
    """Describes why a character wants to reach out."""

    char_id: str
    trigger: str       # "loneliness", "insight", "event", "anniversary", "mood"
    priority: str      # "high", "medium", "low"
    context: str       # brief context for message generation
    created_at: str    # ISO 8601


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class InitiativeEngine:
    """Evaluates whether a character should proactively reach out."""

    def __init__(self, memory_manager=None):
        self.memory_manager = memory_manager
        self._cooldowns: Dict[str, datetime] = {}  # char_id -> last initiative time
        self._settings = self._load_settings()

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def evaluate(self, char_id: str, now: Optional[datetime] = None) -> Optional[InitiativeResult]:
        """Evaluate whether *char_id* should reach out right now.

        Returns an InitiativeResult if a trigger fires, None otherwise.
        Checks triggers in priority order:
          1. Scheduled event  (HIGH)
          2. Loneliness       (HIGH / MEDIUM / LOW depending on gap)
          3. Insight to share (MEDIUM)
          4. Anniversary      (MEDIUM)
          5. Extreme mood     (LOW)
        """
        if now is None:
            now = datetime.now(timezone.utc)

        # --- Boundary checks ---
        if not self._settings.get("enabled", True):
            logger.debug("[%s] Initiative globally disabled", char_id)
            return None

        if char_id in self._settings.get("disabled_characters", []):
            logger.debug("[%s] Initiative disabled for this character", char_id)
            return None

        if self._in_quiet_hours(now):
            logger.debug("[%s] Quiet hours active, skipping", char_id)
            return None

        if self._on_cooldown(char_id, now):
            logger.debug("[%s] Still on cooldown", char_id)
            return None

        # --- Dismiss probability decay ---
        dismiss_count = self._settings.get("dismissed_count", {}).get(char_id, 0)
        if dismiss_count > 0:
            keep_prob = DISMISS_DECAY_BASE ** dismiss_count
            if random.random() > keep_prob:
                logger.debug(
                    "[%s] Skipped due to dismiss decay (count=%d, prob=%.2f)",
                    char_id, dismiss_count, keep_prob,
                )
                return None

        # --- Trigger checks (priority order) ---

        # 1. Scheduled event
        result = self._check_scheduled_event(char_id, now)
        if result:
            self._record_cooldown(char_id, now)
            return result

        # 2. Loneliness
        result = self._check_loneliness(char_id, now)
        if result:
            self._record_cooldown(char_id, now)
            return result

        # 3. Insight to share (recent growth narrative)
        result = self._check_insight(char_id, now)
        if result:
            self._record_cooldown(char_id, now)
            return result

        # 4. Milestone anniversary
        result = self._check_anniversary_trigger(char_id, now)
        if result:
            self._record_cooldown(char_id, now)
            return result

        # 5. Extreme mood
        result = self._check_extreme_mood(char_id, now)
        if result:
            self._record_cooldown(char_id, now)
            return result

        return None

    # ------------------------------------------------------------------
    # Message generation
    # ------------------------------------------------------------------

    def generate_message(self, result: InitiativeResult, llm) -> str:
        """Generate a natural outreach message for the given initiative.

        Uses the character's personality template and the trigger context
        to produce a brief, in-character message (1-2 sentences).
        """
        from garden_graph.character import CHARACTER_TEMPLATES

        template = CHARACTER_TEMPLATES.get(result.char_id, {})
        char_name = template.get("name", result.char_id.capitalize())
        char_prompt = template.get("prompt", "")

        system = (
            f"{char_prompt}\n\n"
            f"You are reaching out to the user on your own — they did not message you.\n"
            f"Trigger: {result.trigger}\n"
            f"Context: {result.context}\n\n"
            f"Write a brief, natural message (1-2 sentences) as {char_name}. "
            f"It should feel genuine — not like a notification. "
            f"Use the same language the user usually speaks."
        )

        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            messages = [
                SystemMessage(content=system),
                HumanMessage(content="(Generate your outreach message now.)"),
            ]
            response = llm.invoke(messages)
            return response.content.strip()
        except Exception as e:
            logger.error("[%s] Failed to generate initiative message: %s", result.char_id, e)
            # Fallback: return a simple context-based message
            return result.context

    # ------------------------------------------------------------------
    # Trigger implementations
    # ------------------------------------------------------------------

    def _check_scheduled_event(self, char_id: str, now: datetime) -> Optional[InitiativeResult]:
        """Check if there is a pending scheduled event for this character."""
        if not self.memory_manager:
            return None

        try:
            pending = self.memory_manager.check_pending_events(char_id, now)
            if pending:
                event = pending[0]  # take the first pending event
                return InitiativeResult(
                    char_id=char_id,
                    trigger="event",
                    priority="high",
                    context=f"Scheduled event triggered: {event['description']}",
                    created_at=now.isoformat(),
                )
        except Exception as e:
            logger.warning("[%s] Error checking scheduled events: %s", char_id, e)

        return None

    def _check_loneliness(self, char_id: str, now: datetime) -> Optional[InitiativeResult]:
        """Check if it has been too long since last contact."""
        last_seen = self._get_last_seen(char_id)
        if last_seen is None:
            return None

        gap = now - last_seen
        days = gap.total_seconds() / 86400

        if days >= LONELINESS_STRONG_DAYS:
            return InitiativeResult(
                char_id=char_id,
                trigger="loneliness",
                priority="high",
                context=f"It's been {int(days)} days since last contact. "
                        f"It's been so long... are you okay?",
                created_at=now.isoformat(),
            )
        elif days >= LONELINESS_MODERATE_DAYS:
            return InitiativeResult(
                char_id=char_id,
                trigger="loneliness",
                priority="medium",
                context=f"It's been {int(days)} days since last contact. "
                        f"I miss our conversations.",
                created_at=now.isoformat(),
            )
        elif days >= LONELINESS_MILD_DAYS:
            return InitiativeResult(
                char_id=char_id,
                trigger="loneliness",
                priority="low",
                context=f"It's been {int(days)} days since last contact. "
                        f"I've been thinking about you.",
                created_at=now.isoformat(),
            )

        return None

    def _check_insight(self, char_id: str, now: datetime) -> Optional[InitiativeResult]:
        """Check if a recent reflection produced a growth narrative worth sharing."""
        try:
            from garden_graph.identity import IdentityManager
            identity_mgr = IdentityManager(DATA_DIR)
            identity = identity_mgr.load(char_id)
            if identity is None:
                return None

            # Look for growth memories created in the last 48 hours
            cutoff = now - timedelta(hours=48)
            recent_growth = [
                gm for gm in identity.growth_memories
                if datetime.fromisoformat(gm.created_at) > cutoff
            ]
            if recent_growth:
                latest = recent_growth[-1]
                return InitiativeResult(
                    char_id=char_id,
                    trigger="insight",
                    priority="medium",
                    context=f"Recent growth insight: {latest.text}",
                    created_at=now.isoformat(),
                )
        except Exception as e:
            logger.warning("[%s] Error checking insights: %s", char_id, e)

        return None

    def _check_anniversary_trigger(self, char_id: str, now: datetime) -> Optional[InitiativeResult]:
        """Check if today is the anniversary of the first conversation."""
        if self._check_anniversary(char_id, now):
            return InitiativeResult(
                char_id=char_id,
                trigger="anniversary",
                priority="medium",
                context="Today is the anniversary of our first conversation.",
                created_at=now.isoformat(),
            )
        return None

    def _check_extreme_mood(self, char_id: str, now: datetime) -> Optional[InitiativeResult]:
        """Check if the character's mood valence is extreme enough to trigger outreach."""
        try:
            if not os.path.exists(MOOD_PATH):
                return None

            with open(MOOD_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            entry = data.get(char_id)
            if not entry:
                return None

            valence = entry.get("vector", {}).get("valence", 0.0)
            if abs(valence) > MOOD_EXTREME_THRESHOLD:
                if valence > 0:
                    context = "Feeling unusually positive and want to share the energy."
                else:
                    context = "Feeling heavy today and could use someone to talk to."
                return InitiativeResult(
                    char_id=char_id,
                    trigger="mood",
                    priority="low",
                    context=context,
                    created_at=now.isoformat(),
                )
        except Exception as e:
            logger.warning("[%s] Error checking mood: %s", char_id, e)

        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_last_seen(self, char_id: str) -> Optional[datetime]:
        """Read last seen time from the shared last_seen_times.json file."""
        try:
            if not os.path.exists(LAST_SEEN_PATH):
                return None
            with open(LAST_SEEN_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            timestamp = data.get(char_id)
            if timestamp:
                return datetime.fromisoformat(timestamp)
        except Exception as e:
            logger.warning("[%s] Error reading last seen time: %s", char_id, e)
        return None

    def _check_anniversary(self, char_id: str, now: datetime) -> bool:
        """Check if today matches the month+day of the first_conversation milestone."""
        try:
            from garden_graph.identity import IdentityManager
            identity_mgr = IdentityManager(DATA_DIR)
            identity = identity_mgr.load(char_id)
            if identity is None:
                return False

            for milestone in identity.milestones:
                if milestone.milestone_type == "first_conversation":
                    milestone_dt = datetime.fromisoformat(milestone.created_at)
                    # Same month and day, but not the same year (actual anniversary)
                    if (milestone_dt.month == now.month
                            and milestone_dt.day == now.day
                            and milestone_dt.year != now.year):
                        return True
            return False
        except Exception as e:
            logger.warning("[%s] Error checking anniversary: %s", char_id, e)
            return False

    def _on_cooldown(self, char_id: str, now: datetime) -> bool:
        """Return True if the character initiated within the last COOLDOWN_HOURS."""
        last = self._cooldowns.get(char_id)
        if last is None:
            return False
        return (now - last) < timedelta(hours=COOLDOWN_HOURS)

    def _record_cooldown(self, char_id: str, now: datetime) -> None:
        """Record that the character just initiated."""
        self._cooldowns[char_id] = now

    def _in_quiet_hours(self, now: datetime) -> bool:
        """Check whether current time falls within quiet hours.

        Uses QUIET_HOURS_START / QUIET_HOURS_END env vars (default 23-08).
        Compares against the hour component of *now* (assumed to be in
        the user's timezone, or UTC if not set).
        """
        quiet_start = int(os.getenv("QUIET_HOURS_START", str(self._settings.get("quiet_start", 23))))
        quiet_end = int(os.getenv("QUIET_HOURS_END", str(self._settings.get("quiet_end", 8))))
        hour = now.hour

        if quiet_start > quiet_end:
            # Wraps midnight, e.g. 23:00 - 08:00
            return hour >= quiet_start or hour < quiet_end
        else:
            return quiet_start <= hour < quiet_end

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------

    def _load_settings(self) -> dict:
        """Load initiative settings from disk, or return defaults."""
        try:
            if os.path.exists(SETTINGS_PATH):
                with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning("Failed to load initiative settings: %s", e)

        return {
            "enabled": True,
            "quiet_start": 23,
            "quiet_end": 8,
            "disabled_characters": [],
            "dismissed_count": {},
        }

    def _save_settings(self) -> None:
        """Persist current settings to disk."""
        try:
            os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Failed to save initiative settings: %s", e)

    def disable_character(self, char_id: str) -> None:
        """Disable initiative for a specific character."""
        disabled = self._settings.setdefault("disabled_characters", [])
        if char_id not in disabled:
            disabled.append(char_id)
            self._save_settings()
            logger.info("[%s] Initiative disabled", char_id)

    def enable_character(self, char_id: str) -> None:
        """Re-enable initiative for a specific character."""
        disabled = self._settings.get("disabled_characters", [])
        if char_id in disabled:
            disabled.remove(char_id)
            self._save_settings()
            logger.info("[%s] Initiative re-enabled", char_id)

    def record_dismissed(self, char_id: str) -> None:
        """Record that the user dismissed an initiative from this character.

        Each dismiss reduces the future probability of the character
        initiating again (exponential decay via DISMISS_DECAY_BASE).
        """
        counts = self._settings.setdefault("dismissed_count", {})
        counts[char_id] = counts.get(char_id, 0) + 1
        self._save_settings()
        logger.info(
            "[%s] Initiative dismissed (total: %d)", char_id, counts[char_id],
        )
