"""Tests for autonomous inter-character conversations."""
import asyncio
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

from garden_graph.heartbeat import Heartbeat


class _FakePresence:
    """Lightweight stand-in for CharacterPresence."""
    def __init__(self, char_id, location, energy=0.7):
        self.char_id = char_id
        self.location = location
        self.energy = energy
        self.activity = "sitting"


class _FakeLLMResponse:
    def __init__(self, text):
        self.content = text


class TestGroupByLocation(unittest.TestCase):
    """Characters are grouped by location before pairing."""

    def setUp(self):
        self.mm = MagicMock()
        self.mm.char_relationships = {}
        self.mm.process_cross_talk = MagicMock(return_value={})
        self.mm.char_relationship_context = MagicMock(return_value="")
        self.hb = Heartbeat(character_ids=["eve", "atlas", "adam"], memory_manager=self.mm)

    def test_no_conversations_when_alone(self):
        """Characters at different locations should not converse."""
        presences = [
            _FakePresence("eve", "rose_garden"),
            _FakePresence("atlas", "library"),
            _FakePresence("adam", "stream"),
        ]
        gw = MagicMock()
        gw.get_all_presences.return_value = presences
        gw.character_context.return_value = ""
        self.hb._garden_world = gw

        loop = asyncio.new_event_loop()
        try:
            # Force _should_converse to always True — still no conversations
            # because nobody is co-located
            self.hb._should_converse = MagicMock(return_value=True)
            loop.run_until_complete(self.hb._autonomous_conversations(datetime.now(timezone.utc)))
            self.hb._should_converse.assert_not_called()
        finally:
            loop.close()

    def test_colocated_pair_is_evaluated(self):
        """Two characters at the same location should be evaluated."""
        presences = [
            _FakePresence("eve", "library"),
            _FakePresence("atlas", "library"),
            _FakePresence("adam", "stream"),
        ]
        gw = MagicMock()
        gw.get_all_presences.return_value = presences
        gw.character_context.return_value = ""
        self.hb._garden_world = gw

        # Force no conversation to avoid LLM call
        self.hb._should_converse = MagicMock(return_value=False)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self.hb._autonomous_conversations(datetime.now(timezone.utc)))
            self.hb._should_converse.assert_called_once()
            args = self.hb._should_converse.call_args[0]
            ids = {args[0].char_id, args[1].char_id}
            assert ids == {"eve", "atlas"}
        finally:
            loop.close()


class TestShouldConverse(unittest.TestCase):
    """Probability logic for starting a conversation."""

    def setUp(self):
        self.mm = MagicMock()
        self.mm.char_relationships = {}
        self.hb = Heartbeat(character_ids=["eve", "atlas"], memory_manager=self.mm)

    def test_low_energy_reduces_probability(self):
        """Characters with low energy should converse less often."""
        a = _FakePresence("eve", "library", energy=0.2)
        b = _FakePresence("atlas", "library", energy=0.2)

        # Run many trials
        count = sum(1 for _ in range(1000) if self.hb._should_converse(a, b))
        # With avg energy 0.2, prob ≈ 0.30 * 0.3 = 0.09, clamped to 0.09
        assert count < 200, f"Low energy should reduce conversations, got {count}/1000"

    def test_high_relationship_boosts_probability(self):
        """Strong relationship should increase conversation chance."""
        self.mm.char_relationships = {
            "eve": {"atlas": {"familiarity": 0.6, "affection": 0.5}},
            "atlas": {"eve": {"familiarity": 0.6, "affection": 0.5}},
        }
        a = _FakePresence("eve", "library", energy=0.8)
        b = _FakePresence("atlas", "library", energy=0.8)

        count = sum(1 for _ in range(1000) if self.hb._should_converse(a, b))
        # prob ≈ 0.30 + 0.15 + 0.10 = 0.55
        assert count > 350, f"Strong relationship should boost conversations, got {count}/1000"

    def test_probability_clamped(self):
        """Probability should stay within [0.05, 0.70]."""
        # Even with maximally strong relationship + full energy,
        # should not exceed 70%
        self.mm.char_relationships = {
            "eve": {"atlas": {"familiarity": 1.0, "affection": 1.0}},
            "atlas": {"eve": {"familiarity": 1.0, "affection": 1.0}},
        }
        a = _FakePresence("eve", "library", energy=1.0)
        b = _FakePresence("atlas", "library", energy=1.0)

        count = sum(1 for _ in range(2000) if self.hb._should_converse(a, b))
        rate = count / 2000
        assert rate <= 0.80, f"Rate {rate:.2f} exceeds plausible clamp"
        assert rate >= 0.05, f"Rate {rate:.2f} below minimum clamp"


