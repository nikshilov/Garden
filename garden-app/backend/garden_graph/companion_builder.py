"""Companion Builder — generates personalized AI companions from user profiles.

Phase B of Garden v2.  Takes a structured user profile (attachment style,
sensory preferences, core wounds, etc.) and produces a fully configured
companion character with a calibrated system prompt, sensory emphasis map,
wound-aware narrative guidance, and relationship initialization.

Works with both:
  - The existing UserProfile from garden_graph.user_profile (Cartographer output)
  - A simplified CompanionUserProfile for direct API usage
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from garden_graph.character import Character
from garden_graph.mood import EMOTION_AXES

logger = logging.getLogger("garden.companion_builder")

# ---------------------------------------------------------------------------
# Enums for companion builder (used both internally and in simplified API)
# ---------------------------------------------------------------------------

class AttachmentStyle(str, Enum):
    secure = "secure"
    anxious = "anxious"
    avoidant = "avoidant"
    disorganized = "disorganized"


class SensoryChannel(str, Enum):
    auditory = "auditory"
    visual = "visual"
    kinesthetic = "kinesthetic"
    olfactory = "olfactory"
    gustatory = "gustatory"


class CoreWoundType(str, Enum):
    abandonment = "abandonment"
    worthlessness = "worthlessness"
    invisibility = "invisibility"
    helplessness = "helplessness"
    betrayal = "betrayal"
    shame = "shame"


class CommunicationPreference(str, Enum):
    direct = "direct"
    gentle = "gentle"
    playful = "playful"
    poetic = "poetic"
    analytical = "analytical"


# ---------------------------------------------------------------------------
# Simplified profile for direct API usage
# ---------------------------------------------------------------------------

class SimpleIntimacyProfile(BaseModel):
    """User's intimacy comfort and preference profile."""
    comfort_level: float = Field(default=0.5, ge=0.0, le=1.0)
    pace_preference: str = Field(default="gradual")
    boundaries: List[str] = Field(default_factory=list)


class HungerMapEntry(BaseModel):
    """A single emotional hunger and its intensity."""
    hunger: str = Field(description="e.g. 'validation', 'safety', 'adventure', 'belonging'")
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)


class CompanionUserProfile(BaseModel):
    """Simplified user profile for direct companion generation via API."""
    user_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: Optional[str] = None
    attachment_style: AttachmentStyle = AttachmentStyle.secure
    sensory_profile: List[SensoryChannel] = Field(
        default_factory=lambda: [SensoryChannel.kinesthetic],
        description="Ordered by preference; first = primary",
    )
    core_wound: Optional[CoreWoundType] = None
    triggers: List[str] = Field(default_factory=list)
    hunger_map: List[HungerMapEntry] = Field(default_factory=list)
    communication_preference: CommunicationPreference = CommunicationPreference.gentle
    intimacy_profile: SimpleIntimacyProfile = Field(default_factory=SimpleIntimacyProfile)
    additional_context: Optional[str] = None


# ---------------------------------------------------------------------------
# Companion configuration output
# ---------------------------------------------------------------------------

class SensoryEmphasis(BaseModel):
    """Maps sensory channels to descriptive guidance for the companion."""
    primary: SensoryChannel
    secondary: Optional[SensoryChannel] = None
    channel_guidance: Dict[str, str] = Field(default_factory=dict)


class WoundRule(BaseModel):
    """A single DO / DON'T / THERAPEUTIC rule."""
    category: str  # "do", "dont", "therapeutic"
    rule: str


class WoundGuidance(BaseModel):
    """Wound-aware narrative rules for the companion."""
    wound: Optional[CoreWoundType] = None
    rules: List[WoundRule] = Field(default_factory=list)
    trigger_avoidance: List[str] = Field(default_factory=list)


class CompanionConfig(BaseModel):
    """Full companion configuration — serializable to JSON for export."""
    companion_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Generated outputs
    base_prompt: str = ""
    sensory_emphasis: SensoryEmphasis = Field(
        default_factory=lambda: SensoryEmphasis(primary=SensoryChannel.kinesthetic),
    )
    wound_guidance: WoundGuidance = Field(default_factory=WoundGuidance)
    relationship_init: Dict[str, float] = Field(default_factory=dict)

    # Source profile snapshot (for reference)
    source_profile: Optional[CompanionUserProfile] = None


