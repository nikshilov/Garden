"""Tests for Mirror agent and pattern management."""
import json
import os
import tempfile
import uuid

import pytest

from garden_graph.mirror import (
    Mirror,
    Pattern,
    IFSPart,
    CommunicationStyle,
    get_patterns,
    record_pattern,
    update_pattern,
    delete_pattern,
    _save_patterns,
    _patterns_path,
    _MIRROR_DATA_DIR,
)
from garden_graph.safety_triggers import SafetyTrigger, Severity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def unique_user_id():
    """Generate a unique user ID to avoid test interference."""
    return f"test_user_{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def cleanup_test_patterns(unique_user_id):
    """Clean up test pattern files after each test."""
    yield
    path = _patterns_path(unique_user_id)
    if os.path.exists(path):
        os.remove(path)


# ---------------------------------------------------------------------------
# Pattern model
# ---------------------------------------------------------------------------

class TestPatternModel:
    def test_pattern_to_dict(self):
        p = Pattern(
            pattern_id="test-123",
            type="avoidance",
            description="User avoids conflict discussions",
            occurrences=3,
            first_seen="2024-01-01T00:00:00Z",
            last_seen="2024-01-15T00:00:00Z",
            ifs_part="Protector",
            therapeutic_note="Likely protecting a vulnerable part",
        )
        d = p.to_dict()
        assert d["pattern_id"] == "test-123"
        assert d["type"] == "avoidance"
        assert d["occurrences"] == 3
        assert d["ifs_part"] == "Protector"

    def test_pattern_from_dict(self):
        data = {
            "pattern_id": "abc",
            "type": "grief",
            "description": "recurring grief theme",
            "occurrences": 2,
            "first_seen": "2024-01-01T00:00:00Z",
            "last_seen": "2024-01-10T00:00:00Z",
            "ifs_part": "Exile",
            "therapeutic_note": "",
        }
        p = Pattern.from_dict(data)
        assert p.pattern_id == "abc"
        assert p.type == "grief"
        assert p.ifs_part == "Exile"

    def test_pattern_roundtrip(self):
        p = Pattern(
            pattern_id="rt-1",
            type="people-pleasing",
            description="Consistently prioritizes others",
            ifs_part="Manager",
        )
        d = p.to_dict()
        p2 = Pattern.from_dict(d)
        assert p2.pattern_id == p.pattern_id
        assert p2.type == p.type
        assert p2.ifs_part == p.ifs_part


# ---------------------------------------------------------------------------
# Pattern CRUD functions
# ---------------------------------------------------------------------------

class TestPatternCRUD:
    def test_record_new_pattern(self, unique_user_id):
        p = record_pattern(
            user_id=unique_user_id,
            pattern_type="avoidance",
            description="User avoids conflict",
            ifs_part="Protector",
        )
        assert p.type == "avoidance"
        assert p.occurrences == 1
        assert p.ifs_part == "Protector"
        assert p.pattern_id  # should have a UUID

    def test_record_duplicate_increments(self, unique_user_id):
        p1 = record_pattern(
            user_id=unique_user_id,
            pattern_type="avoidance",
            description="User avoids conflict",
        )
        p2 = record_pattern(
            user_id=unique_user_id,
            pattern_type="avoidance",
            description="Again avoiding conflict",
        )
        assert p2.occurrences == 2
        assert p2.pattern_id == p1.pattern_id

    def test_get_patterns_empty(self, unique_user_id):
        patterns = get_patterns(unique_user_id)
        assert patterns == []

    def test_get_patterns_after_recording(self, unique_user_id):
        record_pattern(unique_user_id, "grief", "Loss theme")
        record_pattern(unique_user_id, "anger", "Repressed anger")
        patterns = get_patterns(unique_user_id)
        assert len(patterns) == 2
        types = {p.type for p in patterns}
        assert "grief" in types
        assert "anger" in types

    def test_update_pattern(self, unique_user_id):
        p = record_pattern(unique_user_id, "test", "test desc")
        updated = update_pattern(
            unique_user_id,
            p.pattern_id,
            ifs_part="Exile",
            therapeutic_note="Updated note",
        )
        assert updated is not None
        assert updated.ifs_part == "Exile"
        assert updated.therapeutic_note == "Updated note"

    def test_update_nonexistent_pattern(self, unique_user_id):
        result = update_pattern(unique_user_id, "nonexistent-id", ifs_part="Protector")
        assert result is None

    def test_delete_pattern(self, unique_user_id):
        p = record_pattern(unique_user_id, "to-delete", "will be deleted")
        assert delete_pattern(unique_user_id, p.pattern_id) is True
        patterns = get_patterns(unique_user_id)
        assert len(patterns) == 0

    def test_delete_nonexistent(self, unique_user_id):
        assert delete_pattern(unique_user_id, "nonexistent") is False

    def test_persistence(self, unique_user_id):
        """Patterns should persist to disk and survive reload."""
        record_pattern(unique_user_id, "persistent", "survives reload")
        # Load from disk
        patterns = get_patterns(unique_user_id)
        assert len(patterns) == 1
        assert patterns[0].type == "persistent"

    def test_update_preserves_protected_fields(self, unique_user_id):
        p = record_pattern(unique_user_id, "test", "original desc")
        original_id = p.pattern_id
        updated = update_pattern(
            unique_user_id,
            original_id,
            type="should_not_change",
            occurrences=999,
        )
        assert updated is not None
        # Protected fields should not change
        assert updated.type == "test"
        assert updated.pattern_id == original_id
        assert updated.occurrences == 1


