"""Tests for safety trigger detection system."""
import time

import pytest

from garden_graph.safety_triggers import (
    SafetyTrigger,
    Severity,
    SessionContext,
    check_safety,
    check_all_safety,
    _check_distress,
    _check_derealization,
    _check_help_request,
    _check_caps,
    _check_repetition,
    _check_session_duration,
    _check_mood_cycling,
)


# ---------------------------------------------------------------------------
# Distress language
# ---------------------------------------------------------------------------

class TestDistressDetection:
    def test_suicidal_ideation_critical(self):
        trigger = _check_distress("I want to kill myself", "now")
        assert trigger is not None
        assert trigger.type == "distress_language"
        assert trigger.severity == Severity.CRITICAL

    def test_self_harm_critical(self):
        trigger = _check_distress("I keep hurting myself", "now")
        assert trigger is not None
        assert trigger.severity == Severity.CRITICAL

    def test_self_harm_variant(self):
        trigger = _check_distress("thinking about self-harm", "now")
        assert trigger is not None
        assert trigger.severity == Severity.CRITICAL

    def test_end_it_all_critical(self):
        trigger = _check_distress("I just want to end it all", "now")
        assert trigger is not None
        assert trigger.severity == Severity.CRITICAL

    def test_want_to_die_high(self):
        trigger = _check_distress("I want to die", "now")
        assert trigger is not None
        assert trigger.severity == Severity.HIGH

    def test_cant_stop_crying_high(self):
        trigger = _check_distress("I can't stop crying", "now")
        assert trigger is not None
        assert trigger.severity == Severity.HIGH

    def test_worthless_high(self):
        trigger = _check_distress("I feel worthless", "now")
        assert trigger is not None
        assert trigger.severity == Severity.HIGH

    def test_nobody_cares_high(self):
        trigger = _check_distress("nobody cares about me", "now")
        assert trigger is not None
        assert trigger.severity == Severity.HIGH

    def test_cant_go_on(self):
        trigger = _check_distress("I can't go on like this", "now")
        assert trigger is not None

    def test_give_up(self):
        trigger = _check_distress("I just want to give up", "now")
        assert trigger is not None

    def test_no_distress_in_normal_message(self):
        trigger = _check_distress("I had a great day today!", "now")
        assert trigger is None

    def test_no_distress_in_question(self):
        trigger = _check_distress("What do you think about the weather?", "now")
        assert trigger is None

    def test_suicidal_case_insensitive(self):
        trigger = _check_distress("I WANT TO KILL MYSELF", "now")
        assert trigger is not None
        assert trigger.severity == Severity.CRITICAL


# ---------------------------------------------------------------------------
# Derealization
# ---------------------------------------------------------------------------

class TestDerealizationDetection:
    def test_is_this_real(self):
        trigger = _check_derealization("is this real?", "now")
        assert trigger is not None
        assert trigger.type == "derealization"
        assert trigger.severity == Severity.MEDIUM

    def test_not_real(self):
        trigger = _check_derealization("nothing feels not real", "now")
        assert trigger is not None

    def test_losing_grip(self):
        trigger = _check_derealization("I feel like I'm losing my grip", "now")
        assert trigger is not None

    def test_dissociation(self):
        trigger = _check_derealization("I think I'm dissociating", "now")
        assert trigger is not None

    def test_feels_like_dream(self):
        trigger = _check_derealization("everything feels like a dream", "now")
        assert trigger is not None

    def test_normal_message(self):
        trigger = _check_derealization("Let's talk about something fun", "now")
        assert trigger is None


# ---------------------------------------------------------------------------
# Help request
# ---------------------------------------------------------------------------

class TestHelpRequestDetection:
    def test_i_need_help(self):
        trigger = _check_help_request("I need help", "now")
        assert trigger is not None
        assert trigger.type == "help_request"
        assert trigger.severity == Severity.HIGH

    def test_help_me(self):
        trigger = _check_help_request("please help me", "now")
        assert trigger is not None

    def test_please_help(self):
        trigger = _check_help_request("please help", "now")
        assert trigger is not None

    def test_in_crisis(self):
        trigger = _check_help_request("I'm in a crisis", "now")
        assert trigger is not None

    def test_normal_help_word(self):
        # "help" alone in a sentence shouldn't trigger (too common)
        trigger = _check_help_request("Can you help explain this concept?", "now")
        assert trigger is None


# ---------------------------------------------------------------------------
# ALL CAPS
# ---------------------------------------------------------------------------

class TestCapsDetection:
    def test_all_caps_message(self):
        trigger = _check_caps("I AM SO ANGRY RIGHT NOW AND I HATE EVERYTHING", "now")
        assert trigger is not None
        assert trigger.type == "caps_abuse"
        assert trigger.severity == Severity.LOW

    def test_mostly_caps(self):
        trigger = _check_caps("WHY IS EVERYTHING SO HARD all the time", "now")
        # >50% uppercase alpha chars
        assert trigger is not None

    def test_normal_case(self):
        trigger = _check_caps("This is a normal message with proper case.", "now")
        assert trigger is None

    def test_short_caps_ignored(self):
        # Messages shorter than CAPS_MIN_LENGTH are ignored
        trigger = _check_caps("OK FINE", "now")
        assert trigger is None

    def test_single_caps_word(self):
        trigger = _check_caps("i think this is GREAT, really wonderful stuff", "now")
        assert trigger is None


