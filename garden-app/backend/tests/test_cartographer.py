"""Tests for the Cartographer onboarding agent.

These tests mock the LLM to avoid real API calls while verifying
session flow, stage advancement, and profile extraction logic.
"""
import json
from unittest import mock

import pytest

from garden_graph.cartographer import (
    STAGES,
    MIN_MESSAGES_PER_STAGE,
    CartographerSession,
    _parse_profile_json,
)
from garden_graph.user_profile import UserProfile, save_profile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeLLMResponse:
    """Mimics the object returned by llm.invoke()."""

    def __init__(self, content: str):
        self.content = content


def _make_fake_llm(responses=None):
    """Return a mock LLM that returns pre-canned responses in sequence."""
    if responses is None:
        responses = ["Cartographer response."]
    call_count = {"n": 0}

    def _invoke(messages):
        idx = min(call_count["n"], len(responses) - 1)
        call_count["n"] += 1
        return FakeLLMResponse(responses[idx])

    llm = mock.MagicMock()
    llm.invoke = _invoke
    return llm


SAMPLE_PROFILE_JSON = json.dumps({
    "attachment_style": "anxious-preoccupied",
    "sensory_profile": {
        "primary": "auditory",
        "secondary": "kinesthetic",
        "details": {
            "auditory": {"triggers": ["whisper"], "weight": 0.8},
            "kinesthetic": {"triggers": ["warmth"], "weight": 0.6},
            "visual": {"triggers": [], "weight": 0.3},
        },
    },
    "core_wound": {
        "type": "worthlessness",
        "narrative": "Needs to be chosen.",
        "origin_hints": ["betrayal"],
    },
    "triggers": [
        {"stimulus": "phone_during_talk", "reaction": "invisible", "intensity": 0.9},
    ],
    "hunger_map": {
        "child": {"needs": "safety", "feeds_on": "whispers"},
        "teenager": {"needs": "validation", "feeds_on": "being_chosen"},
        "adult": {"needs": "partnership", "feeds_on": "respect"},
    },
    "communication_preference": "direct_honest",
    "intimacy_profile": {
        "safe": ["slow_morning"],
        "exciting": ["teasing"],
        "threatening": ["silence"],
    },
})


# ---------------------------------------------------------------------------
# Session lifecycle tests
# ---------------------------------------------------------------------------


class TestCartographerSession:
    def test_initial_state(self):
        with mock.patch("garden_graph.cartographer.get_llm", return_value=_make_fake_llm()):
            session = CartographerSession(user_id="u1")
            assert session.current_stage == "warm_up"
            assert session.is_complete is False
            assert session.messages == []

    def test_get_first_message(self):
        fake_llm = _make_fake_llm(["Welcome to the garden."])
        with mock.patch("garden_graph.cartographer.get_llm", return_value=fake_llm):
            session = CartographerSession(user_id="u1")
            msg = session.get_first_message()
            assert msg == "Welcome to the garden."
            assert len(session.messages) == 1
            assert session.messages[0]["role"] == "assistant"

    def test_process_message_records_and_responds(self):
        fake_llm = _make_fake_llm(["Reply 1", "Reply 2"])
        with mock.patch("garden_graph.cartographer.get_llm", return_value=fake_llm):
            session = CartographerSession(user_id="u1")
            reply = session.process_message("Hello")
            assert reply == "Reply 1"
            assert len(session.messages) == 2  # user + assistant
            assert session.messages[0]["role"] == "user"
            assert session.messages[1]["role"] == "assistant"

    def test_stage_advancement(self):
        """After MIN_MESSAGES_PER_STAGE user messages the stage should advance."""
        responses = [f"Response {i}" for i in range(20)]
        fake_llm = _make_fake_llm(responses)

        with mock.patch("garden_graph.cartographer.get_llm", return_value=fake_llm):
            session = CartographerSession(user_id="u1")
            assert session.current_stage == "warm_up"

            # Send MIN_MESSAGES_PER_STAGE messages
            for i in range(MIN_MESSAGES_PER_STAGE):
                session.process_message(f"Message {i}")

            # Should have advanced past warm_up
            assert session.current_stage == "sensory_exploration"

    def test_all_stages_reachable(self):
        """Send enough messages to reach every stage including summary."""
        responses = [f"R{i}" for i in range(50)]
        fake_llm = _make_fake_llm(responses)

        with mock.patch("garden_graph.cartographer.get_llm", return_value=fake_llm):
            session = CartographerSession(user_id="u1")

            visited_stages = {session.current_stage}
            for i in range(len(STAGES) * MIN_MESSAGES_PER_STAGE + 5):
                session.process_message(f"msg {i}")
                visited_stages.add(session.current_stage)

            # All stages should have been visited (some may have been skipped
            # to 'complete' but the named stages should appear)
            for stage in STAGES:
                assert stage in visited_stages, f"Stage {stage} was never reached"

    def test_complete_session_returns_fixed_message(self):
        """Once all stages are done, process_message returns a fixed farewell."""
        responses = [f"R{i}" for i in range(50)]
        fake_llm = _make_fake_llm(responses)

        with mock.patch("garden_graph.cartographer.get_llm", return_value=fake_llm):
            session = CartographerSession(user_id="u1")

            # Fast-forward past all stages
            for i in range(len(STAGES) * MIN_MESSAGES_PER_STAGE + 5):
                session.process_message(f"msg {i}")

            # Force completion
            session.stage_index = len(STAGES)
            assert session.is_complete

            reply = session.process_message("One more thing")
            assert "finished" in reply.lower() or "profile" in reply.lower()

    def test_to_dict(self):
        fake_llm = _make_fake_llm()
        with mock.patch("garden_graph.cartographer.get_llm", return_value=fake_llm):
            session = CartographerSession(user_id="u1")
            d = session.to_dict()
            assert d["user_id"] == "u1"
            assert d["current_stage"] == "warm_up"
            assert d["is_complete"] is False