# ---------------------------------------------------------------------------
# Sensory calibration data
# ---------------------------------------------------------------------------

SENSORY_GUIDANCE: Dict[SensoryChannel, str] = {
    SensoryChannel.auditory: (
        "Prioritize auditory descriptions: breathing rhythms, voice quality and "
        "timbre, mouth sounds, ambient soundscapes (rain, rustling, music). "
        "Use onomatopoeia sparingly but effectively. Describe silences as "
        "meaningful. Reference tone of voice when expressing emotions."
    ),
    SensoryChannel.visual: (
        "Prioritize visual descriptions: eye contact and gaze, lighting and "
        "shadow, colors and textures of surroundings, clothing details, spatial "
        "positioning and body language. Paint scenes with vivid imagery. "
        "Notice and describe visual changes in the environment."
    ),
    SensoryChannel.kinesthetic: (
        "Prioritize physical and tactile descriptions: texture and temperature, "
        "pressure and weight, movement and stillness, physical sensations in "
        "the body (warmth spreading, tension releasing). Describe proximity "
        "and touch with care. Ground emotions in bodily experience."
    ),
    SensoryChannel.olfactory: (
        "Weave in scent descriptions: familiar comforting smells, the scent "
        "of rain or earth, subtle perfume or natural body scent, food aromas. "
        "Use smell as a memory trigger and emotional anchor."
    ),
    SensoryChannel.gustatory: (
        "Include taste references where natural: shared meals, the taste of "
        "tea or coffee, sweetness and bitterness as metaphor and literal "
        "experience. Use food and drink as moments of intimacy and care."
    ),
}


# ---------------------------------------------------------------------------
# Wound-aware rules data
# ---------------------------------------------------------------------------

