"""Tests for the Companion Builder (Phase B)."""
import json
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from garden_graph.companion_builder import (
    AttachmentStyle,
    SensoryChannel,
    CoreWoundType,
    CommunicationPreference,
    CompanionUserProfile,
    CompanionConfig,
    HungerMapEntry,
    SimpleIntimacyProfile,
    SensoryEmphasis,
    WoundGuidance,
    WoundRule,
    build_companion,
    instantiate_companion,
    save_companion_config,
    load_companion_config,
    _compute_relationship_init,
    _adapt_existing_profile,
    RELATIONSHIP_AXES,
    WOUND_RULES,
    SENSORY_GUIDANCE,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def basic_profile() -> CompanionUserProfile:
    return CompanionUserProfile(
        user_id="test-user-001",
        name="TestUser",
        attachment_style=AttachmentStyle.secure,
        sensory_profile=[SensoryChannel.kinesthetic, SensoryChannel.auditory],
        core_wound=None,
        triggers=[],
        hunger_map=[],
        communication_preference=CommunicationPreference.gentle,
    )


@pytest.fixture()
def anxious_abandonment_profile() -> CompanionUserProfile:
    return CompanionUserProfile(
        user_id="test-user-002",
        name="AnxiousUser",
        attachment_style=AttachmentStyle.anxious,
        sensory_profile=[SensoryChannel.auditory, SensoryChannel.visual],
        core_wound=CoreWoundType.abandonment,
        triggers=["sudden silence", "being left on read"],
        hunger_map=[
            HungerMapEntry(hunger="safety", intensity=0.9),
            HungerMapEntry(hunger="validation", intensity=0.7),
        ],
        communication_preference=CommunicationPreference.gentle,
        intimacy_profile=SimpleIntimacyProfile(
            comfort_level=0.4,
            pace_preference="slow",
            boundaries=["no sudden physical descriptions"],
        ),
    )


@pytest.fixture()
def avoidant_shame_profile() -> CompanionUserProfile:
    return CompanionUserProfile(
        user_id="test-user-003",
        attachment_style=AttachmentStyle.avoidant,
        sensory_profile=[SensoryChannel.visual],
        core_wound=CoreWoundType.shame,
        triggers=["judgment", "being put on the spot"],
        hunger_map=[
            HungerMapEntry(hunger="freedom", intensity=0.8),
        ],
        communication_preference=CommunicationPreference.analytical,
    )


@pytest.fixture()
def tmp_data_dir(tmp_path):
    """Override the companions data directory to a temp location."""
    companions_dir = tmp_path / "companions"
    companions_dir.mkdir()
    with patch("garden_graph.companion_builder._get_companions_dir", return_value=str(companions_dir)):
        yield companions_dir


# ---------------------------------------------------------------------------
# build_companion tests
# ---------------------------------------------------------------------------

class TestBuildCompanion:
    def test_returns_companion_config(self, basic_profile):
        config = build_companion(basic_profile)
        assert isinstance(config, CompanionConfig)
        assert config.user_id == "test-user-001"
        assert config.companion_id  # non-empty UUID
        assert config.created_at

    def test_base_prompt_is_nonempty(self, basic_profile):
        config = build_companion(basic_profile)
        assert len(config.base_prompt) > 200  # should be a rich prompt

    def test_base_prompt_contains_core_identity(self, basic_profile):
        config = build_companion(basic_profile)
        assert "companion" in config.base_prompt.lower() or "Garden" in config.base_prompt

    def test_base_prompt_contains_attachment_note(self, anxious_abandonment_profile):
        config = build_companion(anxious_abandonment_profile)
        assert "anxious" in config.base_prompt.lower()
        assert "reassurance" in config.base_prompt.lower()

    def test_base_prompt_contains_communication_style(self, basic_profile):
        config = build_companion(basic_profile)
        # gentle style
        assert "softness" in config.base_prompt.lower() or "care" in config.base_prompt.lower()

    def test_base_prompt_contains_sensory_guidance(self, basic_profile):
        config = build_companion(basic_profile)
        # kinesthetic is primary
        assert "texture" in config.base_prompt.lower() or "temperature" in config.base_prompt.lower()

    def test_base_prompt_contains_wound_rules(self, anxious_abandonment_profile):
        config = build_companion(anxious_abandonment_profile)
        # abandonment wound rules
        assert "consistent choosing" in config.base_prompt.lower() or "permanence" in config.base_prompt.lower()
        assert "DON'T" in config.base_prompt or "don't" in config.base_prompt.lower()

    def test_base_prompt_contains_triggers(self, anxious_abandonment_profile):
        config = build_companion(anxious_abandonment_profile)
        assert "sudden silence" in config.base_prompt
        assert "being left on read" in config.base_prompt

    def test_base_prompt_contains_hunger_map(self, anxious_abandonment_profile):
        config = build_companion(anxious_abandonment_profile)
        assert "safety" in config.base_prompt.lower()
        assert "validation" in config.base_prompt.lower()

    def test_base_prompt_contains_intimacy_calibration(self, anxious_abandonment_profile):
        config = build_companion(anxious_abandonment_profile)
        assert "intimacy" in config.base_prompt.lower() or "comfort" in config.base_prompt.lower()
        assert "no sudden physical descriptions" in config.base_prompt

    def test_base_prompt_contains_behavioral_rules(self, basic_profile):
        config = build_companion(basic_profile)
        assert "Never break character" in config.base_prompt

    def test_analytical_communication_style(self, avoidant_shame_profile):
        config = build_companion(avoidant_shame_profile)
        assert "precision" in config.base_prompt.lower() or "frameworks" in config.base_prompt.lower()

    def test_sensory_emphasis_structure(self, basic_profile):
        config = build_companion(basic_profile)
        se = config.sensory_emphasis
        assert se.primary == SensoryChannel.kinesthetic
        assert se.secondary == SensoryChannel.auditory
        assert "kinesthetic" in se.channel_guidance
        assert "auditory" in se.channel_guidance

    def test_sensory_emphasis_single_channel(self):
        profile = CompanionUserProfile(
            user_id="single-sense",
            sensory_profile=[SensoryChannel.visual],
        )
        config = build_companion(profile)
        assert config.sensory_emphasis.primary == SensoryChannel.visual
        assert config.sensory_emphasis.secondary is None

    def test_wound_guidance_structure(self, anxious_abandonment_profile):
        config = build_companion(anxious_abandonment_profile)
        wg = config.wound_guidance
        assert wg.wound == CoreWoundType.abandonment
        assert len(wg.rules) > 0
        categories = {r.category for r in wg.rules}
        assert "do" in categories
        assert "dont" in categories
        assert "therapeutic" in categories
        assert "sudden silence" in wg.trigger_avoidance

    def test_wound_guidance_none_wound(self, basic_profile):
        config = build_companion(basic_profile)
        assert config.wound_guidance.wound is None
        assert config.wound_guidance.rules == []

    def test_config_serializable_to_json(self, anxious_abandonment_profile):
        config = build_companion(anxious_abandonment_profile)
        json_str = json.dumps(config.model_dump(mode="json"))
        assert json_str  # no serialization error
        parsed = json.loads(json_str)
        assert parsed["user_id"] == "test-user-002"


# ---------------------------------------------------------------------------
# Relationship initialization tests
# ---------------------------------------------------------------------------

class TestRelationshipInit:
    def test_all_axes_present(self, basic_profile):
        config = build_companion(basic_profile)
        for axis in RELATIONSHIP_AXES:
            assert axis in config.relationship_init

    def test_secure_baseline(self):
        init = _compute_relationship_init("secure", None, [])
        assert init["trust"] > 0
        assert init["engagement"] > 0
        assert init["affection"] > 0

    def test_anxious_higher_security(self):
        init = _compute_relationship_init("anxious", None, [])
        secure_init = _compute_relationship_init("secure", None, [])
        assert init["security"] > secure_init["security"]
        assert init["empathy"] > secure_init.get("empathy", 0)

    def test_avoidant_higher_autonomy(self):
        init = _compute_relationship_init("avoidant", None, [])
        assert init["autonomy"] > 0.2

    def test_disorganized_safety_focused(self):
        init = _compute_relationship_init("disorganized", None, [])
        assert init["security"] >= 0.25

    def test_abandonment_wound_boosts_security(self):
        init = _compute_relationship_init("secure", "abandonment", [])
        baseline = _compute_relationship_init("secure", None, [])
        assert init["security"] >= baseline["security"]

    def test_worthlessness_wound_boosts_admiration(self):
        init = _compute_relationship_init("secure", "worthlessness", [])
        assert init["admiration"] >= 0.15

    def test_hunger_map_influences_axes(self):
        hungers = [HungerMapEntry(hunger="safety", intensity=1.0)]
        init = _compute_relationship_init("secure", None, hungers)
        baseline = _compute_relationship_init("secure", None, [])
        assert init["security"] > baseline["security"]

    def test_values_within_bounds(self):
        hungers = [
            HungerMapEntry(hunger="safety", intensity=1.0),
            HungerMapEntry(hunger="belonging", intensity=1.0),
            HungerMapEntry(hunger="validation", intensity=1.0),
        ]
        init = _compute_relationship_init("anxious", "abandonment", hungers)
        for axis, val in init.items():
            assert -0.5 <= val <= 0.5, f"{axis}={val} out of expected range"


# ---------------------------------------------------------------------------
# instantiate_companion tests
# ---------------------------------------------------------------------------

class TestInstantiateCompanion:
    def test_creates_character(self, basic_profile):
        config = build_companion(basic_profile)
        character = instantiate_companion(config)
        assert character.name == "Companion"
        assert character.id == f"companion_{basic_profile.user_id}"
        assert character.base_prompt == config.base_prompt

    def test_initializes_relationships_with_memory_manager(self, basic_profile):
        config = build_companion(basic_profile)
        mm = MagicMock()
        mm.relationships = {}
        character = instantiate_companion(config, memory_manager=mm)
        char_id = f"companion_{basic_profile.user_id}"
        assert char_id in mm.relationships
        for axis in RELATIONSHIP_AXES:
            assert axis in mm.relationships[char_id]


# ---------------------------------------------------------------------------
# Persistence tests
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_save_and_load(self, basic_profile, tmp_data_dir):
        config = build_companion(basic_profile)
        save_companion_config(config)
        loaded = load_companion_config(basic_profile.user_id)
        assert loaded is not None
        assert loaded.companion_id == config.companion_id
        assert loaded.user_id == config.user_id
        assert loaded.base_prompt == config.base_prompt

    def test_load_nonexistent(self, tmp_data_dir):
        result = load_companion_config("nonexistent-user")
        assert result is None


# ---------------------------------------------------------------------------
# Adapter tests (existing UserProfile -> CompanionUserProfile)
# ---------------------------------------------------------------------------

class TestAdaptExistingProfile:
    def test_adapts_basic_profile(self):
        """Test adapting the existing user_profile.UserProfile format."""
        from garden_graph.user_profile import UserProfile, SensoryProfile, CoreWound

        existing = UserProfile(
            user_id="adapt-test-001",
            attachment_style="anxious",
            sensory_profile=SensoryProfile(primary="visual", secondary="auditory"),
            core_wound=CoreWound(type="abandonment", narrative="Early loss"),
            communication_preference="poetic",
        )
        adapted = _adapt_existing_profile(existing)
        assert adapted.user_id == "adapt-test-001"
        assert adapted.attachment_style == AttachmentStyle.anxious
        assert adapted.sensory_profile[0] == SensoryChannel.visual
        assert adapted.sensory_profile[1] == SensoryChannel.auditory
        assert adapted.core_wound == CoreWoundType.abandonment
        assert adapted.communication_preference == CommunicationPreference.poetic

    def test_build_from_existing_profile(self):
        """build_companion should accept the existing UserProfile transparently."""
        from garden_graph.user_profile import UserProfile, SensoryProfile

        existing = UserProfile(
            user_id="adapt-test-002",
            attachment_style="avoidant",
            sensory_profile=SensoryProfile(primary="kinesthetic", secondary="olfactory"),
            communication_preference="analytical",
        )
        config = build_companion(existing)
        assert isinstance(config, CompanionConfig)
        assert config.user_id == "adapt-test-002"
        assert "avoidant" in config.base_prompt.lower()

    def test_handles_empty_fields_gracefully(self):
        from garden_graph.user_profile import UserProfile

        existing = UserProfile(user_id="adapt-test-003")
        adapted = _adapt_existing_profile(existing)
        assert adapted.attachment_style == AttachmentStyle.secure
        assert len(adapted.sensory_profile) >= 1


# ---------------------------------------------------------------------------
# Wound rules coverage
# ---------------------------------------------------------------------------

class TestWoundRules:
    def test_all_wound_types_have_rules(self):
        for wound_type in CoreWoundType:
            assert wound_type in WOUND_RULES
            rules = WOUND_RULES[wound_type]
            assert len(rules) >= 4  # at least a few DO/DON'T/THERAPEUTIC

    def test_all_wound_rules_have_categories(self):
        for wound_type, rules in WOUND_RULES.items():
            categories = {r.category for r in rules}
            assert "do" in categories, f"{wound_type} missing 'do' rules"
            assert "dont" in categories, f"{wound_type} missing 'dont' rules"
            assert "therapeutic" in categories, f"{wound_type} missing 'therapeutic' rules"


# ---------------------------------------------------------------------------
# Sensory guidance coverage
# ---------------------------------------------------------------------------

class TestSensoryGuidance:
    def test_all_channels_have_guidance(self):
        for channel in SensoryChannel:
            assert channel in SENSORY_GUIDANCE
            assert len(SENSORY_GUIDANCE[channel]) > 50  # meaningful guidance text
