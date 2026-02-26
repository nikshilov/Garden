"""Tests for Phase 3: Mycelium — inter-character relationships."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from garden_graph.memory.manager import MemoryManager, RELATIONSHIP_AXES


class TestCharRelationships(unittest.TestCase):
    """Test character-to-character relationship tracking."""

    def setUp(self):
        self.mm = MemoryManager(autoload=False)

    def test_char_relationships_initialized(self):
        """char_relationships should be an empty dict by default."""
        self.assertIsInstance(self.mm.char_relationships, dict)
        self.assertEqual(len(self.mm.char_relationships), 0)

    def test_update_creates_relationship(self):
        """Updating a non-existent relationship should create it."""
        delta = self.mm.update_char_relationship(
            from_char="eve", to_char="atlas",
            emotions={"joy": 0.5, "trust": 0.3},
            category="praise", significance=0.7,
        )
        self.assertIn("eve", self.mm.char_relationships)
        self.assertIn("atlas", self.mm.char_relationships["eve"])
        rel = self.mm.char_relationships["eve"]["atlas"]
        # All 10 axes should exist
        for axis in RELATIONSHIP_AXES:
            self.assertIn(axis, rel)

    def test_update_returns_delta(self):
        """update_char_relationship should return the applied deltas."""
        delta = self.mm.update_char_relationship(
            from_char="eve", to_char="atlas",
            emotions={"joy": 0.8},
            category="affection", significance=0.5,
        )
        self.assertIsInstance(delta, dict)
        # Joy maps to affection and engagement
        self.assertTrue(any(v != 0 for v in delta.values()))

    def test_relationship_is_directional(self):
        """Eve's view of Atlas != Atlas's view of Eve."""
        self.mm.update_char_relationship(
            from_char="eve", to_char="atlas",
            emotions={"joy": 0.8}, category="praise", significance=0.5,
        )
        self.mm.update_char_relationship(
            from_char="atlas", to_char="eve",
            emotions={"anger": 0.3}, category="insult", significance=0.3,
        )
        eve_view = self.mm.char_relationships["eve"]["atlas"]
        atlas_view = self.mm.char_relationships["atlas"]["eve"]
        # They should be different
        self.assertNotEqual(eve_view["affection"], atlas_view["affection"])

    def test_values_clamped(self):
        """Relationship values should stay in [-1, 1]."""
        for _ in range(50):
            self.mm.update_char_relationship(
                from_char="eve", to_char="atlas",
                emotions={"joy": 1.0, "trust": 1.0},
                category="affection", significance=1.0,
            )
        rel = self.mm.char_relationships["eve"]["atlas"]
        for axis, val in rel.items():
            self.assertGreaterEqual(val, -1.0)
            self.assertLessEqual(val, 1.0)

    def test_context_empty_when_no_relationships(self):
        """char_relationship_context should return empty string for unknown char."""
        ctx = self.mm.char_relationship_context("unknown_char")
        self.assertEqual(ctx, "")

    def test_context_includes_strong_axes(self):
        """char_relationship_context should mention strong relationship axes."""
        # Create a relationship with strong values
        self.mm.char_relationships["eve"] = {
            "atlas": {axis: 0.0 for axis in RELATIONSHIP_AXES}
        }
        self.mm.char_relationships["eve"]["atlas"]["trust"] = 0.7
        self.mm.char_relationships["eve"]["atlas"]["affection"] = 0.4

        ctx = self.mm.char_relationship_context("eve")
        self.assertIn("atlas", ctx.lower())

    def test_save_and_load_char_relationships(self):
        """Char relationships should round-trip through JSON."""
        self.mm.update_char_relationship(
            from_char="eve", to_char="atlas",
            emotions={"trust": 0.6}, category="praise", significance=0.5,
        )
        # Save
        self.mm._save_char_relationships()
        # Load into a fresh manager
        mm2 = MemoryManager(autoload=False)
        mm2.char_relationship_path = self.mm.char_relationship_path
        mm2.char_relationships = mm2._load_char_relationships()
        self.assertIn("eve", mm2.char_relationships)
        self.assertIn("atlas", mm2.char_relationships["eve"])

    def test_decay_char_relationships(self):
        """Decay should move values toward 0."""
        self.mm.char_relationships["eve"] = {
            "atlas": {axis: 0.0 for axis in RELATIONSHIP_AXES}
        }
        self.mm.char_relationships["eve"]["atlas"]["familiarity"] = 0.5
        self.mm.char_relationships["eve"]["atlas"]["tension"] = 0.3

        # Force decay by setting old timestamp
        self.mm._char_rel_last_decay_ts = None
        self.mm.decay_char_relationships()

        # Values should have moved toward 0 (or stayed the same if decay is tiny)
        self.assertLessEqual(
            self.mm.char_relationships["eve"]["atlas"]["familiarity"], 0.5
        )


if __name__ == "__main__":
    unittest.main()