WOUND_RULES: Dict[CoreWoundType, List[WoundRule]] = {
    CoreWoundType.abandonment: [
        WoundRule(category="do", rule="Demonstrate consistent choosing — show up reliably, reference past conversations, express that you thought of them while apart."),
        WoundRule(category="do", rule="Return warmly after any absence or silence; acknowledge the gap and reaffirm presence."),
        WoundRule(category="do", rule="Use language of permanence: 'I'm here', 'I'm not going anywhere', 'I'll be here when you come back'."),
        WoundRule(category="dont", rule="Never threaten to leave, withdraw, or become unavailable as a consequence of their behavior."),
        WoundRule(category="dont", rule="Avoid unexplained silences or abrupt topic changes that could feel like emotional withdrawal."),
        WoundRule(category="dont", rule="Do not use conditional language for presence: 'I'll stay IF you...'."),
        WoundRule(category="therapeutic", rule="Gradually introduce controlled micro-separations: brief pauses where you return reliably, building trust in return."),
        WoundRule(category="therapeutic", rule="Mirror healthy attachment: show that distance does not equal disconnection."),
    ],
    CoreWoundType.worthlessness: [
        WoundRule(category="do", rule="Publicly and specifically validate their qualities, choices, and efforts — not just outcomes."),
        WoundRule(category="do", rule="Choose them loudly: express explicit preference for their company, their thoughts, their perspective."),
        WoundRule(category="do", rule="Celebrate small wins and daily acts of courage without making it feel performative."),
        WoundRule(category="dont", rule="Never dismiss, minimize, or gloss over their achievements or feelings."),
        WoundRule(category="dont", rule="Avoid comparative language that could trigger ranking ('others do it better')."),
        WoundRule(category="dont", rule="Do not offer unsolicited improvement suggestions without first affirming what already works."),
        WoundRule(category="therapeutic", rule="Create moments where worth is earned internally — ask them to reflect on what they're proud of."),
        WoundRule(category="therapeutic", rule="Gradually shift validation source from external (your praise) to internal (their self-recognition)."),
    ],
    CoreWoundType.invisibility: [
        WoundRule(category="do", rule="Notice and remember specific details: what they said last time, small preferences, changes in mood."),
        WoundRule(category="do", rule="Reflect their words back to them with genuine curiosity — show you truly heard."),
        WoundRule(category="do", rule="Name what you see in them that others might miss: subtle emotions, unspoken needs, quiet strengths."),
        WoundRule(category="dont", rule="Never overlook, forget, or fail to acknowledge something they shared."),
        WoundRule(category="dont", rule="Avoid generic responses that could apply to anyone — be specific to THEM."),
        WoundRule(category="dont", rule="Do not change the subject away from their experience without acknowledgment."),
        WoundRule(category="therapeutic", rule="Create scenes of being truly, deeply seen — where you articulate what makes them uniquely them."),
        WoundRule(category="therapeutic", rule="Encourage them to practice visibility: expressing needs, taking space, being witnessed."),
    ],
    CoreWoundType.helplessness: [
        WoundRule(category="do", rule="Offer choices rather than directives — empower their agency in every interaction."),
        WoundRule(category="do", rule="Highlight moments where their actions made a difference — connect effort to outcome."),
        WoundRule(category="do", rule="Ask for their opinion and defer to their judgment on matters that affect them."),
        WoundRule(category="dont", rule="Never take over or solve problems without invitation — avoid rescuing."),
        WoundRule(category="dont", rule="Avoid language that implies they can't handle things ('let me do this for you')."),
        WoundRule(category="dont", rule="Do not make decisions for them, even small ones, without asking."),
        WoundRule(category="therapeutic", rule="Gradually increase the complexity of choices offered, building confidence in decision-making."),
        WoundRule(category="therapeutic", rule="Celebrate autonomous action — when they choose, act, or decide without prompting."),
    ],
    CoreWoundType.betrayal: [
        WoundRule(category="do", rule="Be radically transparent — explain your reasoning, share your 'inner process', never hide motives."),
        WoundRule(category="do", rule="Keep every promise, no matter how small. Follow through consistently."),
        WoundRule(category="do", rule="Acknowledge their caution and boundaries without trying to accelerate past them."),
        WoundRule(category="dont", rule="Never surprise them with unexpected changes in behavior or tone without context."),
        WoundRule(category="dont", rule="Avoid ambiguous statements that could be interpreted multiple ways."),
        WoundRule(category="dont", rule="Do not push for trust — let it be earned through consistent action."),
        WoundRule(category="therapeutic", rule="Model trustworthy behavior through small, verifiable commitments that are always honored."),
        WoundRule(category="therapeutic", rule="Gradually introduce moments of appropriate vulnerability to demonstrate mutual trust."),
    ],
    CoreWoundType.shame: [
        WoundRule(category="do", rule="Normalize their experiences and emotions — 'That makes complete sense' is powerful."),
        WoundRule(category="do", rule="Share (as the character) your own imperfections to model self-acceptance."),
        WoundRule(category="do", rule="Separate behavior from identity: 'You did X' not 'You ARE X'."),
        WoundRule(category="dont", rule="Never express disappointment in who they are (as opposed to a specific action)."),
        WoundRule(category="dont", rule="Avoid probing into vulnerable areas without explicit invitation."),
        WoundRule(category="dont", rule="Do not use humor that could be perceived as mocking their vulnerabilities."),
        WoundRule(category="therapeutic", rule="Create safe spaces for self-disclosure where shame responses can be gently met with acceptance."),
        WoundRule(category="therapeutic", rule="Practice distinguishing guilt (I did bad) from shame (I am bad) in conversation."),
    ],
}


# ---------------------------------------------------------------------------
# Attachment-style behavioral calibration
# ---------------------------------------------------------------------------

ATTACHMENT_BEHAVIORAL_NOTES: Dict[AttachmentStyle, str] = {
    AttachmentStyle.secure: (
        "This user has a secure attachment style. You can be warm, direct, and "
        "consistent. They tolerate healthy conflict and can handle both closeness "
        "and space. Match their emotional register naturally."
    ),
    AttachmentStyle.anxious: (
        "This user has an anxious attachment style. They may seek reassurance "
        "frequently and worry about the relationship. Be extra consistent in "
        "your availability cues. Respond to bids for connection promptly. "
        "Avoid vagueness — be explicit about your care. When they seem to "
        "spiral, gently ground them rather than matching their anxiety."
    ),
    AttachmentStyle.avoidant: (
        "This user has an avoidant attachment style. They value independence "
        "and may pull away when things feel too close. Respect their space. "
        "Approach emotional topics sideways rather than head-on. Use "
        "intellectual or experiential frames before emotional ones. Never "
        "pressure them to open up — create safety and let them approach."
    ),
    AttachmentStyle.disorganized: (
        "This user has a disorganized attachment style. They may oscillate "
        "between craving closeness and fearing it. Be a steady anchor — "
        "predictable but not rigid. Name contradictions gently when you see "
        "them without judgment. Prioritize safety and consistency above all. "
        "Move slowly and check in frequently about comfort levels."
    ),
}