# ---------------------------------------------------------------------------
# Profile extraction tests
# ---------------------------------------------------------------------------


class TestProfileExtraction:
    def test_extract_profile_parses_json(self):
        """extract_profile should parse LLM JSON into a UserProfile."""
        fake_llm = _make_fake_llm([SAMPLE_PROFILE_JSON])
        with mock.patch("garden_graph.cartographer.get_llm", return_value=fake_llm):
            session = CartographerSession(user_id="extract-user")
            # Add some conversation history (required for extraction prompt)
            session.messages = [
                {"role": "assistant", "content": "Welcome."},
                {"role": "user", "content": "I feel unseen most of the time."},
                {"role": "assistant", "content": "Tell me more about that."},
                {"role": "user", "content": "It started in childhood."},
            ]

            profile = session.extract_profile()
            assert isinstance(profile, UserProfile)
            assert profile.user_id == "extract-user"
            assert profile.attachment_style == "anxious-preoccupied"
            assert profile.sensory_profile.primary == "auditory"
            assert profile.core_wound.type == "worthlessness"
            assert len(profile.triggers) == 1
            assert profile.triggers[0].intensity == 0.9
            assert profile.hunger_map.child.needs == "safety"
            assert profile.intimacy_profile.safe == ["slow_morning"]

    def test_extract_profile_handles_fenced_json(self):
        """LLMs sometimes wrap JSON in ```json ... ``` fences."""
        fenced = f"```json\n{SAMPLE_PROFILE_JSON}\n```"
        fake_llm = _make_fake_llm([fenced])

        with mock.patch("garden_graph.cartographer.get_llm", return_value=fake_llm):
            session = CartographerSession(user_id="fenced-user")
            session.messages = [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
            ]
            profile = session.extract_profile()
            assert profile.attachment_style == "anxious-preoccupied"

    def test_extract_profile_handles_bad_json(self):
        """If the LLM returns invalid JSON, we get an empty/default profile."""
        fake_llm = _make_fake_llm(["this is not json at all"])

        with mock.patch("garden_graph.cartographer.get_llm", return_value=fake_llm):
            session = CartographerSession(user_id="bad-json-user")
            session.messages = [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
            ]
            profile = session.extract_profile()
            # Should still return a valid profile with defaults
            assert isinstance(profile, UserProfile)
            assert profile.user_id == "bad-json-user"
            assert profile.attachment_style == ""


# ---------------------------------------------------------------------------
# JSON parser helper tests
# ---------------------------------------------------------------------------