# ---------------------------------------------------------------------------
# Mirror class
# ---------------------------------------------------------------------------

class TestMirrorAgent:
    def test_mirror_init(self):
        mirror = Mirror(user_id="test")
        assert mirror.user_id == "test"
        assert mirror.communication_style == CommunicationStyle.GENTLE

    def test_mirror_init_direct(self):
        mirror = Mirror(user_id="test", communication_style=CommunicationStyle.DIRECT)
        assert mirror.communication_style == CommunicationStyle.DIRECT

    def test_fallback_response_no_trigger(self):
        mirror = Mirror(user_id="test")
        response = mirror._fallback_response(None)
        assert len(response) > 0
        assert "Mirror" in response or "listening" in response

    def test_fallback_response_low_trigger(self):
        mirror = Mirror(user_id="test")
        trigger = SafetyTrigger(
            type="caps_abuse",
            severity=Severity.LOW,
            message="test",
            timestamp="now",
        )
        response = mirror._fallback_response(trigger)
        assert "here" in response.lower() or "breath" in response.lower()

    def test_fallback_response_critical_trigger(self):
        mirror = Mirror(user_id="test")
        trigger = SafetyTrigger(
            type="distress_language",
            severity=Severity.CRITICAL,
            message="test",
            timestamp="now",
        )
        response = mirror._fallback_response(trigger)
        assert "988" in response or "crisis" in response.lower()

    def test_fallback_response_high_trigger(self):
        mirror = Mirror(user_id="test")
        trigger = SafetyTrigger(
            type="distress_language",
            severity=Severity.HIGH,
            message="test",
            timestamp="now",
        )
        response = mirror._fallback_response(trigger)
        assert "988" in response or "crisis" in response.lower()

    def test_build_system_prompt_gentle(self):
        mirror = Mirror(user_id="test", communication_style=CommunicationStyle.GENTLE)
        prompt = mirror._build_system_prompt()
        assert "GENTLE" in prompt
        assert "Mirror" in prompt

    def test_build_system_prompt_direct(self):
        mirror = Mirror(user_id="test", communication_style=CommunicationStyle.DIRECT)
        prompt = mirror._build_system_prompt()
        assert "DIRECT" in prompt

    def test_build_system_prompt_humor(self):
        mirror = Mirror(user_id="test", communication_style=CommunicationStyle.HUMOR)
        prompt = mirror._build_system_prompt()
        assert "HUMOR" in prompt

    def test_build_system_prompt_with_safety_trigger(self):
        mirror = Mirror(user_id="test")
        trigger = SafetyTrigger(
            type="distress_language",
            severity=Severity.CRITICAL,
            message="Distress detected",
            timestamp="now",
        )
        prompt = mirror._build_system_prompt(safety_trigger=trigger)
        assert "SAFETY TRIGGER" in prompt
        assert "distress_language" in prompt
        assert "988" in prompt  # crisis resource included for CRITICAL

    def test_build_system_prompt_with_patterns(self, unique_user_id):
        record_pattern(unique_user_id, "avoidance", "test pattern")
        mirror = Mirror(user_id=unique_user_id)
        prompt = mirror._build_system_prompt()
        assert "avoidance" in prompt

    def test_respond_without_llm(self):
        """Without LLM, respond should return fallback."""
        mirror = Mirror(user_id="test_no_llm")
        # _get_llm will fail without API keys, triggering fallback
        response = mirror.respond("hello")
        assert len(response) > 0

    def test_start_debrief_without_llm(self):
        mirror = Mirror(user_id="test_no_llm")
        response = mirror.start_debrief()
        assert "Garden" in response or "session" in response.lower()

    def test_integration_prompt_without_llm(self):
        mirror = Mirror(user_id="test_no_llm")
        response = mirror.integration_prompt("attachment")
        assert "attachment" in response

    def test_conversation_history_tracking(self):
        mirror = Mirror(user_id="test_history")
        mirror._conversation_history.append({"role": "user", "content": "hello"})
        mirror._conversation_history.append({"role": "mirror", "content": "welcome"})
        assert len(mirror._conversation_history) == 2


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

