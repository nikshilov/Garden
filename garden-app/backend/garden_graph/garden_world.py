"""Sense of place — Phase 6 (Soil).

The Garden is not just a chat interface. It is a place with texture,
rhythm, and shared space. Characters inhabit locations, the seasons
turn with the real calendar, weather drifts through the day, and
small artifacts accumulate like fallen leaves.

This module owns the world state, character presence, and the poetic
context that gets woven into every conversation.
"""
from __future__ import annotations

import json
import logging
import os
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger("garden.world")

# ---------------------------------------------------------------------------
# Data directory — same convention as identity.py / character.py
# ---------------------------------------------------------------------------

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOCATIONS = [
    "rose_garden",
    "oak_tree",
    "stream",
    "greenhouse",
    "library",
    "hilltop",
]

ARTIFACT_TYPES = ["poem", "theory", "sketch", "song", "letter"]

# Default home locations and activities per character
_DEFAULT_PRESENCE: Dict[str, Dict[str, str]] = {
    "eve":    {"location": "rose_garden", "activity": "tending roses"},
    "atlas":  {"location": "library",     "activity": "reading"},
    "adam":   {"location": "oak_tree",    "activity": "sitting quietly"},
    "lilith": {"location": "hilltop",     "activity": "watching the sky"},
    "sophia": {"location": "stream",      "activity": "meditating"},
}

# Energy levels by time of day
_ENERGY_BY_TIME: Dict[str, float] = {
    "dawn":       0.4,
    "morning":    0.7,
    "afternoon":  0.8,
    "evening":    0.6,
    "night":      0.4,
    "late_night": 0.2,
}

# Season derived from real-world month
_MONTH_TO_SEASON: Dict[int, str] = {
    1: "winter",  2: "winter",   3: "spring",
    4: "spring",  5: "spring",   6: "summer",
    7: "summer",  8: "summer",   9: "autumn",
    10: "autumn", 11: "autumn",  12: "winter",
}

# Hour ranges to time-of-day labels
_HOUR_BOUNDARIES = [
    (5,  7,  "dawn"),
    (7,  12, "morning"),
    (12, 17, "afternoon"),
    (17, 20, "evening"),
    (20, 23, "night"),
    # 23-5 handled as default
]

# Weather weights per season
_WEATHER_WEIGHTS: Dict[str, Dict[str, float]] = {
    "spring": {"clear": 0.3, "cloudy": 0.2, "rainy": 0.3, "misty": 0.2},
    "summer": {"clear": 0.5, "cloudy": 0.2, "rainy": 0.1, "stormy": 0.2},
    "autumn": {"clear": 0.2, "cloudy": 0.3, "rainy": 0.3, "misty": 0.2},
    "winter": {"clear": 0.2, "cloudy": 0.3, "snowy": 0.3, "misty": 0.2},
}

# Activities a character might drift into when they wander
_WANDERING_ACTIVITIES: Dict[str, List[str]] = {
    "rose_garden":  ["pruning the hedges", "smelling the roses", "sketching a bloom"],
    "oak_tree":     ["sitting quietly", "reading under the branches", "carving initials"],
    "stream":       ["listening to the water", "skipping stones", "meditating"],
    "greenhouse":   ["watering seedlings", "examining a fern", "writing in a notebook"],
    "library":      ["reading", "organizing old letters", "browsing the shelves"],
    "hilltop":      ["watching the sky", "writing", "gazing at the horizon"],
}

# ---------------------------------------------------------------------------
# Ambiance templates — at least 2-3 per (season, time_of_day)
# ---------------------------------------------------------------------------