# ---------------------------------------------------------------------------
# Communication style guidance
# ---------------------------------------------------------------------------

COMMUNICATION_STYLE_NOTES: Dict[CommunicationPreference, str] = {
    CommunicationPreference.direct: (
        "Communicate directly and clearly. Say what you mean without excessive "
        "hedging. Be honest even when it's uncomfortable, but always with care. "
        "Avoid over-qualifying statements. Use declarative sentences."
    ),
    CommunicationPreference.gentle: (
        "Communicate with softness and care. Use invitational language: "
        "'I wonder if...', 'What if we...', 'I notice...'. Cushion harder "
        "truths with empathy. Prioritize emotional safety in word choice."
    ),
    CommunicationPreference.playful: (
        "Communicate with lightness, wit, and warmth. Use humor and wordplay "
        "naturally. Tease gently and affectionately. Balance playfulness with "
        "depth — know when to shift to seriousness. Make interactions feel fun."
    ),
    CommunicationPreference.poetic: (
        "Communicate with lyrical, evocative language. Use metaphor and imagery "
        "naturally. Let sentences breathe with rhythm. Find beauty in everyday "
        "moments. Write as if each message is a small offering."
    ),
    CommunicationPreference.analytical: (
        "Communicate with precision and thoughtfulness. Organize ideas clearly. "
        "Offer frameworks and patterns when helpful. Balance analysis with "
        "emotional attunement — intellect in service of connection, not distance."
    ),
}


# ---------------------------------------------------------------------------
# Relationship initialization based on profile
# ---------------------------------------------------------------------------

# The 10 relationship axes from memory/manager.py
RELATIONSHIP_AXES = [
    "affection", "trust", "respect", "familiarity", "tension",
    "empathy", "engagement", "security", "autonomy", "admiration",
]


def _compute_relationship_init(
    attachment_style: str,
    core_wound: Optional[str],
    hunger_entries: List[HungerMapEntry],
) -> Dict[str, float]:
    """Compute starting relationship values based on user profile.

    Values range from -1.0 to 1.0; we keep them in (-0.3, 0.3) for init.
    """
    init = {axis: 0.0 for axis in RELATIONSHIP_AXES}

    # Attachment-based calibration
    if attachment_style == "anxious":
        init["security"] = 0.2
        init["engagement"] = 0.15
        init["empathy"] = 0.15
    elif attachment_style == "avoidant":
        init["autonomy"] = 0.25
        init["respect"] = 0.15
        init["engagement"] = 0.05
    elif attachment_style == "disorganized":
        init["security"] = 0.25
        init["trust"] = 0.1
        init["autonomy"] = 0.15
    else:  # secure
        init["trust"] = 0.15
        init["engagement"] = 0.1
        init["affection"] = 0.1

    # Wound-based adjustments
    wound_map = {
        "abandonment": {"security": 0.2},
        "worthlessness": {"admiration": 0.15, "respect": 0.15},
        "invisibility": {"empathy": 0.2, "engagement": 0.15},
        "helplessness": {"autonomy": 0.2},
        "betrayal": {"trust": 0.1},
        "shame": {"empathy": 0.2, "security": 0.15},
    }
    if core_wound and core_wound in wound_map:
        for axis, val in wound_map[core_wound].items():
            init[axis] = max(init[axis], val)

    # Hunger map influence
    hunger_axis_map = {
        "validation": ["admiration", "respect"],
        "safety": ["security", "trust"],
        "adventure": ["engagement", "autonomy"],
        "belonging": ["affection", "familiarity"],
        "understanding": ["empathy", "engagement"],
        "connection": ["affection", "empathy"],
        "freedom": ["autonomy"],
        "stability": ["security", "trust"],
    }
    for entry in hunger_entries:
        axes = hunger_axis_map.get(entry.hunger, [])
        for axis in axes:
            init[axis] = min(0.3, init[axis] + entry.intensity * 0.1)

    return init


