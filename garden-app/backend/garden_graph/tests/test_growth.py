"""Tests for Phase 4: Growth — Identity Evolution."""
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock


class TestIdentityManager(unittest.TestCase):
    """Test the identity and trait tracking system."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def _get_manager(self):
        from garden_graph.identity import IdentityManager
        return IdentityManager(self.tmpdir)

    def test_get_or_create_defaults(self):
        mgr = self._get_manager()
        identity = mgr.get_or_create("eve")
        self.assertEqual(identity.char_id, "eve")
        self.assertEqual(identity.conversation_count, 0)
        # Default traits should be around 0.5
        for trait, val in identity.traits.items():
            self.assertAlmostEqual(val, 0.5, places=1)

    def test_get_or_create_idempotent(self):
        mgr = self._get_manager()
        a = mgr.get_or_create("eve")
        b = mgr.get_or_create("eve")
        self.assertIs(a, b)

    def test_update_traits(self):
        mgr = self._get_manager()
        mgr.get_or_create("eve")
        mgr.update_traits("eve", {"warmth": 0.1, "openness": -0.05})
        identity = mgr.get_or_create("eve")
        self.assertGreater(identity.traits["warmth"], 0.5)
        self.assertLess(identity.traits["openness"], 0.5)

    def test_traits_clamped(self):
        mgr = self._get_manager()
        mgr.get_or_create("eve")
        mgr.update_traits("eve", {"warmth": 10.0})
        identity = mgr.get_or_create("eve")
        self.assertLessEqual(identity.traits["warmth"], 1.0)

        mgr.update_traits("eve", {"warmth": -20.0})
        self.assertGreaterEqual(identity.traits["warmth"], 0.0)

    def test_record_growth(self):
        mgr = self._get_manager()
        mgr.get_or_create("eve")
        mgr.record_growth(
            "eve",
            "I've learned to be more patient with others.",
            {"warmth": 0.02, "resilience": 0.01},
        )
        identity = mgr.get_or_create("eve")
        self.assertEqual(len(identity.growth_memories), 1)
        self.assertIn("patient", identity.growth_memories[0].text)

    def test_check_milestone_first_time(self):
        mgr = self._get_manager()
        mgr.get_or_create("eve")
        ms = mgr.check_milestone("eve", "first_conversation", "First chat!")
        self.assertIsNotNone(ms)
        self.assertEqual(ms.milestone_type, "first_conversation")

    def test_check_milestone_no_duplicate(self):
        mgr = self._get_manager()
        mgr.get_or_create("eve")
        ms1 = mgr.check_milestone("eve", "first_conversation", "First chat!")
        ms2 = mgr.check_milestone("eve", "first_conversation", "First chat again?")
        self.assertIsNotNone(ms1)
        self.assertIsNone(ms2)

    def test_increment_conversation(self):
        mgr = self._get_manager()
        mgr.get_or_create("eve")
        mgr.increment_conversation("eve")
        mgr.increment_conversation("eve")
        identity = mgr.get_or_create("eve")
        self.assertEqual(identity.conversation_count, 2)

    def test_identity_prompt_segment_default(self):
        """New character with default traits should have minimal prompt."""
        mgr = self._get_manager()
        mgr.get_or_create("eve")
        segment = mgr.identity_prompt_segment("eve")
        # Default traits are all 0.5 — nothing notable to mention
        # Should either be empty or very minimal
        self.assertNotIn("notably", segment.lower() if segment else "")

    def test_identity_prompt_with_evolved_traits(self):
        """Character with shifted traits should have descriptive prompt."""
        mgr = self._get_manager()
        mgr.get_or_create("eve")
        mgr.update_traits("eve", {"warmth": 0.35, "introspection": 0.25})
        segment = mgr.identity_prompt_segment("eve")
        self.assertTrue(len(segment) > 0)

    def test_save_and_load(self):
        mgr = self._get_manager()
        mgr.get_or_create("eve")
        mgr.update_traits("eve", {"warmth": 0.2})
        mgr.record_growth("eve", "I grew", {"warmth": 0.02})
        mgr.check_milestone("eve", "first_conversation", "Hello!")
        mgr.save("eve")

        # Load into fresh manager
        mgr2 = self._get_manager()
        mgr2.load("eve")
        identity = mgr2.get_or_create("eve")
        self.assertGreater(identity.traits["warmth"], 0.5)
        self.assertEqual(len(identity.growth_memories), 1)
        self.assertEqual(len(identity.milestones), 1)


class TestReflectionUpgrade(unittest.TestCase):
    """Test the upgraded reflection system with growth narratives."""

    def test_maybe_reflect_without_llm(self):
        """Without LLM, reflection should still work (simple concatenation)."""
        from garden_graph.memory.reflection import ReflectionManager
        from pathlib import Path
        import tempfile

        tmpdir = Path(tempfile.mkdtemp())
        mgr = ReflectionManager(tmpdir)
        mgr.load("eve")

        # Mock memories
        mock_mems = []
        for i in range(5):
            m = MagicMock()
            m.id = f"mem_{i}"
            m.event_text = f"Memory event {i}"
            mock_mems.append(m)

        # Pump counter past threshold
        for _ in range(ReflectionManager.REFLECTION_THRESHOLD):
            mgr.on_new_memory("eve")

        result = mgr.maybe_reflect("eve", mock_mems, llm=None)
        self.assertIsNotNone(result)
        self.assertIn("Memory event", result.summary)

    def test_all_reflections(self):
        """all_reflections should return the full list."""
        from garden_graph.memory.reflection import ReflectionManager, ReflectionRecord
        from pathlib import Path
        import tempfile

        tmpdir = Path(tempfile.mkdtemp())
        mgr = ReflectionManager(tmpdir)
        mgr._reflections["eve"] = [
            ReflectionRecord.create(["m1"], "summary 1"),
            ReflectionRecord.create(["m2"], "summary 2"),
        ]
        result = mgr.all_reflections("eve")
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