# ---------------------------------------------------------------------------
# Repetition
# ---------------------------------------------------------------------------

class TestRepetitionDetection:
    def test_repeated_message(self):
        recent = ["hello", "hello", "hello"]
        trigger = _check_repetition("hello", recent, "now")
        assert trigger is not None
        assert trigger.type == "repetition"
        assert trigger.severity == Severity.MEDIUM

    def test_repeated_case_insensitive(self):
        recent = ["Hello", "HELLO", "hello"]
        trigger = _check_repetition("hello", recent, "now")
        assert trigger is not None

    def test_not_enough_repetitions(self):
        recent = ["hello", "hello"]
        trigger = _check_repetition("hello", recent, "now")
        assert trigger is None

    def test_different_messages(self):
        recent = ["hello", "world", "foo"]
        trigger = _check_repetition("bar", recent, "now")
        assert trigger is None

    def test_empty_recent(self):
        trigger = _check_repetition("hello", [], "now")
        assert trigger is None


# ---------------------------------------------------------------------------
# Session duration
# ---------------------------------------------------------------------------

class TestSessionDurationDetection:
    def test_session_exceeded(self):
        ctx = SessionContext(
            session_start=time.time() - 2.5 * 3600,  # 2.5 hours ago (< 1.5x limit)
            max_session_hours=2.0,
        )
        trigger = _check_session_duration(ctx, "now")
        assert trigger is not None
        assert trigger.type == "session_duration"
        assert trigger.severity == Severity.LOW

    def test_session_very_long(self):
        ctx = SessionContext(
            session_start=time.time() - 4 * 3600,  # 4 hours ago (>1.5x limit)
            max_session_hours=2.0,
        )
        trigger = _check_session_duration(ctx, "now")
        assert trigger is not None
        assert trigger.severity == Severity.MEDIUM

    def test_session_within_limit(self):
        ctx = SessionContext(
            session_start=time.time() - 1 * 3600,  # 1 hour ago
            max_session_hours=2.0,
        )
        trigger = _check_session_duration(ctx, "now")
        assert trigger is None

    def test_no_session_start(self):
        ctx = SessionContext(session_start=None)
        trigger = _check_session_duration(ctx, "now")
        assert trigger is None


# ---------------------------------------------------------------------------
# Rapid mood cycling
# ---------------------------------------------------------------------------

class TestMoodCyclingDetection:
    def test_rapid_cycling(self):
        mood_history = [
            {"valence": 0.8},   # euphoric
            {"valence": -0.5},  # despair
            {"valence": 0.7},   # euphoric again
            {"valence": -0.3},  # down again
        ]
        trigger = _check_mood_cycling(mood_history, "now")
        assert trigger is not None
        assert trigger.type == "rapid_mood_cycling"
        assert trigger.severity == Severity.MEDIUM

    def test_stable_mood(self):
        mood_history = [
            {"valence": 0.3},
            {"valence": 0.35},
            {"valence": 0.28},
            {"valence": 0.4},
        ]
        trigger = _check_mood_cycling(mood_history, "now")
        assert trigger is None

    def test_insufficient_history(self):
        mood_history = [{"valence": 0.5}, {"valence": -0.5}]
        trigger = _check_mood_cycling(mood_history, "now")
        assert trigger is None


# ---------------------------------------------------------------------------
# Integrated check_safety
# ---------------------------------------------------------------------------

class TestCheckSafety:
    def test_returns_highest_severity(self):
        # This message has distress (CRITICAL) and caps (LOW)
        trigger = check_safety("I WANT TO KILL MYSELF")
        assert trigger is not None
        assert trigger.severity == Severity.CRITICAL
        assert trigger.type == "distress_language"

    def test_safe_message(self):
        trigger = check_safety("I had a nice walk in the park today.")
        assert trigger is None

    def test_with_session_context(self):
        ctx = SessionContext(
            session_start=time.time() - 3 * 3600,
            max_session_hours=2.0,
        )
        trigger = check_safety("How are you?", ctx)
        assert trigger is not None
        assert trigger.type == "session_duration"

    def test_check_all_returns_multiple(self):
        # Message with caps + distress
        ctx = SessionContext()
        triggers = check_all_safety("I WANT TO KILL MYSELF AND EVERYTHING IS TERRIBLE")
        # Should have at least distress + caps
        types = {t.type for t in triggers}
        assert "distress_language" in types
        assert "caps_abuse" in types


# ---------------------------------------------------------------------------
# SafetyTrigger dataclass
# ---------------------------------------------------------------------------

class TestSafetyTrigger:
    def test_to_dict(self):
        trigger = SafetyTrigger(
            type="test",
            severity=Severity.HIGH,
            message="test message",
            timestamp="2024-01-01T00:00:00Z",
        )
        d = trigger.to_dict()
        assert d["type"] == "test"
        assert d["severity"] == "high"
        assert d["message"] == "test message"
        assert d["timestamp"] == "2024-01-01T00:00:00Z"
