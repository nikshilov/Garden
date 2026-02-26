"""Heartbeat engine — gives characters life between conversations.

Runs periodically in the background, maintaining character state:
- Decays mood naturally
- Drifts relationships without contact
- Generates internal thoughts (stored as episodic memories)
- Processes scheduled events
"""
import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any

from garden_graph.mood import generate_mood, MoodState
from garden_graph.memory.episodic import EpisodicStore
from garden_graph.character import CHARACTER_TEMPLATES

logger = logging.getLogger("garden.heartbeat")

# Configurable interval (default: every 6 hours)
HEARTBEAT_INTERVAL_HOURS = float(os.getenv("HEARTBEAT_INTERVAL_HOURS", "6"))

# Internal monologue model (use a cheap/fast model)
HEARTBEAT_MODEL = os.getenv("HEARTBEAT_MODEL", "gpt-4o-mini")


class Heartbeat:
    """Background engine that maintains character life between conversations."""

    def __init__(self, character_ids: list[str], memory_manager=None):
        self.character_ids = character_ids
        self.memory_manager = memory_manager
        self.episodic_store = EpisodicStore()
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._llm = None

    def _get_llm(self):
        """Lazy-load LLM for internal monologue generation."""
        if self._llm is None:
            from garden_graph.config import get_llm
            try:
                self._llm = get_llm(HEARTBEAT_MODEL, temperature=0.9)
            except Exception as e:
                logger.warning(f"Failed to init heartbeat LLM: {e}")
        return self._llm

    async def start(self):
        """Start the heartbeat background loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"Heartbeat started (interval: {HEARTBEAT_INTERVAL_HOURS}h, characters: {self.character_ids})")

    async def stop(self):
        """Stop the heartbeat loop gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Heartbeat stopped")

    async def _loop(self):
        """Main heartbeat loop — runs every HEARTBEAT_INTERVAL_HOURS."""
        while self._running:
            try:
                await self.tick()
            except Exception as e:
                logger.error(f"Heartbeat tick error: {e}", exc_info=True)

            await asyncio.sleep(HEARTBEAT_INTERVAL_HOURS * 3600)

    async def tick(self):
        """Execute one heartbeat cycle for all characters."""
        logger.info("Heartbeat tick starting")
        now = datetime.now(timezone.utc)

        for char_id in self.character_ids:
            try:
                await self._tick_character(char_id, now)
            except Exception as e:
                logger.error(f"Heartbeat tick failed for {char_id}: {e}")

        # Persist memory state after all characters processed
        if self.memory_manager:
            try:
                self.memory_manager.save_to_file(self.memory_manager.get_default_filepath())
            except Exception as e:
                logger.error(f"Failed to save memory state after heartbeat: {e}")

        logger.info("Heartbeat tick complete")

    async def _tick_character(self, char_id: str, now: datetime):
        """Process one heartbeat cycle for a single character."""
        logger.debug(f"[{char_id}] Processing heartbeat tick")

        # 1. Process scheduled events
        if self.memory_manager:
            pending = self.memory_manager.check_pending_events(char_id, now)
            for event in pending:
                logger.info(f"[{char_id}] Event triggered: {event.get('description', '?')}")
                self.memory_manager.complete_event(event['id'], user_responded=False)

        # 2. Drift relationships (familiarity decays without contact)
        self._drift_relationships(char_id, now)

        # 3. Generate internal monologue
        await self._generate_internal_thought(char_id, now)

    def _drift_relationships(self, char_id: str, now: datetime):
        """Apply passive relationship drift when there's no contact."""
        if not self.memory_manager:
            return

        rel = self.memory_manager.relationships.get(char_id, {})
        if not rel:
            return

        # Calculate days since last interaction
        last_seen = self._get_last_seen(char_id)
        if not last_seen:
            return

        days_absent = (now - last_seen).total_seconds() / 86400.0
        if days_absent < 0.5:  # Less than 12 hours — no drift
            return

        # Gentle drift toward neutral
        drift_rate = 0.002  # per day
        drift = drift_rate * days_absent

        for axis in ["familiarity", "engagement", "security"]:
            current = rel.get(axis, 0.0)
            if abs(current) > 0.05:
                # Drift toward 0 (neutral)
                if current > 0:
                    rel[axis] = max(0.0, current - drift)
                else:
                    rel[axis] = min(0.0, current + drift)

        # Tension naturally resolves over time (this is forgiveness in action)
        tension = rel.get("tension", 0.0)
        if tension > 0.05:
            rel["tension"] = max(0.0, tension - drift * 1.5)

        self.memory_manager.relationships[char_id] = rel
        logger.debug(f"[{char_id}] Relationship drift applied (days_absent={days_absent:.1f})")

    def _get_last_seen(self, char_id: str) -> Optional[datetime]:
        """Get last seen time for a character from persisted data."""
        import json
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        path = os.path.join(data_dir, "last_seen_times.json")
        try:
            if os.path.exists(path):
                with open(path, "r") as f:
                    data = json.load(f)
                    ts = data.get(char_id)
                    if ts:
                        return datetime.fromisoformat(ts)
        except Exception:
            pass
        return None

    async def _generate_internal_thought(self, char_id: str, now: datetime):
        """Generate an internal monologue entry for the character.

        This is NOT shown to the user. It's stored in episodic memory
        so the character has continuity — they've been "thinking" between
        conversations.
        """
        llm = self._get_llm()
        if not llm:
            return

        # Build context for the thought
        template = CHARACTER_TEMPLATES.get(char_id, {})
        char_name = template.get("name", char_id.capitalize())

        # Gather recent context
        recent_episodes = self.episodic_store.last_n(char_id, n=3)
        recent_context = ""
        if recent_episodes:
            recent_context = "\n".join(f"- {ep.summary}" for ep in recent_episodes)

        # Get mood and relationship state
        mood_context = ""
        rel_context = ""
        if self.memory_manager:
            mood_vec = self.memory_manager._get_mood_vector(char_id)
            if mood_vec:
                # Find dominant mood
                dominant = max(mood_vec.items(), key=lambda kv: abs(kv[1]), default=("neutral", 0))
                if abs(dominant[1]) > 0.1:
                    mood_context = f"You're currently feeling somewhat {dominant[0]}."

            rel = self.memory_manager.relationships.get(char_id, {})
            if rel:
                # Summarize relationship state
                strong_axes = [(k, v) for k, v in rel.items() if abs(v) > 0.3 and k != "__meta__"]
                if strong_axes:
                    rel_parts = [f"{k}: {v:+.1f}" for k, v in strong_axes[:3]]
                    rel_context = f"Your relationship with the user: {', '.join(rel_parts)}"

        # Time since last seen
        last_seen = self._get_last_seen(char_id)
        time_context = ""
        if last_seen:
            hours = (now - last_seen).total_seconds() / 3600
            if hours < 24:
                time_context = "The user was here recently."
            elif hours < 72:
                time_context = "It's been a day or two since the user was here."
            elif hours < 168:
                time_context = "It's been several days since the user was here. You notice their absence."
            else:
                time_context = "It's been over a week since the user was here. You miss them."

        prompt = f"""You are {char_name}. You're alone in the garden right now, between conversations.
{template.get("prompt", "")}

{mood_context}
{rel_context}
{time_context}

{"Recent memories:" if recent_context else ""}
{recent_context}

Generate a brief internal thought — something you'd think about alone.
This is your private inner monologue, not a message to anyone.
One or two sentences. Be authentic to your personality.
Do not say "I think" at the start. Just think."""

        try:
            from langchain_core.messages import HumanMessage
            response = await asyncio.to_thread(
                llm.invoke, [HumanMessage(content=prompt)]
            )
            thought = response.content.strip()

            if thought and len(thought) > 10:
                # Store as episodic memory with [internal] prefix
                self.episodic_store.add(char_id, f"[internal thought] {thought}")
                logger.info(f"[{char_id}] Internal thought: {thought[:60]}...")

        except Exception as e:
            logger.warning(f"[{char_id}] Failed to generate internal thought: {e}")