class TestParseProfileJson:
    def test_plain_json(self):
        result = _parse_profile_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_fenced_json(self):
        result = _parse_profile_json('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_fenced_no_language(self):
        result = _parse_profile_json('```\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_invalid_json(self):
        result = _parse_profile_json("not json")
        assert result == {}

    def test_empty_string(self):
        result = _parse_profile_json("")
        assert result == {}


# ---------------------------------------------------------------------------
# API endpoint tests (integration with server.py)
# ---------------------------------------------------------------------------


class TestOnboardingEndpoints:
    """Test the onboarding API endpoints via FastAPI TestClient."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        """Import TestClient only when running these tests."""
        from fastapi.testclient import TestClient
        from server import app, _onboarding_sessions
        self.client = TestClient(app)
        self._onboarding_sessions = _onboarding_sessions
        # Clean up sessions before each test
        _onboarding_sessions.clear()

    @mock.patch("garden_graph.cartographer.get_llm")
    def test_start_onboarding(self, mock_get_llm):
        mock_get_llm.return_value = _make_fake_llm(["Welcome!"])
        resp = self.client.post("/onboarding/start", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert "user_id" in data
        assert data["message"] == "Welcome!"
        assert data["stage"] == "warm_up"

    @mock.patch("garden_graph.cartographer.get_llm")
    def test_send_message(self, mock_get_llm):
        mock_get_llm.return_value = _make_fake_llm(["Welcome!", "Tell me more."])

        # Start session
        start = self.client.post("/onboarding/start", json={}).json()
        sid = start["session_id"]

        # Send message
        resp = self.client.post("/onboarding/message", json={
            "session_id": sid,
            "text": "I feel most alive near water.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "Tell me more."
        assert "stage" in data

    def test_message_unknown_session(self):
        resp = self.client.post("/onboarding/message", json={
            "session_id": "nonexistent",
            "text": "hello",
        })
        assert resp.status_code == 404

    def test_message_empty_text(self):
        # Need a valid session first
        with mock.patch("garden_graph.cartographer.get_llm", return_value=_make_fake_llm(["Hi"])):
            start = self.client.post("/onboarding/start", json={}).json()
            sid = start["session_id"]

        resp = self.client.post("/onboarding/message", json={
            "session_id": sid,
            "text": "  ",
        })
        assert resp.status_code == 400

    @mock.patch("garden_graph.cartographer.get_llm")
    def test_complete_onboarding(self, mock_get_llm, tmp_path):
        mock_get_llm.return_value = _make_fake_llm(["Welcome!", "Great.", SAMPLE_PROFILE_JSON])

        with mock.patch("garden_graph.user_profile._profiles_dir", return_value=str(tmp_path)):
            start = self.client.post("/onboarding/start", json={"user_id": "complete-user"}).json()
            sid = start["session_id"]

            # Send a message so there's conversation history
            self.client.post("/onboarding/message", json={"session_id": sid, "text": "I'm here"})

            # Complete
            resp = self.client.post("/onboarding/complete", json={"session_id": sid})
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is True
            assert data["user_id"] == "complete-user"
            assert "profile" in data

            # Session should be cleaned up
            assert sid not in self._onboarding_sessions

    def test_complete_unknown_session(self):
        resp = self.client.post("/onboarding/complete", json={"session_id": "ghost"})
        assert resp.status_code == 404


class TestProfileEndpoints:
    """Test the profile CRUD endpoints."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        from fastapi.testclient import TestClient
        from server import app
        self.client = TestClient(app)
        self._tmp_path = tmp_path
        self._patcher = mock.patch(
            "garden_graph.user_profile._profiles_dir", return_value=str(tmp_path)
        )
        self._patcher.start()

    @pytest.fixture(autouse=True)
    def _teardown(self):
        yield
        self._patcher.stop()

    def test_get_profile_not_found(self):
        resp = self.client.get("/profile/no-such-user")
        assert resp.status_code == 404

    def test_get_profile(self):
        from garden_graph.user_profile import UserProfile, save_profile
        profile = UserProfile(user_id="get-user", attachment_style="secure")
        save_profile(profile)

        resp = self.client.get("/profile/get-user")
        assert resp.status_code == 200
        assert resp.json()["profile"]["attachment_style"] == "secure"

    def test_put_profile(self):
        from garden_graph.user_profile import UserProfile, save_profile
        profile = UserProfile(user_id="put-user", attachment_style="anxious")
        save_profile(profile)

        resp = self.client.put("/profile/put-user", json={
            "attachment_style": "secure",
        })
        assert resp.status_code == 200
        assert resp.json()["profile"]["attachment_style"] == "secure"
        assert resp.json()["profile"]["version"] == 2

    def test_put_profile_not_found(self):
        resp = self.client.put("/profile/ghost-user", json={
            "attachment_style": "secure",
        })
        assert resp.status_code == 404

    def test_put_profile_no_updates(self):
        from garden_graph.user_profile import UserProfile, save_profile
        save_profile(UserProfile(user_id="empty-put"))

        resp = self.client.put("/profile/empty-put", json={})
        assert resp.status_code == 400
