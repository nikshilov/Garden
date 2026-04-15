"""Tests for Phase 7: Autonomy — Self-Healing Garden (Health Monitor)."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from garden_graph.health import (
    HealthMonitor, SelfRepair, HealthCheck, HealthStatus,
    overall_status,
)


class TestHealthStatus(unittest.TestCase):
    """Test HealthStatus enum ordering."""

    def test_ordering(self):
        self.assertTrue(HealthStatus.GREEN < HealthStatus.YELLOW)
        self.assertTrue(HealthStatus.YELLOW < HealthStatus.RED)
        self.assertFalse(HealthStatus.RED < HealthStatus.GREEN)

    def test_overall_status_green(self):
        checks = [
            HealthCheck("eve", "memory", HealthStatus.GREEN, "ok", False, "t"),
            HealthCheck("eve", "mood", HealthStatus.GREEN, "ok", False, "t"),
        ]
        self.assertEqual(overall_status(checks), HealthStatus.GREEN)

    def test_overall_status_yellow(self):
        checks = [
            HealthCheck("eve", "memory", HealthStatus.GREEN, "ok", False, "t"),
            HealthCheck("eve", "mood", HealthStatus.YELLOW, "stale", False, "t"),
        ]
        self.assertEqual(overall_status(checks), HealthStatus.YELLOW)

    def test_overall_status_red(self):
        checks = [
            HealthCheck("eve", "memory", HealthStatus.GREEN, "ok", False, "t"),
            HealthCheck("eve", "mood", HealthStatus.RED, "broken", False, "t"),
        ]
        self.assertEqual(overall_status(checks), HealthStatus.RED)

    def test_overall_status_empty(self):
        self.assertEqual(overall_status([]), HealthStatus.GREEN)


class TestMemoryHealth(unittest.TestCase):
    """Test memory health checks."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.monitor = HealthMonitor(data_dir=self.tmpdir)

    def test_no_records_is_green(self):
        checks = self.monitor.check_memory_health("newchar")
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].status, HealthStatus.GREEN)
        self.assertIn("new character", checks[0].message.lower())


class TestMoodHealth(unittest.TestCase):
    """Test mood health checks."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.monitor = HealthMonitor(data_dir=self.tmpdir)

    def test_missing_mood_file_is_red(self):
        checks = self.monitor.check_mood_health("eve")
        self.assertEqual(checks[0].status, HealthStatus.RED)
        self.assertIn("missing", checks[0].message.lower())

    def test_healthy_mood_is_green(self):
        mood_data = {
            "eve": {
                "vector": {"valence": 0.2, "arousal": 0.1, "tension": -0.1},
                "set_at": datetime.now(timezone.utc).isoformat(),
            }
        }
        with open(os.path.join(self.tmpdir, "mood_states.json"), "w") as f:
            json.dump(mood_data, f)

        checks = self.monitor.check_mood_health("eve")
        self.assertEqual(checks[0].status, HealthStatus.GREEN)

    def test_extreme_mood_is_yellow(self):
        mood_data = {
            "eve": {
                "vector": {"valence": 0.95, "arousal": 0.1},
                "set_at": datetime.now(timezone.utc).isoformat(),
            }
        }
        with open(os.path.join(self.tmpdir, "mood_states.json"), "w") as f:
            json.dump(mood_data, f)

        checks = self.monitor.check_mood_health("eve")
        statuses = [c.status for c in checks]
        self.assertIn(HealthStatus.YELLOW, statuses)
        extreme_check = [c for c in checks if c.status == HealthStatus.YELLOW][0]
        self.assertTrue(extreme_check.auto_fixable)

    def test_stale_mood_is_yellow(self):
        old_time = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        mood_data = {
            "eve": {
                "vector": {"valence": 0.1, "arousal": 0.1},
                "set_at": old_time,
            }
        }
        with open(os.path.join(self.tmpdir, "mood_states.json"), "w") as f:
            json.dump(mood_data, f)

        checks = self.monitor.check_mood_health("eve")
        statuses = [c.status for c in checks]
        self.assertIn(HealthStatus.YELLOW, statuses)

    def test_no_char_entry_is_red(self):
        mood_data = {"atlas": {"vector": {}, "set_at": "2026-01-01T00:00:00+00:00"}}
        with open(os.path.join(self.tmpdir, "mood_states.json"), "w") as f:
            json.dump(mood_data, f)

        checks = self.monitor.check_mood_health("eve")
        self.assertEqual(checks[0].status, HealthStatus.RED)


class TestRelationshipHealth(unittest.TestCase):
    """Test relationship health checks."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.monitor = HealthMonitor(data_dir=self.tmpdir)

    def test_no_files_is_green(self):
        checks = self.monitor.check_relationship_health("eve")
        self.assertEqual(checks[0].status, HealthStatus.GREEN)

    def test_out_of_bounds_is_yellow(self):
        rel_data = {
            "eve": {"affection": 1.5, "trust": 0.3}
        }
        with open(os.path.join(self.tmpdir, "relationships.json"), "w") as f:
            json.dump(rel_data, f)

        checks = self.monitor.check_relationship_health("eve")
        statuses = [c.status for c in checks]
        self.assertIn(HealthStatus.YELLOW, statuses)
        oob_check = [c for c in checks if "out of bounds" in c.message.lower()][0]
        self.assertTrue(oob_check.auto_fixable)