class TestOneConversationPerCharacter(unittest.TestCase):
    """Each character should talk at most once per tick."""

    def setUp(self):
        self.mm = MagicMock()
        self.mm.char_relationships = {}
        self.mm.process_cross_talk = MagicMock(return_value={})
        self.mm.char_relationship_context = MagicMock(return_value="")
        self.hb = Heartbeat(
            character_ids=["eve", "atlas", "adam"],
            memory_manager=self.mm,
        )

    def test_character_talks_at_most_once(self):
        """If three characters are co-located, at most one pair converses."""
        presences = [
            _FakePresence("eve", "library"),
            _FakePresence("atlas", "library"),
            _FakePresence("adam", "library"),
        ]
        gw = MagicMock()
        gw.get_all_presences.return_value = presences
        gw.character_context.return_value = ""
        self.hb._garden_world = gw

        # Force all conversations to happen
        self.hb._should_converse = MagicMock(return_value=True)
        self.hb._generate_conversation = AsyncMock()

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self.hb._autonomous_conversations(datetime.now(timezone.utc)))
            # Only 1 conversation should have been generated (first pair wins)
            assert self.hb._generate_conversation.call_count == 1
        finally:
            loop.close()


class TestGenerateConversation(unittest.TestCase):
    """Test the LLM-backed conversation generation."""

    def setUp(self):
        self.mm = MagicMock()
        self.mm.char_relationships = {}
        self.mm.process_cross_talk = MagicMock(return_value={})
        self.mm.char_relationship_context = MagicMock(return_value="")
        self.hb = Heartbeat(
            character_ids=["eve", "atlas"],
            memory_manager=self.mm,
        )
        self.hb.episodic_store = MagicMock()

    @patch("garden_graph.heartbeat.Heartbeat._get_llm")
    def test_generates_and_stores(self, mock_get_llm):
        """Should call LLM, store cross_talk, and create episodic memories."""
        fake_llm = MagicMock()
        fake_llm.invoke.side_effect = [
            _FakeLLMResponse("The light here is beautiful today."),
            _FakeLLMResponse("It really is. I was just thinking the same."),
        ]
        mock_get_llm.return_value = fake_llm

        a = _FakePresence("eve", "library")
        b = _FakePresence("atlas", "library")

        gw = MagicMock()
        gw.character_context.return_value = ""
        self.hb._garden_world = gw

        loop = asyncio.new_event_loop()
        try:
            with patch("garden_graph.heartbeat.random") as mock_random:
                mock_random.random.return_value = 0.6  # no third message
                loop.run_until_complete(
                    self.hb._generate_conversation(a, b, "library", datetime.now(timezone.utc))
                )
        finally:
            loop.close()

        # LLM called twice (A opens, B responds)
        assert fake_llm.invoke.call_count == 2

        # Cross-talk stored for both directions
        assert self.mm.process_cross_talk.call_count == 2

        # Episodic memories created for both characters
        assert self.hb.episodic_store.add.call_count == 2

    @patch("garden_graph.heartbeat.Heartbeat._get_llm")
    def test_third_message_on_coin_flip(self, mock_get_llm):
        """50% chance of a third message from A."""
        fake_llm = MagicMock()
        fake_llm.invoke.side_effect = [
            _FakeLLMResponse("Look at that bird."),
            _FakeLLMResponse("Oh, I see it!"),
            _FakeLLMResponse("A robin, I think."),
        ]
        mock_get_llm.return_value = fake_llm

        a = _FakePresence("eve", "stream")
        b = _FakePresence("atlas", "stream")

        gw = MagicMock()
        gw.character_context.return_value = ""
        self.hb._garden_world = gw

        loop = asyncio.new_event_loop()
        try:
            with patch("garden_graph.heartbeat.random") as mock_random:
                mock_random.random.return_value = 0.3  # < 0.5, trigger third msg
                loop.run_until_complete(
                    self.hb._generate_conversation(a, b, "stream", datetime.now(timezone.utc))
                )
        finally:
            loop.close()

        # LLM called 3 times
        assert fake_llm.invoke.call_count == 3

        # 2 cross-talk + 4 episodic (2 initial + 2 continuation)
        assert self.hb.episodic_store.add.call_count == 4


class TestNoConversationWithoutDeps(unittest.TestCase):
    """Conversations require both garden_world and memory_manager."""

    def test_no_garden_world(self):
        hb = Heartbeat(character_ids=["eve"], memory_manager=MagicMock())
        hb._garden_world = None

        loop = asyncio.new_event_loop()
        try:
            # Should exit early, no error
            loop.run_until_complete(hb._autonomous_conversations(datetime.now(timezone.utc)))
        finally:
            loop.close()

    def test_no_memory_manager(self):
        hb = Heartbeat(character_ids=["eve"], memory_manager=None)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(hb._autonomous_conversations(datetime.now(timezone.utc)))
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