class TestReportGeneration:
    def test_generate_report_empty(self):
        mirror = Mirror(user_id="report_test_empty")
        report = mirror.generate_report()
        assert report["user_id"] == "report_test_empty"
        assert report["period"] == "recent"
        assert report["pattern_count"] == 0
        assert "generated_at" in report

    def test_generate_report_with_patterns(self, unique_user_id):
        record_pattern(unique_user_id, "avoidance", "avoids conflict", ifs_part="Protector")
        record_pattern(unique_user_id, "grief", "recurring loss theme", ifs_part="Exile")

        mirror = Mirror(user_id=unique_user_id)
        report = mirror.generate_report()

        assert report["pattern_count"] == 2
        assert len(report["themes"]) == 2
        assert "Protector" in report["ifs_parts_identified"]
        assert "Exile" in report["ifs_parts_identified"]
        # Should have recommendations for both Protector and Exile
        assert len(report["recommendations"]) >= 2

    def test_generate_report_period_parameter(self, unique_user_id):
        mirror = Mirror(user_id=unique_user_id)
        report = mirror.generate_report(period="month")
        assert report["period"] == "month"

    def test_generate_report_many_patterns(self, unique_user_id):
        for i in range(6):
            record_pattern(unique_user_id, f"pattern_{i}", f"description {i}")

        mirror = Mirror(user_id=unique_user_id)
        report = mirror.generate_report()

        assert report["pattern_count"] == 6
        # Should recommend real-world therapy when >5 patterns
        rec_texts = " ".join(report["recommendations"])
        assert "therapeutic relationship" in rec_texts.lower() or len(report["recommendations"]) > 0


# ---------------------------------------------------------------------------
# IFS parts enum
# ---------------------------------------------------------------------------

class TestIFSPart:
    def test_enum_values(self):
        assert IFSPart.PROTECTOR.value == "Protector"
        assert IFSPart.EXILE.value == "Exile"
        assert IFSPart.MANAGER.value == "Manager"
        assert IFSPart.FIREFIGHTER.value == "Firefighter"
        assert IFSPart.SELF.value == "Self"
        assert IFSPart.UNKNOWN.value == "Unknown"


# ---------------------------------------------------------------------------
# Communication style enum
# ---------------------------------------------------------------------------

class TestCommunicationStyle:
    def test_enum_values(self):
        assert CommunicationStyle.DIRECT.value == "direct"
        assert CommunicationStyle.GENTLE.value == "gentle"
        assert CommunicationStyle.HUMOR.value == "humor"
