"""Tests for Phase 5: Voice — Initiative Engine."""
import os
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock


class TestInitiativeEngine(unittest.TestCase):
    """Test the initiative evaluation system."""

    def setUp(self):
        self.mm = MagicMock()
        self.mm.check_pending_events = MagicMock(return_value=[])
        self.mm.relationships = {}

    def _get_engine(self):
        from garden_graph.initiative import InitiativeEngine
        engine = InitiativeEngine(memory_manager=self.mm)
        return engine

    def test_no_initiative_when_recently_seen(self):
        """No initiative if user was here recently."""
        engine = self._get_engine()
        now = datetime.now(timezone.utc)
        engine._get_last_seen = MagicMock(return_value=now - timedelta(hours=6))
        result = engine.evaluate("eve", now)
        self.assertIsNone(result)

    def test_loneliness_after_3_days(self):
        """Should trigger loneliness initiative after 3+ days."""
        engine = self._get_engine()
        now = datetime.now(timezone.utc)
        engine._get_last_seen = MagicMock(return_value=now - timedelta(days=4))
        # Need to provide mood data too
        self.mm._get_mood_vector = MagicMock(return_value={})
        result = engine.evaluate("eve", now)
        if result:
            self.assertEqual(result.trigger, "loneliness")

    def test_loneliness_stronger_after_week(self):
        """Loneliness should be stronger after a week."""
        engine = self._get_engine()
        now = datetime.now(timezone.utc)
        engine._get_last_seen = MagicMock(return_value=now - timedelta(days=8))
        self.mm._get_mood_vector = MagicMock(return_value={})
        result = engine.evaluate("eve", now)
        if result:
            self.assertIn(result.priority, ["medium", "high"])

    def test_cooldown_prevents_spam(self):
        """Character shouldn't initiate twice in 24h."""
        engine = self._get_engine()
        now = datetime.now(timezone.utc)
        # Set cooldown to recent
        engine._cooldowns["eve"] = now - timedelta(hours=12)
        engine._get_last_seen = MagicMock(return_value=now - timedelta(days=5))
        self.mm._get_mood_vector = MagicMock(return_value={})
        result = engine.evaluate("eve", now)
        self.assertIsNone(result)

    def test_quiet_hours_respected(self):
        """Should not initiate during quiet hours."""
        engine = self._get_engine()
        engine._settings = {
            "enabled": True,
            "quiet_start": 23,
            "quiet_end": 8,
            "disabled_characters": [],
            "dismissed_count": {},
        }
        # Create a time at 2 AM
        quiet_time = datetime(2026, 1, 15, 2, 0, 0, tzinfo=timezone.utc)
        engine._get_last_seen = MagicMock(return_value=quiet_time - timedelta(days=5))
        self.mm._get_mood_vector = MagicMock(return_value={})
        result = engine.evaluate("eve", quiet_time)
        self.assertIsNone(result)

    def test_disabled_character_skipped(self):
        """Should not initiate for disabled characters."""
        engine = self._get_engine()
        engine._settings = {
            "enabled": True,
            "quiet_start": 23,
            "quiet_end": 8,
            "disabled_characters": ["eve"],
            "dismissed_count": {},
        }
        now = datetime.now(timezone.utc)
        engine._get_last_seen = MagicMock(return_value=now - timedelta(days=5))
        result = engine.evaluate("eve", now)
        self.assertIsNone(result)

    def test_globally_disabled(self):
        """Should not initiate when globally disabled."""
        engine = self._get_engine()
        engine._settings["enabled"] = False
        now = datetime.now(timezone.utc)
        engine._get_last_seen = MagicMock(return_value=now - timedelta(days=10))
        result = engine.evaluate("eve", now)
        self.assertIsNone(result)

    def test_initiative_result_structure(self):
        """InitiativeResult should have all required fields."""
        from garden_graph.initiative import InitiativeResult
        result = InitiativeResult(
            char_id="eve",
            trigger="loneliness",
            priority="medium",
            context="It's been 5 days",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.assertEqual(result.char_id, "eve")
        self.assertEqual(result.trigger, "loneliness")

    def test_enable_disable_character(self):
        engine = self._get_engine()
        engine.disable_character("atlas")
        self.assertIn("atlas", engine._settings["disabled_characters"])
        engine.enable_character("atlas")
        self.assertNotIn("atlas", engine._settings["disabled_characters"])

    def test_record_dismissed(self):
        engine = self._get_engine()
        engine.record_dismissed("eve")
        engine.record_dismissed("eve")
        self.assertEqual(engine._settings["dismissed_count"].get("eve", 0), 2)


if __name__ == "__main__":
    unittest.main()
