"""Tests for user_profile module — schema, persistence, and updates."""
import json
import os
import tempfile
from unittest import mock

import pytest

from garden_graph.user_profile import (
    CoreWound,
    HungerMap,
    HungerPart,
    IntimacyProfile,
    SensoryDetail,
    SensoryProfile,
    Trigger,
    UserProfile,
    load_profile,
    save_profile,
    update_profile,
    _profiles_dir,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sample_profile(user_id: str = "test-user-1") -> UserProfile:
    """Build a minimal but complete sample profile."""
    return UserProfile(
        user_id=user_id,
        version=1,
        attachment_style="anxious-preoccupied",
        sensory_profile=SensoryProfile(
            primary="auditory",
            secondary="kinesthetic",
            details={
                "auditory": SensoryDetail(triggers=["whisper", "breathing"], weight=0.8),
                "kinesthetic": SensoryDetail(triggers=["warm_skin"], weight=0.6),
                "visual": SensoryDetail(triggers=["eye_contact"], weight=0.3),
            },
        ),
        core_wound=CoreWound(
            type="worthlessness",
            narrative="Needs proof of being chosen.",
            origin_hints=["early_relationship_betrayal"],
        ),
        triggers=[
            Trigger(stimulus="phone_during_conversation", reaction="invisible", intensity=0.9),
        ],
        hunger_map=HungerMap(
            child=HungerPart(needs="safety", feeds_on="whispers"),
            teenager=HungerPart(needs="validation", feeds_on="being_chosen"),
            adult=HungerPart(needs="partnership", feeds_on="mutual_respect"),
        ),
        communication_preference="direct_honest",
        intimacy_profile=IntimacyProfile(
            safe=["slow_morning_intimacy"],
            exciting=["public_displays"],
            threatening=["silence_after_sex"],
        ),
    )


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestUserProfileSchema:
    def test_create_minimal_profile(self):
        profile = UserProfile(user_id="u1")
        assert profile.user_id == "u1"
        assert profile.version == 1
        assert profile.created_at  # auto-generated

    def test_create_full_profile(self):
        profile = _sample_profile()
        assert profile.attachment_style == "anxious-preoccupied"
        assert profile.sensory_profile.primary == "auditory"
        assert len(profile.triggers) == 1
        assert profile.triggers[0].intensity == 0.9
        assert profile.hunger_map.child.needs == "safety"
        assert profile.intimacy_profile.safe == ["slow_morning_intimacy"]

    def test_profile_serialization_roundtrip(self):
        profile = _sample_profile()
        data = profile.model_dump()
        restored = UserProfile(**data)
        assert restored.user_id == profile.user_id
        assert restored.attachment_style == profile.attachment_style
        assert restored.sensory_profile.primary == profile.sensory_profile.primary
        assert len(restored.triggers) == len(profile.triggers)

    def test_profile_json_roundtrip(self):
        profile = _sample_profile()
        json_str = json.dumps(profile.model_dump())
        data = json.loads(json_str)
        restored = UserProfile(**data)
        assert restored.user_id == profile.user_id

    def test_default_values(self):
        profile = UserProfile(user_id="u2")
        assert profile.attachment_style == ""
        assert profile.sensory_profile.primary == "kinesthetic"
        assert profile.core_wound.type == ""
        assert profile.triggers == []
        assert profile.hunger_map.child.needs == ""
        assert profile.intimacy_profile.safe == []

    def test_sensory_detail_defaults(self):
        detail = SensoryDetail()
        assert detail.triggers == []
        assert detail.weight == 0.5

    def test_trigger_defaults(self):
        t = Trigger(stimulus="loud_noise")
        assert t.reaction == ""
        assert t.intensity == 0.5


# ---------------------------------------------------------------------------
# Persistence tests
# ---------------------------------------------------------------------------


class TestUserProfilePersistence:
    def test_save_and_load(self, tmp_path):
        """save_profile writes a JSON file that load_profile can read back."""
        profile = _sample_profile("persist-user")

        with mock.patch("garden_graph.user_profile._profiles_dir", return_value=str(tmp_path)):
            save_profile(profile)

            # File should exist
            path = tmp_path / "persist-user.json"
            assert path.exists()

            # Load it back
            loaded = load_profile("persist-user")
            assert loaded is not None
            assert loaded.user_id == "persist-user"
            assert loaded.attachment_style == "anxious-preoccupied"
            assert loaded.sensory_profile.primary == "auditory"

    def test_load_nonexistent(self, tmp_path):
        with mock.patch("garden_graph.user_profile._profiles_dir", return_value=str(tmp_path)):
            result = load_profile("does-not-exist")
            assert result is None

    def test_update_profile(self, tmp_path):
        profile = _sample_profile("update-user")

        with mock.patch("garden_graph.user_profile._profiles_dir", return_value=str(tmp_path)):
            save_profile(profile)

            updated = update_profile("update-user", {"attachment_style": "secure"})
            assert updated is not None
            assert updated.attachment_style == "secure"
            assert updated.version == 2  # bumped

            # Verify persistence
            reloaded = load_profile("update-user")
            assert reloaded.attachment_style == "secure"
            assert reloaded.version == 2

    def test_update_nonexistent(self, tmp_path):
        with mock.patch("garden_graph.user_profile._profiles_dir", return_value=str(tmp_path)):
            result = update_profile("ghost", {"attachment_style": "secure"})
            assert result is None

    def test_save_creates_directory(self, tmp_path):
        nested = tmp_path / "sub" / "profiles"
        profile = UserProfile(user_id="dir-test")

        def _fake_profiles_dir():
            os.makedirs(str(nested), exist_ok=True)
            return str(nested)

        with mock.patch("garden_graph.user_profile._profiles_dir", side_effect=_fake_profiles_dir):
            save_profile(profile)
            assert (nested / "dir-test.json").exists()

    def test_update_bumps_version_incrementally(self, tmp_path):
        profile = _sample_profile("ver-user")
        profile.version = 5

        with mock.patch("garden_graph.user_profile._profiles_dir", return_value=str(tmp_path)):
            save_profile(profile)
            updated = update_profile("ver-user", {"communication_preference": "gentle"})
            assert updated.version == 6