class TestCoherence(unittest.TestCase):
    """Test coherence (repetition) checks."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.monitor = HealthMonitor(data_dir=self.tmpdir)

    def test_word_overlap_identical(self):
        self.assertEqual(HealthMonitor._word_overlap("hello world", "hello world"), 1.0)

    def test_word_overlap_different(self):
        self.assertEqual(HealthMonitor._word_overlap("hello world", "foo bar"), 0.0)

    def test_word_overlap_partial(self):
        overlap = HealthMonitor._word_overlap("hello beautiful world", "hello world today")
        self.assertGreater(overlap, 0.5)

    def test_word_overlap_empty(self):
        self.assertEqual(HealthMonitor._word_overlap("", "hello"), 0.0)


class TestSelfRepairMood(unittest.TestCase):
    """Test mood self-repair."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repair = SelfRepair(data_dir=self.tmpdir)

    def test_reset_stuck_mood(self):
        mood_data = {
            "eve": {
                "vector": {"valence": 0.95, "arousal": -0.92, "tension": 0.3},
                "set_at": datetime.now(timezone.utc).isoformat(),
            }
        }
        mood_path = os.path.join(self.tmpdir, "mood_states.json")
        with open(mood_path, "w") as f:
            json.dump(mood_data, f)

        result = self.repair.reset_stuck_mood("eve")
        self.assertTrue(result)

        # Verify the values were reset
        with open(mood_path) as f:
            updated = json.load(f)
        self.assertEqual(updated["eve"]["vector"]["valence"], 0.0)
        self.assertEqual(updated["eve"]["vector"]["arousal"], 0.0)
        self.assertEqual(updated["eve"]["vector"]["tension"], 0.3)  # untouched

    def test_no_reset_needed(self):
        mood_data = {
            "eve": {
                "vector": {"valence": 0.3, "arousal": -0.2},
                "set_at": datetime.now(timezone.utc).isoformat(),
            }
        }
        with open(os.path.join(self.tmpdir, "mood_states.json"), "w") as f:
            json.dump(mood_data, f)

        result = self.repair.reset_stuck_mood("eve")
        self.assertFalse(result)


class TestSelfRepairRelationships(unittest.TestCase):
    """Test relationship axis clamping."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repair = SelfRepair(data_dir=self.tmpdir)

    def test_clamp_user_relationships(self):
        rel_data = {
            "eve": {"affection": 1.5, "trust": -1.3, "respect": 0.5}
        }
        rel_path = os.path.join(self.tmpdir, "relationships.json")
        with open(rel_path, "w") as f:
            json.dump(rel_data, f)

        result = self.repair.clamp_relationship_axes("eve")
        self.assertTrue(result)

        with open(rel_path) as f:
            updated = json.load(f)
        self.assertEqual(updated["eve"]["affection"], 1.0)
        self.assertEqual(updated["eve"]["trust"], -1.0)
        self.assertEqual(updated["eve"]["respect"], 0.5)  # untouched

    def test_clamp_char_relationships(self):
        char_rel_data = {
            "eve": {"atlas": {"affection": 2.0, "trust": 0.3}}
        }
        char_rel_path = os.path.join(self.tmpdir, "char_relationships.json")
        with open(char_rel_path, "w") as f:
            json.dump(char_rel_data, f)

        result = self.repair.clamp_relationship_axes("eve")
        self.assertTrue(result)

        with open(char_rel_path) as f:
            updated = json.load(f)
        self.assertEqual(updated["eve"]["atlas"]["affection"], 1.0)
        self.assertEqual(updated["eve"]["atlas"]["trust"], 0.3)


class TestRepairAll(unittest.TestCase):
    """Test aggregate repair."""

    def test_repair_dispatches_correctly(self):
        tmpdir = tempfile.mkdtemp()
        repair = SelfRepair(data_dir=tmpdir)

        # Create mood with extreme value
        mood_data = {
            "eve": {
                "vector": {"valence": 0.99},
                "set_at": datetime.now(timezone.utc).isoformat(),
            }
        }
        with open(os.path.join(tmpdir, "mood_states.json"), "w") as f:
            json.dump(mood_data, f)

        checks = [
            HealthCheck("eve", "mood", HealthStatus.YELLOW, "Mood axes stuck at extremes: valence=0.99.", True, "t"),
        ]

        repairs = repair.repair_all("eve", checks)
        self.assertEqual(len(repairs), 1)
        self.assertIn("Reset stuck mood", repairs[0])

    def test_non_fixable_skipped(self):
        tmpdir = tempfile.mkdtemp()
        repair = SelfRepair(data_dir=tmpdir)

        checks = [
            HealthCheck("eve", "mood", HealthStatus.YELLOW, "Mood stale", False, "t"),
        ]

        repairs = repair.repair_all("eve", checks)
        self.assertEqual(len(repairs), 0)


class TestHealthCheckSerialization(unittest.TestCase):
    """Test HealthCheck.to_dict()."""

    def test_to_dict(self):
        check = HealthCheck(
            char_id="eve",
            category="memory",
            status=HealthStatus.GREEN,
            message="All good",
            auto_fixable=False,
            checked_at="2026-01-01T00:00:00+00:00",
        )
        d = check.to_dict()
        self.assertEqual(d["char_id"], "eve")
        self.assertEqual(d["status"], "green")
        self.assertEqual(d["category"], "memory")


class TestCheckAllCharacters(unittest.TestCase):
    """Test batch character health check."""

    def test_check_all_characters(self):
        tmpdir = tempfile.mkdtemp()
        monitor = HealthMonitor(data_dir=tmpdir)
        results = monitor.check_all_characters(["eve", "atlas"])
        self.assertIn("eve", results)
        self.assertIn("atlas", results)
        # Both should have at least memory + mood + relationship + coherence checks
        for char_id in ["eve", "atlas"]:
            categories = {c.category for c in results[char_id]}
            self.assertIn("memory", categories)
            self.assertIn("mood", categories)


if __name__ == "__main__":
    unittest.main()
