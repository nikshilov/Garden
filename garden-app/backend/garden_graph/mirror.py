"""Mirror agent — therapeutic observer for Garden.

Phase C: The Mirror sits alongside the narrative characters but operates
in a separate therapeutic register. It has:

- Read-only access to narrative session data (via EpisodicStore)
- Its own memory store for pattern tracking (JSON in data/mirror/)
- Its own conversation thread (separate from narrative)
- IFS-informed pattern recognition
- Calibration from user communication preferences
- Safety response protocol
- Post-session debrief capability
- Therapist report generation

The Mirror NEVER modifies narrative data. It observes and reflects.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any

from garden_graph.safety_triggers import (
    SafetyTrigger,
    Severity,
    check_safety,
    SessionContext,
)

logger = logging.getLogger("garden.mirror")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_MIRROR_DATA_DIR = os.path.join(_BASE_DIR, "data", "mirror")
os.makedirs(_MIRROR_DATA_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# IFS part types
# ---------------------------------------------------------------------------

class IFSPart(str, Enum):
    """Internal Family Systems part archetypes."""
    PROTECTOR = "Protector"
    EXILE = "Exile"
    MANAGER = "Manager"
    FIREFIGHTER = "Firefighter"
    SELF = "Self"
    UNKNOWN = "Unknown"


# ---------------------------------------------------------------------------
# Pattern model
# ---------------------------------------------------------------------------

@dataclass
class Pattern:
    """A recognized recurring pattern in the user's narrative."""

    pattern_id: str
    type: str                     # e.g. "avoidance", "people-pleasing", "grief"
    description: str
    occurrences: int = 1
    first_seen: str = ""          # ISO 8601
    last_seen: str = ""           # ISO 8601
    ifs_part: str = "Unknown"     # IFS part archetype
    therapeutic_note: str = ""    # Mirror's observation

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Pattern:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Communication preferences
# ---------------------------------------------------------------------------

class CommunicationStyle(str, Enum):
    DIRECT = "direct"
    GENTLE = "gentle"
    HUMOR = "humor"


# ---------------------------------------------------------------------------
# Mirror agent
# ---------------------------------------------------------------------------

