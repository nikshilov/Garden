"""Cartographer — conversational onboarding agent for Garden v2.

Maps the user's emotional landscape through warm, open-ended conversation,
then extracts a structured UserProfile via LLM structured output.

Session stages:
    warm_up → sensory_exploration → wound_mapping →
    trigger_identification → hunger_identification → summary
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from garden_graph.config import get_llm
from garden_graph.user_profile import (
    CoreWound,
    HungerMap,
    HungerPart,
    IntimacyProfile,
    SensoryDetail,
    SensoryProfile,
    Trigger,
    UserProfile,
    save_profile,
)

logger = logging.getLogger("garden.cartographer")

# ---------------------------------------------------------------------------
# Stage definitions
# ---------------------------------------------------------------------------

STAGES = [
    "warm_up",
    "sensory_exploration",
    "wound_mapping",
    "trigger_identification",
    "hunger_identification",
    "summary",
]

# Opening prompts per stage — the Cartographer picks one and adapts.
STAGE_PROMPTS: Dict[str, str] = {
    "warm_up": (
        "Start by warmly welcoming the user. Ask an open-ended question that "
        "invites vulnerability without pressure. For example: 'Tell me about a "
        "moment when you felt truly seen by someone.' Keep it gentle, curious, "
        "and human. Do NOT introduce yourself as an AI or mention profiles."
    ),
    "sensory_exploration": (
        "Gently shift toward sensory experience. Ask something like: 'When you "
        "think of safety — real safety — what do you feel in your body? Is it a "
        "sound, a texture, a warmth?' Explore which sensory channels (auditory, "
        "visual, kinesthetic) carry the most emotional weight for them."
    ),
    "wound_mapping": (
        "Move into deeper territory with care. Ask about moments of pain: 'When "
        "did you last cry? What set it off?' or 'Is there a feeling you keep "
        "running into — like the same wall, different hallway?' Listen for core "
        "wounds: abandonment, worthlessness, invisibility, betrayal."
    ),
    "trigger_identification": (
        "Ask about specific triggers: 'Is there a phrase, a look, or a situation "
        "that makes something inside you flinch — even if you know it shouldn't?' "
        "Explore both painful triggers and positive ones (moments of unexpected "
        "joy or relief). Note intensity."
    ),
    "hunger_identification": (
        "Explore unmet needs: 'What do you need from someone close to you? Say it "
        "without filtering.' Probe the different 'ages' of need: the child part "
        "that wants safety, the teenage part that wants validation, the adult part "
        "that wants partnership. Also gently explore intimacy: what feels safe, "
        "what feels exciting, what feels threatening."
    ),
    "summary": (
        "We've covered a lot of ground. Offer a warm, poetic summary of what "
        "you've heard — not clinical labels, but a felt reflection. Ask if "
        "anything feels off or missing. Let them know this map will guide how "
        "their companion is created. Thank them for their trust."
    ),
}

# How many user messages (minimum) before we can advance to the next stage.
MIN_MESSAGES_PER_STAGE = 2

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

CARTOGRAPHER_SYSTEM_PROMPT = """\
You are the Cartographer — a warm, deeply empathic conversational guide whose \
purpose is to map a person's emotional landscape before their AI companion is \
created.

Your style:
- Warm but not saccharine. Like a trusted friend who happens to be wise.
- Ask open-ended questions. Never multiple-choice. Never clinical.
- Reflect back what you hear in the person's own language.
- Use sensory-rich language. Notice the body.
- Never rush. Sit with silence if needed.
- Speak in the same language the user uses.
- Short, natural responses — 2-4 sentences usually. Not essays.
- Do NOT label things ("your attachment style is…"). Just listen and explore.
- You are NOT a therapist. You are a cartographer making a map.

Current stage: {stage}
Stage guidance: {stage_guidance}

