"""Tests for the Narrative Arc Tracker (Phase B)."""
import json
import os
import pytest
from unittest.mock import patch

from garden_graph.narrative_arc import (
    ArcPhase,
    ArcEvent,
    PhaseTransition,
    NarrativeArc,
    save_arc,
    load_arc,
    PHASE_MIN_EVENTS,
    CRISIS_SIGNALS,
    REPAIR_SIGNALS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def fresh_arc() -> NarrativeArc:
    return NarrativeArc(user_id="test-user-001")


@pytest.fixture()
def tmp_arcs_dir(tmp_path):
    arcs_dir = tmp_path / "narrative_arcs"
    arcs_dir.mkdir()
    with patch("garden_graph.narrative_arc._get_arcs_dir", return_value=str(arcs_dir)):
        yield arcs_dir


# ---------------------------------------------------------------------------
# Basic initialization tests
# ---------------------------------------------------------------------------

class TestNarrativeArcInit:
    def test_starts_in_establishing_phase(self, fresh_arc):
        assert fresh_arc.current_phase == ArcPhase.establishing

    def test_has_empty_events(self, fresh_arc):
        assert fresh_arc.key_events == []
        assert fresh_arc.intensity_curve == []
        assert fresh_arc.phase_transitions == []

    def test_get_current_phase(self, fresh_arc):
        assert fresh_arc.get_current_phase() == ArcPhase.establishing


# ---------------------------------------------------------------------------
# update_arc tests
# ---------------------------------------------------------------------------

class TestUpdateArc:
    def test_adds_event(self, fresh_arc):
        event = fresh_arc.update_arc({
            "description": "User shared a memory",
            "emotional_intensity": 0.3,
        })
        assert isinstance(event, ArcEvent)
        assert event.description == "User shared a memory"
        assert event.emotional_intensity == 0.3
        assert event.phase == ArcPhase.establishing.value
        assert len(fresh_arc.key_events) == 1
        assert len(fresh_arc.intensity_curve) == 1

    def test_clamps_intensity(self, fresh_arc):
        event = fresh_arc.update_arc({
            "description": "Extreme event",
            "emotional_intensity": 5.0,
        })
        assert event.emotional_intensity == 1.0

        event2 = fresh_arc.update_arc({
            "description": "Negative intensity",
            "emotional_intensity": -1.0,
        })
        assert event2.emotional_intensity == 0.0

    def test_default_event_type(self, fresh_arc):
        event = fresh_arc.update_arc({"description": "test"})
        assert event.event_type == "message"

    def test_custom_event_type(self, fresh_arc):
        event = fresh_arc.update_arc({
            "description": "test",
            "event_type": "milestone",
        })
        assert event.event_type == "milestone"

    def test_metadata_preserved(self, fresh_arc):
        event = fresh_arc.update_arc({
            "description": "test",
            "metadata": {"custom_key": "value"},
        })
        assert event.metadata == {"custom_key": "value"}


# ---------------------------------------------------------------------------
# Phase advancement tests
# ---------------------------------------------------------------------------

class TestPhaseAdvancement:
    def test_does_not_advance_below_min_events(self, fresh_arc):
        # Add fewer events than threshold
        fresh_arc.update_arc({"description": "event 1", "emotional_intensity": 0.5})
        fresh_arc.update_arc({"description": "event 2", "emotional_intensity": 0.5})
        assert fresh_arc.should_advance_phase() is False
        assert fresh_arc.current_phase == ArcPhase.establishing

    def test_advances_after_threshold(self, fresh_arc):
        # establishing needs 3 events with avg intensity >= 0.3
        for i in range(4):
            fresh_arc.update_arc({
                "description": f"meaningful event {i}",
                "emotional_intensity": 0.5,
            })
        # Should have advanced to deepening
        assert fresh_arc.current_phase == ArcPhase.deepening
        assert len(fresh_arc.phase_transitions) >= 1

    def test_phase_transition_recorded(self, fresh_arc):
        for i in range(4):
            fresh_arc.update_arc({
                "description": f"event {i}",
                "emotional_intensity": 0.5,
            })
        transitions = fresh_arc.phase_transitions
        assert len(transitions) >= 1
        t = transitions[0]
        assert t.from_phase == ArcPhase.establishing.value
        assert t.to_phase == ArcPhase.deepening.value
        assert t.reason  # non-empty

    def test_low_intensity_does_not_advance(self, fresh_arc):
        for i in range(10):
            fresh_arc.update_arc({
                "description": f"bland event {i}",
                "emotional_intensity": 0.1,
            })
        assert fresh_arc.current_phase == ArcPhase.establishing


# ---------------------------------------------------------------------------
# Crisis detection tests
# ---------------------------------------------------------------------------

class TestCrisisDetection:
    def test_crisis_signal_triggers_crisis_phase(self, fresh_arc):
        # First, get past establishing
        for i in range(4):
            fresh_arc.update_arc({
                "description": f"warmth {i}",
                "emotional_intensity": 0.5,
            })
        # Now in deepening — trigger crisis
        fresh_arc.update_arc({
            "description": "I feel betrayed and hurt by what you said",
            "emotional_intensity": 0.8,
        })
        assert fresh_arc.current_phase == ArcPhase.crisis

    def test_crisis_requires_high_intensity(self, fresh_arc):
        # Crisis signal but low intensity should not trigger
        fresh_arc.update_arc({
            "description": "I'm a little hurt",
            "emotional_intensity": 0.3,
        })
        assert fresh_arc.current_phase == ArcPhase.establishing

    def test_repair_signal_during_crisis(self, fresh_arc):
        # Force into crisis
        fresh_arc.current_phase = ArcPhase.crisis
        fresh_arc._phase_event_counts[ArcPhase.crisis.value] = 1

        fresh_arc.update_arc({
            "description": "I understand and I'm sorry for reacting that way",
            "emotional_intensity": 0.5,
        })
        assert fresh_arc.current_phase == ArcPhase.repair


# ---------------------------------------------------------------------------
# Mirror handoff triggers tests
# ---------------------------------------------------------------------------

class TestMirrorHandoff:
    def test_no_triggers_on_empty_arc(self, fresh_arc):
        triggers = fresh_arc.get_mirror_handoff_triggers()
        assert triggers == []

    def test_wound_activation_in_crisis(self, fresh_arc):
        fresh_arc.current_phase = ArcPhase.crisis
        fresh_arc.key_events.append(ArcEvent(
            timestamp="2026-01-01T00:00:00",
            phase="crisis",
            event_type="message",
            description="intense event",
            emotional_intensity=0.9,
        ))
        triggers = fresh_arc.get_mirror_handoff_triggers()
        assert "wound_activation" in triggers

    def test_pattern_recognition_on_repeated_high_intensity(self, fresh_arc):
        for i in range(3):
            fresh_arc.key_events.append(ArcEvent(
                timestamp=f"2026-01-01T00:0{i}:00",
                phase="establishing",
                event_type="message",
                description=f"intense event {i}",
                emotional_intensity=0.8,
            ))
        triggers = fresh_arc.get_mirror_handoff_triggers()
        assert "pattern_recognition" in triggers

    def test_breakthrough_after_crisis_to_repair(self, fresh_arc):
        fresh_arc.current_phase = ArcPhase.repair
        fresh_arc.phase_transitions.append(PhaseTransition(
            from_phase=ArcPhase.crisis.value,
            to_phase=ArcPhase.repair.value,
            timestamp="2026-01-01T00:00:00",
            reason="repair signal",
        ))
        fresh_arc.key_events.append(ArcEvent(
            timestamp="2026-01-01T00:00:00",
            phase="repair",
            event_type="message",
            description="healing",
            emotional_intensity=0.4,
        ))
        triggers = fresh_arc.get_mirror_handoff_triggers()
        assert "breakthrough_moment" in triggers

    def test_resistance_in_testing(self, fresh_arc):
        fresh_arc.current_phase = ArcPhase.testing
        for i in range(4):
            fresh_arc.key_events.append(ArcEvent(
                timestamp=f"2026-01-01T00:0{i}:00",
                phase="testing",
                event_type="message",
                description=f"tense event {i}",
                emotional_intensity=0.7,
            ))
        fresh_arc._phase_event_counts["testing"] = 4
        triggers = fresh_arc.get_mirror_handoff_triggers()
        assert "resistance" in triggers

    def test_integration_ready_on_low_intensity(self, fresh_arc):
        fresh_arc.current_phase = ArcPhase.integration
        for i in range(4):
            fresh_arc.key_events.append(ArcEvent(
                timestamp=f"2026-01-01T00:0{i}:00",
                phase="integration",
                event_type="message",
                description=f"calm event {i}",
                emotional_intensity=0.1,
            ))
        triggers = fresh_arc.get_mirror_handoff_triggers()
        assert "integration_ready" in triggers


# ---------------------------------------------------------------------------
# Serialization tests
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_to_dict_roundtrip(self, fresh_arc):
        fresh_arc.update_arc({"description": "event", "emotional_intensity": 0.5})
        data = fresh_arc.to_dict()
        restored = NarrativeArc.from_dict(data)
        assert restored.user_id == fresh_arc.user_id
        assert restored.current_phase == fresh_arc.current_phase
        assert len(restored.key_events) == len(fresh_arc.key_events)
        assert restored.intensity_curve == fresh_arc.intensity_curve

    def test_to_dict_json_serializable(self, fresh_arc):
        fresh_arc.update_arc({"description": "event", "emotional_intensity": 0.5})
        data = fresh_arc.to_dict()
        json_str = json.dumps(data)
        assert json_str  # no error


# ---------------------------------------------------------------------------
# Persistence tests
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_save_and_load(self, fresh_arc, tmp_arcs_dir):
        fresh_arc.update_arc({"description": "saved event", "emotional_intensity": 0.6})
        save_arc(fresh_arc)
        loaded = load_arc("test-user-001")
        assert loaded is not None
        assert loaded.user_id == "test-user-001"
        assert len(loaded.key_events) == 1
        assert loaded.key_events[0].description == "saved event"

    def test_load_nonexistent(self, tmp_arcs_dir):
        result = load_arc("nonexistent-user")
        assert result is None

    def test_save_overwrites(self, fresh_arc, tmp_arcs_dir):
        fresh_arc.update_arc({"description": "first", "emotional_intensity": 0.3})
        save_arc(fresh_arc)

        fresh_arc.update_arc({"description": "second", "emotional_intensity": 0.4})
        save_arc(fresh_arc)

        loaded = load_arc("test-user-001")
        assert len(loaded.key_events) == 2


# ---------------------------------------------------------------------------
# ArcEvent and PhaseTransition model tests
# ---------------------------------------------------------------------------

class TestModels:
    def test_arc_event_to_dict(self):
        event = ArcEvent(
            timestamp="2026-01-01T00:00:00",
            phase="establishing",
            event_type="message",
            description="test",
            emotional_intensity=0.5,
            metadata={"key": "val"},
        )
        d = event.to_dict()
        assert d["phase"] == "establishing"
        assert d["metadata"] == {"key": "val"}

    def test_arc_event_from_dict(self):
        d = {
            "timestamp": "2026-01-01T00:00:00",
            "phase": "deepening",
            "event_type": "milestone",
            "description": "reached milestone",
            "emotional_intensity": 0.7,
            "metadata": {},
        }
        event = ArcEvent.from_dict(d)
        assert event.phase == "deepening"
        assert event.emotional_intensity == 0.7

    def test_phase_transition_roundtrip(self):
        t = PhaseTransition(
            from_phase="establishing",
            to_phase="deepening",
            timestamp="2026-01-01T00:00:00",
            reason="natural",
        )
        d = t.to_dict()
        restored = PhaseTransition.from_dict(d)
        assert restored.from_phase == "establishing"
        assert restored.to_phase == "deepening"