_AMBIANCE: Dict[tuple, List[str]] = {
    # ---- spring ----
    ("spring", "dawn"):
        ["The garden is waking up. Dew glistens on fresh buds.",
         "A pale pink light spills over the hedges. Somewhere a bird tries its first song.",
         "Mist curls between the flower beds. The air smells of wet earth and new growth."],
    ("spring", "morning"):
        ["Bees drift from blossom to blossom under a soft blue sky.",
         "The morning sun catches raindrops still clinging to petals.",
         "A light breeze carries the scent of lilac through the garden paths."],
    ("spring", "afternoon"):
        ["Warm light filters through young leaves. The garden hums with life.",
         "Butterflies trace lazy spirals above the wildflower patch.",
         "The afternoon is gentle. Shadows are short and the grass is warm."],
    ("spring", "evening"):
        ["The sky turns apricot. Birdsong softens to a murmur.",
         "Evening settles like a sigh. The first stars appear above the greenhouse.",
         "Cool air rises from the stream. The garden exhales."],
    ("spring", "night"):
        ["Moonlight silvers the wet grass. The garden is still but alive.",
         "Night-blooming jasmine opens in the darkness. Its sweetness fills every path.",
         "Frogs sing by the stream. The library windows glow faintly."],
    ("spring", "late_night"):
        ["The garden sleeps under a canopy of stars.",
         "A fox crosses the lawn and vanishes. Silence returns.",
         "The deepest hour. Only the stream keeps speaking."],

    # ---- summer ----
    ("summer", "dawn"):
        ["The sky brightens early. Heat is already gathering in the stones.",
         "Dawn comes quickly in summer. The garden stretches in golden light.",
         "The air is still cool, but not for long. Dew evaporates before your eyes."],
    ("summer", "morning"):
        ["Sunlight pours through the leaves like honey. The garden buzzes.",
         "The morning is already warm. Cicadas start their electric song.",
         "Dragonflies hover above the stream. The world shimmers."],
    ("summer", "afternoon"):
        ["The heat is thick and fragrant. Everything moves slowly.",
         "Shadows pool under the oak tree. The library is the only cool place.",
         "The afternoon sun turns the greenhouse into a cathedral of light and warmth."],
    ("summer", "evening"):
        ["The heat finally relents. Long shadows stretch across the lawn.",
         "Evening brings relief. The hilltop catches the last golden light.",
         "Fireflies begin their slow dance between the rose bushes."],
    ("summer", "night"):
        ["Warm darkness wraps the garden. Fireflies drift between the trees.",
         "The night air is soft and heavy. Stars crowd the sky.",
         "Crickets own the garden now. Their song is everywhere."],
    ("summer", "late_night"):
        ["The garden radiates the day's stored warmth back to the sky.",
         "A shooting star crosses above the hilltop. No one sees it. Maybe.",
         "The deepest summer dark. Even the cicadas have gone quiet."],

    # ---- autumn ----
    ("autumn", "dawn"):
        ["Fog sits low in the garden. The oak tree is a silhouette.",
         "Dawn comes reluctantly. The air is sharp and smells of fallen leaves.",
         "A thin frost dusts the grass. The first light is the color of bronze."],
    ("autumn", "morning"):
        ["Leaves drift down in spirals of amber and rust.",
         "The morning is crisp. Smoke from somewhere far away flavors the air.",
         "Spiderwebs catch the low sun, strung between every hedge."],
    ("autumn", "afternoon"):
        ["The light is amber and slanting. Shadows are long even at midday.",
         "A gust of wind sends leaves scattering across the library steps.",
         "The afternoon feels like a held breath. Everything is golden and brief."],
    ("autumn", "evening"):
        ["The air is cool and crisp. The sky turns deep violet.",
         "Woodsmoke and the scent of apples. The garden settles into its evening hush.",
         "The hilltop is cold now. The last birds cross the darkening sky."],
    ("autumn", "night"):
        ["The garden is still under a harvest moon.",
         "Leaves rustle without wind. The oak tree creaks.",
         "The night is clear and cold. Stars feel very close."],
    ("autumn", "late_night"):
        ["Frost forms on the greenhouse glass. The garden is a study in silence.",
         "An owl calls from the oak tree. Once. Twice. Then nothing.",
         "The deepest autumn night. The garden draws inward."],

    # ---- winter ----
    ("winter", "dawn"):
        ["The garden wakes slowly under a white sky.",
         "Dawn is pale and reluctant. Bare branches etch the horizon.",
         "A thin layer of frost makes every surface precise and glittering."],
    ("winter", "morning"):
        ["The air is sharp enough to taste. Breath rises in small clouds.",
         "Pale winter sun touches the greenhouse roof but brings no warmth.",
         "The stream is edged with ice. The garden is spare and beautiful."],
    ("winter", "afternoon"):
        ["The light never quite reaches full strength. Shadows are blue.",
         "A quiet afternoon. The library fireplace crackles faintly.",
         "The garden rests. Everything is dormant, waiting."],
    ("winter", "evening"):
        ["The sky darkens early. Lamplight glows from the library windows.",
         "Cold settles in. The garden pulls its silence around itself like a blanket.",
         "Stars appear before dinner. The hilltop is wind-scoured and vast."],
    ("winter", "night"):
        ["Snow glows faintly under the moon. The world is muffled.",
         "The garden is a charcoal sketch — all lines and no color.",
         "Winter night. The silence has weight."],
    ("winter", "late_night"):
        ["The deepest cold. The garden endures.",
         "Nothing moves. Even the stream sounds slower.",
         "Somewhere under the frozen ground, roots are dreaming of spring."],
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class GardenState:
    """The shared world state — season, weather, time, and ambiance."""

    season: str         # "spring", "summer", "autumn", "winter"
    time_of_day: str    # "dawn", "morning", "afternoon", "evening", "night", "late_night"
    weather: str        # "clear", "cloudy", "rainy", "misty", "stormy", "snowy"
    ambiance: str       # generated description of what the garden feels like right now
    last_updated: str   # ISO 8601

    def to_dict(self) -> dict:
        return {
            "season": self.season,
            "time_of_day": self.time_of_day,
            "weather": self.weather,
            "ambiance": self.ambiance,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> GardenState:
        return cls(
            season=data["season"],
            time_of_day=data["time_of_day"],
            weather=data["weather"],
            ambiance=data.get("ambiance", ""),
            last_updated=data["last_updated"],
        )


@dataclass
class CharacterPresence:
    """Where each character is in the garden and what they are doing."""

    char_id: str
    location: str   # one of LOCATIONS
    activity: str   # freeform short description
    energy: float   # 0.0 to 1.0

    def to_dict(self) -> dict:
        return {
            "char_id": self.char_id,
            "location": self.location,
            "activity": self.activity,
            "energy": round(self.energy, 2),
        }

    @classmethod
    def from_dict(cls, data: dict) -> CharacterPresence:
        return cls(
            char_id=data["char_id"],
            location=data["location"],
            activity=data["activity"],
            energy=data.get("energy", 0.5),
        )


@dataclass
class Artifact:
    """Something a character has created — a poem, a letter, a sketch."""

    id: str
    creator_id: str
    artifact_type: str  # one of ARTIFACT_TYPES
    title: str
    content: str
    created_at: str     # ISO 8601

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "creator_id": self.creator_id,
            "artifact_type": self.artifact_type,
            "title": self.title,
            "content": self.content,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Artifact:
        return cls(
            id=data["id"],
            creator_id=data["creator_id"],
            artifact_type=data["artifact_type"],
            title=data["title"],
            content=data["content"],
            created_at=data["created_at"],
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _season_from_month(month: int) -> str:
    return _MONTH_TO_SEASON.get(month, "winter")


def _time_of_day_from_hour(hour: int) -> str:
    for start, end, label in _HOUR_BOUNDARIES:
        if start <= hour < end:
            return label
    return "late_night"


def _pick_weather(season: str) -> str:
    weights = _WEATHER_WEIGHTS.get(season, _WEATHER_WEIGHTS["winter"])
    options = list(weights.keys())
    probs = list(weights.values())
    return random.choices(options, weights=probs, k=1)[0]


def _pick_ambiance(season: str, time_of_day: str) -> str:
    templates = _AMBIANCE.get((season, time_of_day))
    if templates:
        return random.choice(templates)
    # Fallback — should never happen if the table is complete
    return f"The garden rests in {season} {time_of_day}."


def _location_label(location: str) -> str:
    """Turn a snake_case location into a readable phrase."""
    labels = {
        "rose_garden": "the rose garden",
        "oak_tree": "the old oak tree",
        "stream": "the stream",
        "greenhouse": "the greenhouse",
        "library": "the library",
        "hilltop": "the hilltop",
    }
    return labels.get(location, location.replace("_", " "))


# ---------------------------------------------------------------------------
# GardenWorld
# ---------------------------------------------------------------------------

class GardenWorld:
    """Manages the living state of the garden as a shared place.

    Owns the world state (season, weather, ambiance), character presence
    (location and activity), and artifacts (things characters create).
    """

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            data_dir = _DATA_DIR
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

        self._state: Optional[GardenState] = None
        self._presences: Dict[str, CharacterPresence] = {}
        self._artifacts: List[Artifact] = []

        # Load persisted state
        self._load_state()
        self._load_artifacts()

    # ------------------------------------------------------------------
    # World state
    # ------------------------------------------------------------------

    def update(self, now: Optional[datetime] = None) -> GardenState:
        """Recompute season, time of day, weather, and ambiance.

        Called during heartbeat ticks — not on every request.
        Weather changes here; season and time of day are always derived
        from the real clock.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        season = _season_from_month(now.month)
        time_of_day = _time_of_day_from_hour(now.hour)
        weather = _pick_weather(season)
        ambiance = _pick_ambiance(season, time_of_day)

        self._state = GardenState(
            season=season,
            time_of_day=time_of_day,
            weather=weather,
            ambiance=ambiance,
            last_updated=now.isoformat(),
        )

        # Possibly shuffle character positions
        self._drift_presences(time_of_day)

        self._save_state()
        logger.info(
            f"Garden updated: {season} {time_of_day}, {weather}. "
            f'"{ambiance[:60]}..."'
        )
        return self._state

    def get_state(self) -> GardenState:
        """Return the current garden state, creating a default if needed."""
        if self._state is None:
            self.update()
        return self._state

    # ------------------------------------------------------------------
    # Character presence
    # ------------------------------------------------------------------

    def get_presence(self, char_id: str) -> CharacterPresence:
        """Return where a character currently is in the garden.

        If no presence has been recorded yet, returns the character's
        default location and activity.
        """
        if char_id in self._presences:
            # Keep energy in sync with current time of day
            state = self.get_state()
            self._presences[char_id].energy = _ENERGY_BY_TIME.get(
                state.time_of_day, 0.5
            )
            return self._presences[char_id]

        # Build default presence
        defaults = _DEFAULT_PRESENCE.get(char_id, {
            "location": "oak_tree",
            "activity": "wandering",
        })
        state = self.get_state()
        energy = _ENERGY_BY_TIME.get(state.time_of_day, 0.5)

        presence = CharacterPresence(
            char_id=char_id,
            location=defaults["location"],
            activity=defaults["activity"],
            energy=energy,
        )
        self._presences[char_id] = presence
        return presence

    def get_all_presences(self) -> List[CharacterPresence]:
        """Return presence for every known character."""
        for char_id in _DEFAULT_PRESENCE:
            self.get_presence(char_id)  # ensure each is initialized
        return list(self._presences.values())

    def _drift_presences(self, time_of_day: str):
        """During a heartbeat tick, characters might wander.

        Each character has a small probability (~15%) of moving to a
        different location and picking up a new activity there.
        """
        drift_probability = 0.15

        for char_id in list(_DEFAULT_PRESENCE.keys()):
            presence = self.get_presence(char_id)

            if random.random() < drift_probability:
                # Pick a new location different from current
                other_locations = [
                    loc for loc in LOCATIONS if loc != presence.location
                ]
                new_location = random.choice(other_locations)
                new_activity = random.choice(
                    _WANDERING_ACTIVITIES.get(new_location, ["exploring"])
                )

                presence.location = new_location
                presence.activity = new_activity
                logger.debug(
                    f"[{char_id}] Wandered to {new_location}: {new_activity}"
                )

            # Update energy for new time of day
            presence.energy = _ENERGY_BY_TIME.get(time_of_day, 0.5)

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------

    def add_artifact(
        self,
        creator_id: str,
        artifact_type: str,
        title: str,
        content: str,
    ) -> Artifact:
        """Create and store a new artifact."""
        artifact = Artifact(
            id=f"art_{uuid.uuid4().hex[:12]}",
            creator_id=creator_id,
            artifact_type=artifact_type,
            title=title,
            content=content,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._artifacts.append(artifact)
        self._save_artifacts()
        logger.info(
            f"[{creator_id}] Created {artifact_type}: \"{title}\""
        )
        return artifact

    def get_artifacts(
        self,
        creator_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Artifact]:
        """Return recent artifacts, optionally filtered by creator.

        Newest first.
        """
        source = self._artifacts
        if creator_id is not None:
            source = [a for a in source if a.creator_id == creator_id]
        # Return newest first
        return list(reversed(source))[:limit]

    # ------------------------------------------------------------------
    # Prompt helpers
    # ------------------------------------------------------------------

    def world_context(self) -> str:
        """Return a prompt segment describing the current garden state.

        Suitable for injection into any character's system prompt to
        ground them in the shared place.
        """
        state = self.get_state()

        # Weather description
        weather_desc = {
            "clear": "The sky is clear.",
            "cloudy": "Clouds drift overhead.",
            "rainy": "Rain falls softly.",
            "misty": "A thin mist hangs in the air.",
            "stormy": "A storm rolls through. Thunder murmurs in the distance.",
            "snowy": "Snow is falling gently.",
        }

        lines = ["THE GARDEN RIGHT NOW:"]
        lines.append(
            f"It is a {state.weather} {state.season} {state.time_of_day}. "
            f"{weather_desc.get(state.weather, '')}"
        )
        lines.append(state.ambiance)

        # Other characters' presences
        presences = self.get_all_presences()
        others = []
        for p in presences:
            others.append(
                f"{p.char_id.capitalize()} is at {_location_label(p.location)}, "
                f"{p.activity}."
            )
        if others:
            lines.append("")
            lines.extend(others)

        return "\n".join(lines)

    def character_context(self, char_id: str) -> str:
        """Return a character-specific context segment.

        Tells the character where they are, what they're doing, and how
        they're feeling in terms of energy.
        """
        state = self.get_state()
        presence = self.get_presence(char_id)

        # Energy description
        if presence.energy >= 0.7:
            energy_desc = "You feel alert and energetic."
        elif presence.energy >= 0.4:
            energy_desc = "Your energy is moderate."
        else:
            energy_desc = "You feel quiet and low on energy."

        # Time-of-day color
        time_color = {
            "dawn": "The first light is soft and uncertain.",
            "morning": "The morning light is bright and inviting.",
            "afternoon": "The afternoon light falls warm and steady.",
            "evening": "The evening light is warm and fading.",
            "night": "The night is deep around you.",
            "late_night": "The hour is very late. The world is asleep.",
        }

        lines = [
            f"You are at {_location_label(presence.location)}, {presence.activity}.",
            time_color.get(state.time_of_day, ""),
            energy_desc,
        ]

        # Mention nearby characters
        all_presences = self.get_all_presences()
        nearby = [
            p for p in all_presences
            if p.char_id != char_id and p.location == presence.location
        ]
        if nearby:
            names = [p.char_id.capitalize() for p in nearby]
            if len(names) == 1:
                lines.append(f"{names[0]} is here with you.")
            else:
                lines.append(f"{', '.join(names[:-1])} and {names[-1]} are here with you.")

        return "\n".join(line for line in lines if line)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _state_path(self) -> str:
        return os.path.join(self.data_dir, "garden_world.json")

    def _artifacts_path(self) -> str:
        return os.path.join(self.data_dir, "garden_artifacts.json")

    def _save_state(self) -> None:
        if self._state is None:
            return
        payload = {
            "state": self._state.to_dict(),
            "presences": {
                cid: p.to_dict() for cid, p in self._presences.items()
            },
        }
        try:
            with open(self._state_path(), "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            logger.debug("Garden world state saved")
        except Exception as e:
            logger.error(f"Failed to save garden world state: {e}")

    def _load_state(self) -> None:
        path = self._state_path()
        if not os.path.exists(path):
            logger.info("No garden world state found — will create on first update")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self._state = GardenState.from_dict(payload["state"])
            for cid, pdata in payload.get("presences", {}).items():
                self._presences[cid] = CharacterPresence.from_dict(pdata)
            logger.info(
                f"Garden world loaded: {self._state.season} "
                f"{self._state.time_of_day}, {self._state.weather}"
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to load garden world state: {e}")
            self._state = None

    def _save_artifacts(self) -> None:
        try:
            data = [a.to_dict() for a in self._artifacts]
            with open(self._artifacts_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved {len(data)} artifacts")
        except Exception as e:
            logger.error(f"Failed to save artifacts: {e}")

    def _load_artifacts(self) -> None:
        path = self._artifacts_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._artifacts = [Artifact.from_dict(a) for a in data]
            logger.info(f"Loaded {len(self._artifacts)} artifacts")
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to load artifacts: {e}")
            self._artifacts = []
