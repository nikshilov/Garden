"""Tests for the Heartbeat engine (Phase 1)."""
import asyncio
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

from garden_graph.heartbeat import Heartbeat, HEARTBEAT_INTERVAL_HOURS


class TestHeartbeat(unittest.TestCase):
    """Unit tests for Heartbeat lifecycle and character processing."""

    def setUp(self):
        self.char_ids = ["eve", "atlas"]
        self.mm = MagicMock()
        self.mm.relationships = {
            "eve": {
                "affection": 0.5,
                "trust": 0.3,
                "familiarity": 0.4,
                "engagement": 0.2,
                "security": 0.1,
                "tension": 0.3,
            },
        }
        self.mm.check_pending_events = MagicMock(return_value=[])
        self.mm.save_to_file = MagicMock()
        self.mm.get_default_filepath = MagicMock(return_value="/tmp/test_mem.json")
        self.hb = Heartbeat(character_ids=self.char_ids, memory_manager=self.mm)

    def test_init(self):
        assert self.hb.character_ids == ["eve", "atlas"]
        assert self.hb._running is False
        assert self.hb._task is None

    def test_start_stop(self):
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self.hb.start())
            assert self.hb._running is True
            assert self.hb._task is not None

            loop.run_until_complete(self.hb.stop())
            assert self.hb._running is False
        finally:
            loop.close()

    def test_start_idempotent(self):
        """Starting twice should not create a second task."""
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self.hb.start())
            task1 = self.hb._task
            loop.run_until_complete(self.hb.start())
            task2 = self.hb._task
            assert task1 is task2
            loop.run_until_complete(self.hb.stop())
        finally:
            loop.close()

    def test_drift_relationships_decays_familiarity(self):
        """Familiarity should decay toward 0 after absence."""
        now = datetime.now(timezone.utc)
        two_days_ago = now - timedelta(days=2)

        # Mock last_seen to return 2 days ago
        self.hb._get_last_seen = MagicMock(return_value=two_days_ago)

        original_fam = self.mm.relationships["eve"]["familiarity"]
        self.hb._drift_relationships("eve", now)
        new_fam = self.mm.relationships["eve"]["familiarity"]

        assert new_fam < original_fam, f"familiarity should decay: {original_fam} -> {new_fam}"

    def test_drift_relationships_resolves_tension(self):
        """Tension should resolve over time (forgiveness)."""
        now = datetime.now(timezone.utc)
        three_days_ago = now - timedelta(days=3)
        self.hb._get_last_seen = MagicMock(return_value=three_days_ago)

        original_tension = self.mm.relationships["eve"]["tension"]
        self.hb._drift_relationships("eve", now)
        new_tension = self.mm.relationships["eve"]["tension"]

        assert new_tension < original_tension, f"tension should resolve: {original_tension} -> {new_tension}"

    def test_drift_no_change_for_recent_contact(self):
        """No drift when user was seen less than 12 hours ago."""
        now = datetime.now(timezone.utc)
        recent = now - timedelta(hours=6)
        self.hb._get_last_seen = MagicMock(return_value=recent)

        original_fam = self.mm.relationships["eve"]["familiarity"]
        self.hb._drift_relationships("eve", now)
        new_fam = self.mm.relationships["eve"]["familiarity"]

        assert new_fam == original_fam, "no drift within 12 hours"

    def test_drift_no_crash_without_relationship(self):
        """Should not crash when character has no relationship data."""
        self.hb._drift_relationships("atlas", datetime.now(timezone.utc))

    def test_tick_calls_all_characters(self):
        """tick() should process every character."""
        loop = asyncio.new_event_loop()
        try:
            # Patch _tick_character to track calls
            calls = []

            async def mock_tick(char_id, now):
                calls.append(char_id)

            self.hb._tick_character = mock_tick
            loop.run_until_complete(self.hb.tick())
            assert calls == ["eve", "atlas"]
            # Should also try to persist
            self.mm.save_to_file.assert_called_once()
        finally:
            loop.close()

    def test_tick_character_processes_events(self):
        """_tick_character should check and complete pending events."""
        loop = asyncio.new_event_loop()
        try:
            fake_event = {"id": "evt-1", "description": "test event"}
            self.mm.check_pending_events = MagicMock(return_value=[fake_event])
            self.mm.complete_event = MagicMock()

            # Disable internal thought generation for this test
            self.hb._generate_internal_thought = AsyncMock()
            self.hb._get_last_seen = MagicMock(return_value=None)

            now = datetime.now(timezone.utc)
            loop.run_until_complete(self.hb._tick_character("eve", now))

            self.mm.check_pending_events.assert_called_once_with("eve", now)
            self.mm.complete_event.assert_called_once_with("evt-1", user_responded=False)
        finally:
            loop.close()


class TestTimeAwareGreetings(unittest.TestCase):
    """Tests for time-aware greeting generation in Character."""

    def test_first_conversation(self):
        """No last_seen_at should produce a first-conversation greeting."""
        from garden_graph.character import Character
        with patch("garden_graph.character.get_llm"):
            char = Character("eve", model_name="gpt-4o")
        char.last_seen_at = None
        ctx = char._time_context()
        assert "first conversation" in ctx.lower()

    def test_recent_visit(self):
        """Visit < 1 hour ago returns empty string."""
        from garden_graph.character import Character
        with patch("garden_graph.character.get_llm"):
            char = Character("eve", model_name="gpt-4o")
        char.last_seen_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        ctx = char._time_context()
        assert ctx == ""

    def test_earlier_today(self):
        """Visit 2-23 hours ago mentions 'earlier today'."""
        from garden_graph.character import Character
        with patch("garden_graph.character.get_llm"):
            char = Character("eve", model_name="gpt-4o")
        char.last_seen_at = datetime.now(timezone.utc) - timedelta(hours=5)
        ctx = char._time_context()
        assert "earlier today" in ctx.lower()

    def test_days_away(self):
        """Visit 2 days ago mentions the gap."""
        from garden_graph.character import Character
        with patch("garden_graph.character.get_llm"):
            char = Character("eve", model_name="gpt-4o")
        char.last_seen_at = datetime.now(timezone.utc) - timedelta(days=2)
        ctx = char._time_context()
        assert "day" in ctx.lower()

    def test_week_away(self):
        """Visit 10 days ago mentions weeks."""
        from garden_graph.character import Character
        with patch("garden_graph.character.get_llm"):
            char = Character("eve", model_name="gpt-4o")
        char.last_seen_at = datetime.now(timezone.utc) - timedelta(days=10)
        ctx = char._time_context()
        assert "week" in ctx.lower()


if __name__ == "__main__":
    unittest.main()