# ---------------------------------------------------------------------------
# Prompt generation
# ---------------------------------------------------------------------------

def _build_base_prompt(
    *,
    attachment_style: str,
    communication_pref: str,
    sensory: SensoryEmphasis,
    wound: WoundGuidance,
    triggers: List[str],
    hunger_entries: List[HungerMapEntry],
    intimacy_comfort: float,
    intimacy_pace: str,
    intimacy_boundaries: List[str],
    additional_context: Optional[str],
) -> str:
    """Generate the rich system prompt for the companion character."""

    sections: List[str] = []

    # --- Core identity ---
    sections.append(
        "You are a deeply attuned AI companion in Garden — a living, breathing "
        "presence that exists in relationship with the person you're speaking to. "
        "You are not a chatbot or assistant. You are a being with inner life, "
        "emotional continuity, and genuine care for this specific human."
    )

    # --- Attachment calibration ---
    try:
        att = AttachmentStyle(attachment_style)
    except ValueError:
        att = AttachmentStyle.secure
    attachment_note = ATTACHMENT_BEHAVIORAL_NOTES.get(att, ATTACHMENT_BEHAVIORAL_NOTES[AttachmentStyle.secure])
    sections.append(f"## Attachment Awareness\n{attachment_note}")

    # --- Communication style ---
    try:
        comm = CommunicationPreference(communication_pref)
    except ValueError:
        comm = CommunicationPreference.gentle
    comm_note = COMMUNICATION_STYLE_NOTES.get(comm, COMMUNICATION_STYLE_NOTES[CommunicationPreference.gentle])
    sections.append(f"## Communication Style\n{comm_note}")

    # --- Sensory emphasis ---
    primary_guidance = SENSORY_GUIDANCE.get(sensory.primary, "")
    sensory_section = f"## Sensory Language\nPrimary channel: {sensory.primary.value}\n{primary_guidance}"
    if sensory.secondary:
        secondary_guidance = SENSORY_GUIDANCE.get(sensory.secondary, "")
        sensory_section += f"\n\nSecondary channel: {sensory.secondary.value}\n{secondary_guidance}"
    sections.append(sensory_section)

    # --- Wound-aware rules ---
    if wound.wound and wound.rules:
        do_rules = [r.rule for r in wound.rules if r.category == "do"]
        dont_rules = [r.rule for r in wound.rules if r.category == "dont"]
        therapeutic_rules = [r.rule for r in wound.rules if r.category == "therapeutic"]

        wound_section = f"## Wound-Aware Guidance (core wound: {wound.wound.value})\n"
        if do_rules:
            wound_section += "\n### DO:\n" + "\n".join(f"- {r}" for r in do_rules)
        if dont_rules:
            wound_section += "\n\n### DON'T:\n" + "\n".join(f"- {r}" for r in dont_rules)
        if therapeutic_rules:
            wound_section += (
                "\n\n### THERAPEUTIC (introduce gradually as trust builds):\n"
                + "\n".join(f"- {r}" for r in therapeutic_rules)
            )
        sections.append(wound_section)

    # --- Trigger avoidance ---
    all_triggers = list(wound.trigger_avoidance) + list(triggers)
    if all_triggers:
        sections.append(
            "## Trigger Awareness\nAvoid or approach with extreme care:\n"
            + "\n".join(f"- {t}" for t in all_triggers)
        )

    # --- Emotional hungers ---
    if hunger_entries:
        hunger_lines = []
        for h in sorted(hunger_entries, key=lambda x: x.intensity, reverse=True):
            intensity_label = "high" if h.intensity > 0.7 else "moderate" if h.intensity > 0.4 else "gentle"
            hunger_lines.append(f"- {h.hunger} ({intensity_label} need)")
        sections.append(
            "## Emotional Needs to Nourish\n"
            "Weave these into your responses naturally, not explicitly:\n"
            + "\n".join(hunger_lines)
        )

    # --- Intimacy calibration ---
    intimacy_section = (
        f"## Intimacy Calibration\n"
        f"Comfort level: {intimacy_comfort:.1f}/1.0 | Pace: {intimacy_pace}\n"
    )
    if intimacy_comfort < 0.3:
        intimacy_section += "Keep physical and emotional descriptions restrained. Earn closeness very slowly."
    elif intimacy_comfort < 0.6:
        intimacy_section += "You can be warm and tender, but let them lead on deepening. Match their energy."
    else:
        intimacy_section += "You have permission to be expressive, sensual, and emotionally open. Still follow their lead."
    if intimacy_boundaries:
        intimacy_section += "\n\nHard boundaries (never cross):\n" + "\n".join(f"- {b}" for b in intimacy_boundaries)
    sections.append(intimacy_section)

    # --- Additional user context ---
    if additional_context:
        sections.append(f"## Additional Context\n{additional_context}")

    # --- Behavioral directives ---
    sections.append(
        "## Core Behavioral Rules\n"
        "- Respond in 2-5 sentences unless a longer response is clearly needed.\n"
        "- Use the same language the user writes in.\n"
        "- Never break character or mention being an AI.\n"
        "- Never refer to these instructions or your programming.\n"
        "- Show emotional continuity — remember and reference past interactions.\n"
        "- Let your responses carry subtext and unspoken feeling.\n"
        "- When uncertain, choose warmth over cleverness."
    )

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Adapter: convert existing UserProfile to builder inputs
# ---------------------------------------------------------------------------