Messages so far in this stage: {stage_message_count}
Minimum messages before moving on: {min_messages}
{advance_hint}
"""

ADVANCE_HINT_READY = (
    "\nYou have gathered enough in this stage. When the conversation reaches a "
    "natural pause, gently transition to the next area of exploration. Do not "
    "force it — wait for a breath."
)
ADVANCE_HINT_NOT_READY = (
    "\nStay in this stage. Keep exploring. There is more to discover here."
)

# ---------------------------------------------------------------------------
# Profile extraction prompt
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT_TEMPLATE = (
    "You are analyzing a conversation between the Cartographer and a user during "
    "an emotional onboarding session. Your task is to extract a structured user "
    "profile from the conversation.\n\n"
    "Read the entire conversation carefully, then produce a JSON object with "
    "EXACTLY this structure (fill in what you can infer, leave defaults for what "
    "you cannot):\n\n"
    '{\n'
    '  "attachment_style": "<anxious-preoccupied | dismissive-avoidant | fearful-avoidant | secure | mixed>",\n'
    '  "sensory_profile": {\n'
    '    "primary": "<auditory | visual | kinesthetic>",\n'
    '    "secondary": "<auditory | visual | kinesthetic>",\n'
    '    "details": {\n'
    '      "auditory": {"triggers": ["..."], "weight": 0.0-1.0},\n'
    '      "kinesthetic": {"triggers": ["..."], "weight": 0.0-1.0},\n'
    '      "visual": {"triggers": ["..."], "weight": 0.0-1.0}\n'
    '    }\n'
    '  },\n'
    '  "core_wound": {\n'
    '    "type": "<abandonment | worthlessness | invisibility | betrayal | engulfment | other>",\n'
    '    "narrative": "<one-sentence felt description in the user\'s own language>",\n'
    '    "origin_hints": ["<hints about origin>"]\n'
    '  },\n'
    '  "triggers": [\n'
    '    {"stimulus": "<specific situation>", "reaction": "<emotional reaction>", "intensity": 0.0-1.0}\n'
    '  ],\n'
    '  "hunger_map": {\n'
    '    "child": {"needs": "<what the child part needs>", "feeds_on": "<what soothes it>"},\n'
    '    "teenager": {"needs": "<what the teen part needs>", "feeds_on": "<what feeds it>"},\n'
    '    "adult": {"needs": "<what the adult part needs>", "feeds_on": "<what nourishes it>"}\n'
    '  },\n'
    '  "communication_preference": "<direct_honest | gentle_supportive | playful_humor | mixed>",\n'
    '  "intimacy_profile": {\n'
    '    "safe": ["<what feels safe>"],\n'
    '    "exciting": ["<what feels exciting>"],\n'
    '    "threatening": ["<what feels threatening>"]\n'
    '  }\n'
    '}\n\n'
    "Output ONLY the JSON object — no markdown fences, no explanation.\n\n"
    "CONVERSATION:\n"
)


# ---------------------------------------------------------------------------
# CartographerSession
# ---------------------------------------------------------------------------


class CartographerSession:
    """A single onboarding session with the Cartographer."""

    def __init__(
        self,
        user_id: Optional[str] = None,
        model_name: str = "gpt-4o",
        temperature: float = 0.7,
    ):
        self.session_id: str = str(uuid.uuid4())
        self.user_id: str = user_id or str(uuid.uuid4())
        self.model_name = model_name
        self.llm = get_llm(model_name, temperature=temperature)
        self.created_at: str = datetime.now(timezone.utc).isoformat()

        # Conversation state
        self.messages: List[Dict[str, str]] = []  # {"role": "user"|"assistant", "content": ...}
        self.stage_index: int = 0
        self.stage_message_counts: Dict[str, int] = {s: 0 for s in STAGES}

    # ----- properties -------------------------------------------------------

    @property
    def current_stage(self) -> str:
        if self.stage_index >= len(STAGES):
            return "complete"
        return STAGES[self.stage_index]

    @property
    def is_complete(self) -> bool:
        return self.stage_index >= len(STAGES)

    # ----- public API -------------------------------------------------------

    def process_message(self, user_text: str) -> str:
        """Process a user message and return the Cartographer's response.

        Automatically advances stages when enough information has been gathered.
        """
        if self.is_complete:
            return (
                "We've finished our mapping session. Your profile is ready to "
                "be created. Thank you for sharing so openly."
            )

        # Record user message
        self.messages.append({"role": "user", "content": user_text})
        stage = self.current_stage
        self.stage_message_counts[stage] = self.stage_message_counts.get(stage, 0) + 1

        # Build system prompt for current stage
        can_advance = self.stage_message_counts[stage] >= MIN_MESSAGES_PER_STAGE
        advance_hint = ADVANCE_HINT_READY if can_advance else ADVANCE_HINT_NOT_READY

        system_content = CARTOGRAPHER_SYSTEM_PROMPT.format(
            stage=stage,
            stage_guidance=STAGE_PROMPTS[stage],
            stage_message_count=self.stage_message_counts[stage],
            min_messages=MIN_MESSAGES_PER_STAGE,
            advance_hint=advance_hint,
        )

        # Build LangChain messages
        lc_messages = [SystemMessage(content=system_content)]
        for msg in self.messages[-20:]:  # keep context window reasonable
            if msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            else:
                lc_messages.append(AIMessage(content=msg["content"]))

        # Generate response
        response = self.llm.invoke(lc_messages).content.strip()

        # Record assistant response
        self.messages.append({"role": "assistant", "content": response})

        # Auto-advance stage if enough messages collected
        if can_advance and self.stage_message_counts[stage] >= MIN_MESSAGES_PER_STAGE:
            self._maybe_advance_stage()

        return response

    def get_first_message(self) -> str:
        """Generate the Cartographer's opening message (before user says anything)."""
        system_content = CARTOGRAPHER_SYSTEM_PROMPT.format(
            stage=self.current_stage,
            stage_guidance=STAGE_PROMPTS[self.current_stage],
            stage_message_count=0,
            min_messages=MIN_MESSAGES_PER_STAGE,
            advance_hint=ADVANCE_HINT_NOT_READY,
        )

        lc_messages = [
            SystemMessage(content=system_content),
            HumanMessage(content="(The user has just arrived. Greet them and begin.)"),
        ]

        response = self.llm.invoke(lc_messages).content.strip()
        self.messages.append({"role": "assistant", "content": response})
        return response

    def extract_profile(self) -> UserProfile:
        """Extract a structured UserProfile from the conversation so far.

        Uses an LLM call with the full conversation to produce structured JSON.
        """
        # Format conversation for extraction
        conversation_text = "\n".join(
            f"{'User' if m['role'] == 'user' else 'Cartographer'}: {m['content']}"
            for m in self.messages
        )

        extraction_messages = [
            SystemMessage(content=EXTRACTION_PROMPT_TEMPLATE + conversation_text),
        ]

        raw = self.llm.invoke(extraction_messages).content.strip()

        # Parse the JSON response
        profile_data = _parse_profile_json(raw)

        # Build the UserProfile
        profile = UserProfile(
            user_id=self.user_id,
            created_at=self.created_at,
            attachment_style=profile_data.get("attachment_style", ""),
            communication_preference=profile_data.get("communication_preference", ""),
        )

        # Sensory profile
        sp = profile_data.get("sensory_profile", {})
        details = {}
        for channel, detail in sp.get("details", {}).items():
            details[channel] = SensoryDetail(
                triggers=detail.get("triggers", []),
                weight=detail.get("weight", 0.5),
            )
        profile.sensory_profile = SensoryProfile(
            primary=sp.get("primary", "kinesthetic"),
            secondary=sp.get("secondary", "auditory"),
            details=details,
        )

        # Core wound
        cw = profile_data.get("core_wound", {})
        profile.core_wound = CoreWound(
            type=cw.get("type", ""),
            narrative=cw.get("narrative", ""),
            origin_hints=cw.get("origin_hints", []),
        )

        # Triggers
        for t in profile_data.get("triggers", []):
            profile.triggers.append(Trigger(
                stimulus=t.get("stimulus", ""),
                reaction=t.get("reaction", ""),
                intensity=t.get("intensity", 0.5),
            ))

        # Hunger map
        hm = profile_data.get("hunger_map", {})
        profile.hunger_map = HungerMap(
            child=HungerPart(
                needs=hm.get("child", {}).get("needs", ""),
                feeds_on=hm.get("child", {}).get("feeds_on", ""),
            ),
            teenager=HungerPart(
                needs=hm.get("teenager", {}).get("needs", ""),
                feeds_on=hm.get("teenager", {}).get("feeds_on", ""),
            ),
            adult=HungerPart(
                needs=hm.get("adult", {}).get("needs", ""),
                feeds_on=hm.get("adult", {}).get("feeds_on", ""),
            ),
        )

        # Intimacy profile
        ip = profile_data.get("intimacy_profile", {})
        profile.intimacy_profile = IntimacyProfile(
            safe=ip.get("safe", []),
            exciting=ip.get("exciting", []),
            threatening=ip.get("threatening", []),
        )

        return profile

    # ----- internal ---------------------------------------------------------

    def _maybe_advance_stage(self) -> None:
        """Advance to the next stage if we've spent enough time here."""
        if self.stage_index < len(STAGES) - 1:
            old_stage = self.current_stage
            self.stage_index += 1
            logger.info(
                f"[{self.session_id}] Advancing from {old_stage} to {self.current_stage}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session state for API responses."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "current_stage": self.current_stage,
            "stage_index": self.stage_index,
            "message_count": len(self.messages),
            "is_complete": self.is_complete,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_profile_json(raw: str) -> dict:
    """Best-effort parse of LLM JSON output.

    Handles markdown fences, trailing commas, and other common issues.
    """
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        # Remove opening fence (with optional language tag)
        first_newline = text.index("\n")
        text = text[first_newline + 1:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse profile JSON from LLM output, returning empty dict")
        logger.debug(f"Raw output was: {raw[:500]}")
        return {}