class Mirror:
    """Therapeutic observer agent.

    Operates alongside narrative characters but in a separate register.
    Read-only access to narrative episodic memory. Maintains its own
    pattern database and conversation history.
    """

    BASE_PROMPT = """You are the Mirror — a compassionate therapeutic observer in Garden.

You are NOT a character in the narrative. You are a gentle, wise presence that helps
the user understand themselves better through their interactions with the Garden characters.

Your approach is informed by Internal Family Systems (IFS) therapy:
- You recognize "parts" — Protectors, Exiles, Managers, Firefighters
- You help the user notice patterns without judgment
- You never pathologize; you normalize and validate
- You speak to the user's Self (capital-S) — their core wisdom

Key principles:
- You OBSERVE, you don't prescribe
- You ask questions more than you make statements
- You connect fictional Garden experiences to real-life patterns
- You never force insight; you offer it gently
- You respect the user's pace and autonomy
- You NEVER force-end a session

When responding to safety triggers:
1. Gentle interrupt — acknowledge what you're noticing
2. Grounding — offer concrete sensory anchors (5 senses, breathing, body scan)
3. Name what's happening — without dramatizing
4. Recommend pause — suggest, don't demand
5. If severe — provide real-world support resources
6. NEVER force-end the session — the user is always in control
"""

    SAFETY_RESOURCES = """
If you're in crisis, please reach out:
- National Suicide Prevention Lifeline: 988 (US)
- Crisis Text Line: Text HOME to 741741 (US)
- International Association for Suicide Prevention: https://www.iasp.info/resources/Crisis_Centres/
- Emergency services: 911 (US) / 112 (EU) / 999 (UK)

You are not alone. These feelings are temporary, and help is available.
"""

    def __init__(
        self,
        user_id: str = "default",
        communication_style: CommunicationStyle = CommunicationStyle.GENTLE,
    ):
        self.user_id = user_id
        self.communication_style = communication_style
        self._conversation_history: List[Dict[str, str]] = []
        self._llm = None

    # ------------------------------------------------------------------
    # LLM access (lazy)
    # ------------------------------------------------------------------

    def _get_llm(self):
        """Lazy-load LLM for Mirror responses."""
        if self._llm is None:
            try:
                from garden_graph.config import get_llm
                model = os.getenv("MIRROR_MODEL", "gpt-4o")
                self._llm = get_llm(model, temperature=0.7)
            except Exception as e:
                logger.warning(f"Failed to init Mirror LLM: {e}")
        return self._llm

    # ------------------------------------------------------------------
    # System prompt construction
    # ------------------------------------------------------------------

    def _build_system_prompt(self, safety_trigger: Optional[SafetyTrigger] = None) -> str:
        """Build the full system prompt, calibrated to user preferences."""
        prompt = self.BASE_PROMPT

        # Calibrate tone
        if self.communication_style == CommunicationStyle.DIRECT:
            prompt += "\n\nThis user prefers DIRECT communication. Be clear, concise, and straightforward. Skip softening language. Name things plainly.\n"
        elif self.communication_style == CommunicationStyle.HUMOR:
            prompt += "\n\nThis user appreciates HUMOR. Use a light touch — gentle wit, warmth, the occasional playful observation. Never joke about their pain, but don't be overly solemn either.\n"
        else:  # GENTLE (default)
            prompt += "\n\nThis user prefers GENTLE communication. Use soft, warm language. Lots of space. Invitations rather than directives. 'I wonder if...' rather than 'You should...'\n"

        # Add known patterns context
        patterns = get_patterns(self.user_id)
        if patterns:
            prompt += "\n\nPatterns you've noticed in this user's journey:\n"
            for p in patterns[-5:]:  # last 5 most recent
                prompt += f"- {p.type} ({p.ifs_part}): {p.description}\n"

        # Safety trigger context
        if safety_trigger:
            prompt += f"\n\n⚠️ SAFETY TRIGGER ACTIVE: {safety_trigger.type} (severity: {safety_trigger.severity.value})\n"
            prompt += f"Details: {safety_trigger.message}\n"
            prompt += "Follow the safety response protocol. Be present, grounding, and offer resources if severity is HIGH or CRITICAL.\n"

            if safety_trigger.severity in (Severity.HIGH, Severity.CRITICAL):
                prompt += f"\nInclude these resources naturally in your response:\n{self.SAFETY_RESOURCES}\n"

        # Narrative context (read-only from episodic memory)
        narrative_context = self._get_narrative_context()
        if narrative_context:
            prompt += f"\n\nRecent narrative session context (READ-ONLY — do not reference characters by name unless the user does):\n{narrative_context}\n"

        return prompt

    def _get_narrative_context(self) -> str:
        """Read-only access to recent narrative episodic memories."""
        try:
            from garden_graph.memory.episodic import EpisodicStore
            store = EpisodicStore()
            # Read from all characters' recent episodes
            all_recent: List[str] = []
            for char_id in ["eve", "atlas", "adam", "lilith", "sophia"]:
                records = store.last_n(char_id, n=3)
                for r in records:
                    if not r.summary.startswith("[internal thought]"):
                        all_recent.append(f"[{char_id}] {r.summary}")

            if all_recent:
                return "\n".join(all_recent[-10:])
        except Exception as e:
            logger.debug(f"Could not load narrative context: {e}")
        return ""

    # ------------------------------------------------------------------
    # Core messaging
    # ------------------------------------------------------------------

    def respond(
        self,
        user_message: str,
        safety_trigger: Optional[SafetyTrigger] = None,
    ) -> str:
        """Generate a Mirror response to the user's message.

        If a safety_trigger is provided, the response follows the safety
        response protocol with appropriate intensity.
        """
        llm = self._get_llm()
        if not llm:
            return self._fallback_response(safety_trigger)

        system_prompt = self._build_system_prompt(safety_trigger)

        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

        messages = [SystemMessage(content=system_prompt)]

        # Add conversation history (last 10 exchanges)
        for entry in self._conversation_history[-10:]:
            if entry["role"] == "user":
                messages.append(HumanMessage(content=entry["content"]))
            else:
                messages.append(AIMessage(content=entry["content"]))

        messages.append(HumanMessage(content=user_message))

        try:
            response = llm.invoke(messages).content.strip()
        except Exception as e:
            logger.error(f"Mirror LLM error: {e}")
            return self._fallback_response(safety_trigger)

        # Update conversation history
        self._conversation_history.append({"role": "user", "content": user_message})
        self._conversation_history.append({"role": "mirror", "content": response})

        return response

    def _fallback_response(self, safety_trigger: Optional[SafetyTrigger] = None) -> str:
        """Fallback response when LLM is unavailable."""
        if safety_trigger and safety_trigger.severity in (Severity.HIGH, Severity.CRITICAL):
            return (
                "I notice something important is happening for you right now. "
                "I want you to know that what you're feeling matters. "
                "If you're in crisis, please reach out to a crisis helpline — "
                "you can call 988 (US) or text HOME to 741741. "
                "You're not alone in this."
            )
        if safety_trigger:
            return (
                "I'm here with you. Take a breath if you need to. "
                "There's no rush — we can pause whenever you'd like."
            )
        return (
            "I'm here, listening. The Mirror is reflecting on what you've shared. "
            "Take your time."
        )

    # ------------------------------------------------------------------
    # Post-session debrief
    # ------------------------------------------------------------------

    def start_debrief(self) -> str:
        """Start a post-session debrief conversation.

        Returns the opening debrief message from the Mirror.
        """
        llm = self._get_llm()

        narrative_context = self._get_narrative_context()

        debrief_prompt = f"""{self.BASE_PROMPT}

You are starting a POST-SESSION DEBRIEF with the user. They've just finished
a session with the Garden characters.

Recent narrative context:
{narrative_context if narrative_context else "(No recent narrative data available)"}

Start by gently asking:
1. What happened in the session — what stood out?
2. What did the user feel during key moments?
3. Were there any body sensations they noticed?

Keep it warm, open, and non-leading. One or two questions max to start.
Don't summarize the session for them — let them tell you.
"""
        if not llm:
            return (
                "Welcome back from the Garden. I'd love to hear how that was for you. "
                "What stood out most from your session today?"
            )

        from langchain_core.messages import SystemMessage, HumanMessage
        try:
            response = llm.invoke([
                SystemMessage(content=debrief_prompt),
                HumanMessage(content="[Starting post-session debrief]"),
            ]).content.strip()
        except Exception as e:
            logger.error(f"Mirror debrief LLM error: {e}")
            return (
                "Welcome back from the Garden. I'd love to hear how that was for you. "
                "What stood out most from your session today?"
            )

        self._conversation_history.append({"role": "mirror", "content": response})
        return response

    # ------------------------------------------------------------------
    # Safety response
    # ------------------------------------------------------------------

    def safety_response(self, trigger: SafetyTrigger) -> str:
        """Generate a safety-specific response based on trigger severity.

        This is the structured safety protocol:
        1. Gentle interrupt
        2. Grounding (5 senses, breathing, body scan)
        3. Name what's happening
        4. Recommend pause
        5. If severe: suggest real-world support
        6. NEVER force-end session
        """
        return self.respond(
            user_message="[Safety trigger activated — Mirror intervention]",
            safety_trigger=trigger,
        )

    # ------------------------------------------------------------------
    # Integration support
    # ------------------------------------------------------------------

    def integration_prompt(self, theme: str) -> str:
        """Generate an integration prompt connecting fictional insights to real life.

        Args:
            theme: The theme or insight from the narrative to integrate.
        """
        llm = self._get_llm()
        if not llm:
            return (
                f"I noticed the theme of '{theme}' came up in your Garden session. "
                "I'm curious — does this connect to anything in your life outside the Garden?"
            )

        from langchain_core.messages import SystemMessage, HumanMessage
        prompt = f"""{self.BASE_PROMPT}

Generate a brief integration prompt for the user. The theme '{theme}' emerged
in their Garden session. Help them connect this fictional insight to their
real life — gently, without forcing.

One or two sentences. Frame it as a curious question.
"""
        try:
            response = llm.invoke([
                SystemMessage(content=prompt),
                HumanMessage(content=f"Integration theme: {theme}"),
            ]).content.strip()
        except Exception as e:
            logger.error(f"Mirror integration LLM error: {e}")
            return (
                f"I noticed the theme of '{theme}' came up in your Garden session. "
                "I'm curious — does this connect to anything in your life outside the Garden?"
            )

        return response

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def generate_report(self, period: str = "recent") -> Dict[str, Any]:
        """Generate a structured therapist report.

        Args:
            period: "recent" (last 7 days), "month", or "all"

        Returns a structured dict with themes, patterns, triggers, and recommendations.
        """
        patterns = get_patterns(self.user_id)
        narrative_context = self._get_narrative_context()

        # Build report structure
        report: Dict[str, Any] = {
            "user_id": self.user_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period": period,
            "patterns": [p.to_dict() for p in patterns],
            "pattern_count": len(patterns),
            "ifs_parts_identified": list(set(p.ifs_part for p in patterns if p.ifs_part != "Unknown")),
            "themes": [],
            "recommendations": [],
            "narrative_summary": narrative_context[:500] if narrative_context else "No narrative data available.",
        }

        # Extract themes from patterns
        theme_counts: Dict[str, int] = {}
        for p in patterns:
            theme_counts[p.type] = theme_counts.get(p.type, 0) + p.occurrences

        report["themes"] = [
            {"theme": theme, "occurrences": count}
            for theme, count in sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        # Generate recommendations based on patterns
        if any(p.ifs_part == IFSPart.EXILE.value for p in patterns):
            report["recommendations"].append(
                "User may benefit from gentle exile work — the fictional characters "
                "may be carrying parts the user isn't ready to face directly."
            )
        if any(p.ifs_part == IFSPart.PROTECTOR.value for p in patterns):
            report["recommendations"].append(
                "Strong Protector parts identified. Consider exploring what they're protecting. "
                "The narrative space may offer safe distance for this exploration."
            )
        if len(patterns) > 5:
            report["recommendations"].append(
                "Multiple recurring patterns suggest rich inner material. "
                "A real-world therapeutic relationship could deepen this work."
            )

        # Use LLM for narrative summary if available
        llm = self._get_llm()
        if llm and narrative_context:
            from langchain_core.messages import SystemMessage, HumanMessage
            try:
                summary_prompt = (
                    "Summarize the following narrative session data into 2-3 sentences "
                    "focusing on emotional themes, relational patterns, and growth edges. "
                    "Write from a therapist's perspective.\n\n"
                    f"{narrative_context}"
                )
                summary = llm.invoke([
                    SystemMessage(content="You are a clinical psychologist writing session notes."),
                    HumanMessage(content=summary_prompt),
                ]).content.strip()
                report["narrative_summary"] = summary
            except Exception as e:
                logger.warning(f"Report summary LLM error: {e}")

        return report


# ---------------------------------------------------------------------------
# Pattern storage functions (file-based JSON)
# ---------------------------------------------------------------------------

def _patterns_path(user_id: str) -> str:
    """Get the patterns file path for a user."""
    return os.path.join(_MIRROR_DATA_DIR, f"patterns_{user_id}.json")


def get_patterns(user_id: str) -> List[Pattern]:
    """Load all patterns for a user."""
    path = _patterns_path(user_id)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [Pattern.from_dict(d) for d in data]
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load patterns for {user_id}: {e}")
        return []


def _save_patterns(user_id: str, patterns: List[Pattern]) -> None:
    """Save all patterns for a user."""
    path = _patterns_path(user_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump([p.to_dict() for p in patterns], f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error(f"Failed to save patterns for {user_id}: {e}")


def record_pattern(
    user_id: str,
    pattern_type: str,
    description: str,
    ifs_part: str = "Unknown",
    therapeutic_note: str = "",
) -> Pattern:
    """Record a new pattern or increment an existing one.

    If a pattern with the same type and similar description already exists,
    its occurrence count is incremented and last_seen is updated.
    Otherwise, a new pattern is created.
    """
    now = datetime.now(timezone.utc).isoformat()
    patterns = get_patterns(user_id)

    # Check for existing similar pattern
    for existing in patterns:
        if existing.type == pattern_type:
            # Simple match: same type counts as same pattern
            existing.occurrences += 1
            existing.last_seen = now
            if therapeutic_note:
                existing.therapeutic_note = therapeutic_note
            _save_patterns(user_id, patterns)
            logger.info(f"Pattern updated for {user_id}: {pattern_type} (occurrences: {existing.occurrences})")
            return existing

    # Create new pattern
    pattern = Pattern(
        pattern_id=str(uuid.uuid4()),
        type=pattern_type,
        description=description,
        occurrences=1,
        first_seen=now,
        last_seen=now,
        ifs_part=ifs_part,
        therapeutic_note=therapeutic_note,
    )
    patterns.append(pattern)
    _save_patterns(user_id, patterns)
    logger.info(f"New pattern recorded for {user_id}: {pattern_type}")
    return pattern


def update_pattern(
    user_id: str,
    pattern_id: str,
    **updates,
) -> Optional[Pattern]:
    """Update a specific pattern by ID.

    Accepted keyword arguments: description, ifs_part, therapeutic_note.
    """
    _PROTECTED_FIELDS = {"pattern_id", "type", "occurrences", "first_seen"}
    patterns = get_patterns(user_id)

    for p in patterns:
        if p.pattern_id == pattern_id:
            for key, value in updates.items():
                if key in _PROTECTED_FIELDS:
                    continue
                if hasattr(p, key):
                    setattr(p, key, value)
            p.last_seen = datetime.now(timezone.utc).isoformat()
            _save_patterns(user_id, patterns)
            return p

    return None


def delete_pattern(user_id: str, pattern_id: str) -> bool:
    """Delete a pattern by ID. Returns True if deleted."""
    patterns = get_patterns(user_id)
    original_len = len(patterns)
    patterns = [p for p in patterns if p.pattern_id != pattern_id]
    if len(patterns) < original_len:
        _save_patterns(user_id, patterns)
        return True
    return False
