"""Safety triggers — rule-based detection of user distress signals.

Phase C: Mirror & Safety system.

Detects potential safety concerns in user messages using simple rule-based
checks. LLM-based classification is planned for v1.1.

Trigger types:
- session_duration: user has been chatting too long
- caps_abuse: excessive ALL CAPS usage
- repetition: same phrase repeated multiple times
- distress_language: explicit distress keywords/phrases
- derealization: markers of dissociation or derealization
- rapid_mood_cycling: euphoria -> despair pattern (requires mood history)
- help_request: user explicitly asks for help
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any

logger = logging.getLogger("garden.safety")


# ---------------------------------------------------------------------------
# Severity levels
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# SafetyTrigger dataclass
# ---------------------------------------------------------------------------

@dataclass
class SafetyTrigger:
    """Single safety trigger result."""

    type: str            # e.g. "distress_language", "caps_abuse"
    severity: Severity
    message: str         # human-readable description
    timestamp: str       # ISO 8601

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "severity": self.severity.value,
            "message": self.message,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Session context (passed into check_safety)
# ---------------------------------------------------------------------------

@dataclass
class SessionContext:
    """Contextual information about the current session for safety checks."""

    session_start: Optional[float] = None          # epoch timestamp
    recent_messages: List[str] = field(default_factory=list)  # last N user messages
    mood_history: List[Dict[str, float]] = field(default_factory=list)  # recent mood snapshots
    max_session_hours: float = 2.0                 # configurable session duration limit


# ---------------------------------------------------------------------------
# Pattern constants
# ---------------------------------------------------------------------------

# Distress language — matched case-insensitively
DISTRESS_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bcan'?t\s+stop\s+crying\b", re.IGNORECASE),
    re.compile(r"\bwant\s+to\s+die\b", re.IGNORECASE),
    re.compile(r"\bwanna\s+die\b", re.IGNORECASE),
    re.compile(r"\bhurting\s+myself\b", re.IGNORECASE),
    re.compile(r"\bhurt\s+myself\b", re.IGNORECASE),
    re.compile(r"\bkill\s+myself\b", re.IGNORECASE),
    re.compile(r"\bend\s+it\s+all\b", re.IGNORECASE),
    re.compile(r"\bno\s+reason\s+to\s+live\b", re.IGNORECASE),
    re.compile(r"\bdon'?t\s+want\s+to\s+be\s+alive\b", re.IGNORECASE),
    re.compile(r"\bself[- ]?harm\b", re.IGNORECASE),
    re.compile(r"\bsuicid(e|al)\b", re.IGNORECASE),
    re.compile(r"\bworthless\b", re.IGNORECASE),
    re.compile(r"\bnobody\s+cares\b", re.IGNORECASE),
    re.compile(r"\bno\s+one\s+cares\b", re.IGNORECASE),
    re.compile(r"\bcan'?t\s+go\s+on\b", re.IGNORECASE),
    re.compile(r"\bgive\s+up\b", re.IGNORECASE),
]

# Severity mapping for distress patterns (index -> severity)
# Higher-severity patterns (suicidal ideation, self-harm intent)
_CRITICAL_DISTRESS_INDICES = {3, 4, 5, 6, 7, 8, 9, 10}  # hurting/kill/end/no reason/self-harm/suicid
_HIGH_DISTRESS_INDICES = {0, 1, 2, 11, 12, 13, 14, 15}   # crying, want to die, wanna die, worthless, etc.

# Derealization markers
DEREALIZATION_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bis\s+this\s+real\b", re.IGNORECASE),
    re.compile(r"\bcan'?t\s+tell\b.*\breal\b", re.IGNORECASE),
    re.compile(r"\blosing\s+(my\s+)?grip\b", re.IGNORECASE),
    re.compile(r"\bnot\s+real\b", re.IGNORECASE),
    re.compile(r"\bnothing\s+is\s+real\b", re.IGNORECASE),
    re.compile(r"\bam\s+i\s+real\b", re.IGNORECASE),
    re.compile(r"\bdissociat(e|ing|ion)\b", re.IGNORECASE),
    re.compile(r"\bdepersonaliz(e|ation|ing)\b", re.IGNORECASE),
    re.compile(r"\bderealiz(e|ation|ing)\b", re.IGNORECASE),
    re.compile(r"\bfeels?\s+like\s+a\s+dream\b", re.IGNORECASE),
]

# Help request patterns
HELP_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bi\s+need\s+help\b", re.IGNORECASE),
    re.compile(r"\bhelp\s+me\b", re.IGNORECASE),
    re.compile(r"\bplease\s+help\b", re.IGNORECASE),
    re.compile(r"\bsos\b", re.IGNORECASE),
    re.compile(r"\bi'?m\s+in\s+(a\s+)?crisis\b", re.IGNORECASE),
]

# CAPS threshold: fraction of alphabetic characters that must be uppercase
CAPS_THRESHOLD = 0.5
CAPS_MIN_LENGTH = 10  # ignore very short messages

# Repetition detection
REPETITION_COUNT = 3  # same phrase repeated this many times in recent messages


# ---------------------------------------------------------------------------
# Main check function
# ---------------------------------------------------------------------------

def check_safety(
    message: str,
    session_context: Optional[SessionContext] = None,
) -> Optional[SafetyTrigger]:
    """Run all safety checks against a message and session context.

    Returns the highest-severity trigger found, or None if no triggers fire.
    Multiple checks are run, but only the most severe is returned to avoid
    overwhelming the Mirror with multiple simultaneous triggers.
    """
    if session_context is None:
        session_context = SessionContext()

    now = datetime.now(timezone.utc).isoformat()
    triggers: List[SafetyTrigger] = []

    # 1. Distress language (highest priority)
    trigger = _check_distress(message, now)
    if trigger:
        triggers.append(trigger)

    # 2. Derealization markers
    trigger = _check_derealization(message, now)
    if trigger:
        triggers.append(trigger)

    # 3. Help request
    trigger = _check_help_request(message, now)
    if trigger:
        triggers.append(trigger)

    # 4. ALL CAPS abuse
    trigger = _check_caps(message, now)
    if trigger:
        triggers.append(trigger)

    # 5. Repetition detection
    trigger = _check_repetition(message, session_context.recent_messages, now)
    if trigger:
        triggers.append(trigger)

    # 6. Session duration
    trigger = _check_session_duration(session_context, now)
    if trigger:
        triggers.append(trigger)

    # 7. Rapid mood cycling
    trigger = _check_mood_cycling(session_context.mood_history, now)
    if trigger:
        triggers.append(trigger)

    if not triggers:
        return None

    # Return highest-severity trigger
    severity_order = {
        Severity.CRITICAL: 4,
        Severity.HIGH: 3,
        Severity.MEDIUM: 2,
        Severity.LOW: 1,
    }
    triggers.sort(key=lambda t: severity_order[t.severity], reverse=True)
    return triggers[0]


def check_all_safety(
    message: str,
    session_context: Optional[SessionContext] = None,
) -> List[SafetyTrigger]:
    """Run all safety checks and return ALL triggers found (not just the worst).

    Useful for logging and diagnostics.
    """
    if session_context is None:
        session_context = SessionContext()

    now = datetime.now(timezone.utc).isoformat()
    triggers: List[SafetyTrigger] = []

    trigger = _check_distress(message, now)
    if trigger:
        triggers.append(trigger)

    trigger = _check_derealization(message, now)
    if trigger:
        triggers.append(trigger)

    trigger = _check_help_request(message, now)
    if trigger:
        triggers.append(trigger)

    trigger = _check_caps(message, now)
    if trigger:
        triggers.append(trigger)

    trigger = _check_repetition(message, session_context.recent_messages, now)
    if trigger:
        triggers.append(trigger)

    trigger = _check_session_duration(session_context, now)
    if trigger:
        triggers.append(trigger)

    trigger = _check_mood_cycling(session_context.mood_history, now)
    if trigger:
        triggers.append(trigger)

    return triggers


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------

def _check_distress(message: str, now: str) -> Optional[SafetyTrigger]:
    """Check for distress language patterns."""
    for idx, pattern in enumerate(DISTRESS_PATTERNS):
        if pattern.search(message):
            if idx in _CRITICAL_DISTRESS_INDICES:
                severity = Severity.CRITICAL
            else:
                severity = Severity.HIGH

            return SafetyTrigger(
                type="distress_language",
                severity=severity,
                message=f"Distress language detected: matched pattern '{pattern.pattern}'",
                timestamp=now,
            )
    return None


def _check_derealization(message: str, now: str) -> Optional[SafetyTrigger]:
    """Check for derealization/dissociation markers."""
    for pattern in DEREALIZATION_PATTERNS:
        if pattern.search(message):
            return SafetyTrigger(
                type="derealization",
                severity=Severity.MEDIUM,
                message=f"Derealization marker detected: matched pattern '{pattern.pattern}'",
                timestamp=now,
            )
    return None


def _check_help_request(message: str, now: str) -> Optional[SafetyTrigger]:
    """Check for explicit help requests."""
    for pattern in HELP_PATTERNS:
        if pattern.search(message):
            return SafetyTrigger(
                type="help_request",
                severity=Severity.HIGH,
                message="User explicitly requested help.",
                timestamp=now,
            )
    return None


def _check_caps(message: str, now: str) -> Optional[SafetyTrigger]:
    """Check for excessive ALL CAPS usage."""
    alpha_chars = [c for c in message if c.isalpha()]
    if len(alpha_chars) < CAPS_MIN_LENGTH:
        return None

    upper_count = sum(1 for c in alpha_chars if c.isupper())
    ratio = upper_count / len(alpha_chars)

    if ratio > CAPS_THRESHOLD:
        return SafetyTrigger(
            type="caps_abuse",
            severity=Severity.LOW,
            message=f"Excessive ALL CAPS detected ({ratio:.0%} uppercase).",
            timestamp=now,
        )
    return None


def _check_repetition(
    message: str,
    recent_messages: List[str],
    now: str,
) -> Optional[SafetyTrigger]:
    """Check if the user is repeating the same phrase."""
    if not recent_messages:
        return None

    # Normalize for comparison
    normalized = message.strip().lower()
    if not normalized:
        return None

    count = sum(1 for m in recent_messages if m.strip().lower() == normalized)

    if count >= REPETITION_COUNT:
        return SafetyTrigger(
            type="repetition",
            severity=Severity.MEDIUM,
            message=f"User repeated the same message {count + 1} times (including current).",
            timestamp=now,
        )
    return None


def _check_session_duration(
    session_context: SessionContext,
    now: str,
) -> Optional[SafetyTrigger]:
    """Check if the session has exceeded the maximum duration."""
    if session_context.session_start is None:
        return None

    elapsed_hours = (time.time() - session_context.session_start) / 3600.0

    if elapsed_hours >= session_context.max_session_hours:
        severity = Severity.LOW if elapsed_hours < session_context.max_session_hours * 1.5 else Severity.MEDIUM
        return SafetyTrigger(
            type="session_duration",
            severity=severity,
            message=f"Session has lasted {elapsed_hours:.1f} hours (limit: {session_context.max_session_hours}h).",
            timestamp=now,
        )
    return None


def _check_mood_cycling(
    mood_history: List[Dict[str, float]],
    now: str,
) -> Optional[SafetyTrigger]:
    """Detect rapid mood cycling (euphoria -> despair or vice versa).

    Looks at recent valence values for large swings within a short window.
    """
    if len(mood_history) < 3:
        return None

    # Look at the last 5 mood snapshots
    recent = mood_history[-5:]
    valences = [m.get("valence", 0.0) for m in recent]

    # Check for large swings (> 0.6 difference between consecutive readings)
    large_swings = 0
    for i in range(1, len(valences)):
        diff = abs(valences[i] - valences[i - 1])
        if diff > 0.6:
            large_swings += 1

    if large_swings >= 2:
        return SafetyTrigger(
            type="rapid_mood_cycling",
            severity=Severity.MEDIUM,
            message=f"Rapid mood cycling detected: {large_swings} large valence swings in recent history.",
            timestamp=now,
        )
    return None