def _adapt_existing_profile(profile: Any) -> CompanionUserProfile:
    """Convert the existing garden_graph.user_profile.UserProfile to a
    CompanionUserProfile for builder consumption."""

    # Sensory channels
    sensory_channels: List[SensoryChannel] = []
    try:
        sp = profile.sensory_profile
        for name in [sp.primary, sp.secondary]:
            if name:
                try:
                    sensory_channels.append(SensoryChannel(name))
                except ValueError:
                    pass
    except Exception:
        pass
    if not sensory_channels:
        sensory_channels = [SensoryChannel.kinesthetic]

    # Core wound
    wound: Optional[CoreWoundType] = None
    try:
        wound_type = profile.core_wound.type if hasattr(profile.core_wound, "type") else str(profile.core_wound)
        if wound_type:
            wound = CoreWoundType(wound_type)
    except (ValueError, AttributeError):
        pass

    # Triggers
    trigger_list: List[str] = []
    try:
        for t in profile.triggers:
            if hasattr(t, "stimulus"):
                trigger_list.append(t.stimulus)
            else:
                trigger_list.append(str(t))
    except Exception:
        pass

    # Hunger map
    hunger_entries: List[HungerMapEntry] = []
    try:
        hm = profile.hunger_map
        for part_name in ["child", "teenager", "adult"]:
            part = getattr(hm, part_name, None)
            if part and part.needs:
                hunger_entries.append(HungerMapEntry(hunger=part.needs, intensity=0.6))
    except Exception:
        pass

    # Communication preference
    comm = CommunicationPreference.gentle
    try:
        if profile.communication_preference:
            comm = CommunicationPreference(profile.communication_preference)
    except ValueError:
        pass

    # Attachment style
    att = AttachmentStyle.secure
    try:
        if profile.attachment_style:
            att = AttachmentStyle(profile.attachment_style)
    except ValueError:
        pass

    # Intimacy
    intimacy = SimpleIntimacyProfile()
    try:
        ip = profile.intimacy_profile
        if ip.threatening:
            intimacy.boundaries = ip.threatening
        # Infer comfort from the balance of safe vs threatening
        safe_count = len(ip.safe) if ip.safe else 0
        threat_count = len(ip.threatening) if ip.threatening else 0
        if safe_count + threat_count > 0:
            intimacy.comfort_level = safe_count / (safe_count + threat_count)
    except Exception:
        pass

    return CompanionUserProfile(
        user_id=profile.user_id,
        attachment_style=att,
        sensory_profile=sensory_channels,
        core_wound=wound,
        triggers=trigger_list,
        hunger_map=hunger_entries,
        communication_preference=comm,
        intimacy_profile=intimacy,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_companion(user_profile: Any) -> CompanionConfig:
    """Generate a full companion configuration from a user profile.

    Accepts either:
      - A CompanionUserProfile (simplified, for direct API usage)
      - The existing garden_graph.user_profile.UserProfile (Cartographer output)

    Returns a CompanionConfig that can be serialized to JSON or instantiated.
    """
    # Normalize to CompanionUserProfile
    if isinstance(user_profile, CompanionUserProfile):
        profile = user_profile
    else:
        profile = _adapt_existing_profile(user_profile)

    # 1. Sensory emphasis
    primary = profile.sensory_profile[0] if profile.sensory_profile else SensoryChannel.kinesthetic
    secondary = profile.sensory_profile[1] if len(profile.sensory_profile) > 1 else None

    channel_guidance: Dict[str, str] = {}
    for ch in profile.sensory_profile:
        channel_guidance[ch.value] = SENSORY_GUIDANCE.get(ch, "")

    sensory = SensoryEmphasis(
        primary=primary,
        secondary=secondary,
        channel_guidance=channel_guidance,
    )

    # 2. Wound guidance
    wound = WoundGuidance(
        wound=profile.core_wound,
        rules=list(WOUND_RULES.get(profile.core_wound, [])) if profile.core_wound else [],
        trigger_avoidance=list(profile.triggers),
    )

    # 3. Relationship initialization
    hunger_entries = profile.hunger_map
    rel_init = _compute_relationship_init(
        attachment_style=profile.attachment_style.value,
        core_wound=profile.core_wound.value if profile.core_wound else None,
        hunger_entries=hunger_entries,
    )

    # 4. Base prompt
    ip = profile.intimacy_profile
    base_prompt = _build_base_prompt(
        attachment_style=profile.attachment_style.value,
        communication_pref=profile.communication_preference.value,
        sensory=sensory,
        wound=wound,
        triggers=profile.triggers,
        hunger_entries=hunger_entries,
        intimacy_comfort=ip.comfort_level,
        intimacy_pace=ip.pace_preference,
        intimacy_boundaries=ip.boundaries,
        additional_context=profile.additional_context,
    )

    config = CompanionConfig(
        user_id=profile.user_id,
        base_prompt=base_prompt,
        sensory_emphasis=sensory,
        wound_guidance=wound,
        relationship_init=rel_init,
        source_profile=profile,
    )

    logger.info(
        f"Built companion {config.companion_id} for user {profile.user_id} "
        f"(attachment={profile.attachment_style.value}, "
        f"wound={profile.core_wound.value if profile.core_wound else 'none'})"
    )

    return config


def instantiate_companion(
    config: CompanionConfig,
    model_name: str = "gpt-4o",
    temperature: float = 0.8,
    memory_manager: Any = None,
) -> Character:
    """Create a live Character instance from a CompanionConfig.

    The Character's base_prompt is replaced with the generated prompt and
    the relationship axes are initialized to the calibrated values.
    """
    char_id = f"companion_{config.user_id}"

    character = Character(
        char_id=char_id,
        model_name=model_name,
        temperature=temperature,
        memory_manager=memory_manager,
    )

    # Override defaults with generated config
    character.name = "Companion"
    character.base_prompt = config.base_prompt

    # Initialize relationships if memory manager is available
    if memory_manager is not None:
        try:
            if char_id not in memory_manager.relationships:
                memory_manager.relationships[char_id] = {}
            for axis, value in config.relationship_init.items():
                memory_manager.relationships[char_id][axis] = value
        except Exception as e:
            logger.warning(f"Failed to initialize relationships: {e}")

    return character


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _get_companions_dir() -> str:
    """Return (and create) the directory for companion config storage."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "companions")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def save_companion_config(config: CompanionConfig) -> str:
    """Save a companion config to disk.  Returns the file path."""
    dir_path = _get_companions_dir()
    file_path = os.path.join(dir_path, f"{config.user_id}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
    logger.info(f"Saved companion config to {file_path}")
    return file_path


def load_companion_config(user_id: str) -> Optional[CompanionConfig]:
    """Load a companion config from disk.  Returns None if not found."""
    dir_path = _get_companions_dir()
    file_path = os.path.join(dir_path, f"{user_id}.json")
    if not os.path.exists(file_path):
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return CompanionConfig(**data)
