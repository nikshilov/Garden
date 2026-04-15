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
import random
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple

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

        # Phase 6: Garden world state
        self._garden_world = None
        try:
            from garden_graph.garden_world import GardenWorld
            self._garden_world = GardenWorld()
        except Exception:
            pass

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

        # Phase 6: Update garden world state (season, weather, presences)
        if self._garden_world:
            try:
                self._garden_world.update(now)
                logger.info("Garden world state updated")
            except Exception as e:
                logger.warning(f"Garden world update failed: {e}")

        for char_id in self.character_ids:
            try:
                await self._tick_character(char_id, now)
            except Exception as e:
                logger.error(f"Heartbeat tick failed for {char_id}: {e}")

        # Autonomous inter-character conversations
        try:
            await self._autonomous_conversations(now)
        except Exception as e:
            logger.error(f"Autonomous conversations failed: {e}", exc_info=True)

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

        # 3. Backfill embeddings for old memories (Phase 2)
        backfilled = self.episodic_store.backfill_embeddings(char_id, batch_size=20)
        if backfilled:
            logger.info(f"[{char_id}] Backfilled {backfilled} memory embeddings")

        # 4. Cluster memories if enough have embeddings (Phase 2)
        self._cluster_memories(char_id)

        # 5. Process identity evolution (Phase 4)
        self._evolve_identity(char_id)

        # 6. Generate internal monologue
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

        # Phase 3: Also drift character-to-character relationships
        try:
            if hasattr(self.memory_manager, 'decay_char_relationships'):
                self.memory_manager.decay_char_relationships()
        except Exception as e:
            logger.debug(f"[{char_id}] Char relationship decay skipped: {e}")

    def _cluster_memories(self, char_id: str):
        """Cluster related episodic memories by embedding similarity.

        Results are stored as a JSON file per character that can feed into
        the reflection system. Only runs when enough embedded records exist.
        """
        import json as _json
        records = self.episodic_store._load(char_id)
        embedded = [r for r in records if r.embedding is not None]
        if len(embedded) < 5:
            return  # not enough data to cluster meaningfully

        try:
            import numpy as np
            from garden_graph.memory.clustering import cluster_memories

            embeddings = np.array([r.embedding for r in embedded], dtype=np.float32)
            ids = [r.id for r in embedded]
            summaries = [r.summary for r in embedded]

            clusters = cluster_memories(
                embeddings, ids, summaries,
                min_cluster_size=3, similarity_threshold=0.45,
            )

            if clusters:
                # Persist clusters for the reflection system
                data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
                os.makedirs(data_dir, exist_ok=True)
                path = os.path.join(data_dir, f"clusters_{char_id}.json")
                with open(path, "w", encoding="utf-8") as f:
                    _json.dump(
                        [{"label": c.label, "record_ids": c.record_ids,
                          "coherence": c.coherence} for c in clusters],
                        f, ensure_ascii=False, indent=2,
                    )
                logger.info(f"[{char_id}] Found {len(clusters)} memory clusters")
        except Exception as e:
            logger.warning(f"[{char_id}] Clustering failed: {e}")

    def _evolve_identity(self, char_id: str):
        """Feed reflection results into the identity system (Phase 4).

        Checks recent reflections for trait deltas and growth narratives,
        then applies them to the character's evolving identity.
        """
        try:
            from garden_graph.identity import IdentityManager
            from garden_graph.memory.reflection import ReflectionManager

            if not self.memory_manager:
                return

            reflection_mgr = self.memory_manager.reflection_mgr
            all_refs = reflection_mgr.all_reflections(char_id)
            if not all_refs:
                return

            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
            id_mgr = IdentityManager(data_dir)
            identity = id_mgr.get_or_create(char_id)

            # Process reflections that have trait deltas or growth narratives
            processed_ids = {gm.id for gm in identity.growth_memories}
            for ref in all_refs:
                if ref.id in processed_ids:
                    continue  # already processed

                # Apply trait deltas
                if ref.traits_delta:
                    id_mgr.update_traits(char_id, ref.traits_delta)
                    logger.info(f"[{char_id}] Applied trait drift from reflection: {ref.traits_delta}")

                # Record growth narrative
                narrative = reflection_mgr.generate_growth_narrative(ref)
                if narrative:
                    id_mgr.record_growth(char_id, narrative, ref.traits_delta or {})
                    logger.info(f"[{char_id}] Growth narrative: {narrative[:60]}...")

        except ImportError:
            pass  # identity module not available yet
        except Exception as e:
            logger.debug(f"[{char_id}] Identity evolution skipped: {e}")

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

        # Phase 6: Garden world context for richer internal thoughts
        garden_context = ""
        if self._garden_world:
            try:
                garden_context = self._garden_world.character_context(char_id)
            except Exception:
                pass

        prompt = f"""You are {char_name}. You're in the garden right now, between conversations.
{template.get("prompt", "")}

{garden_context}
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

    # ------------------------------------------------------------------
    # Autonomous inter-character conversations
    # ------------------------------------------------------------------

    async def _autonomous_conversations(self, now: datetime):
        """After individual ticks, let co-located characters talk to each other.

        Groups characters by location, evaluates conversation probability
        for each co-located pair, and generates short exchanges.
        Each character participates in at most one conversation per tick.
        """
        if not self._garden_world or not self.memory_manager:
            return

        presences = self._garden_world.get_all_presences()

        # Group by location
        by_location: Dict[str, List] = defaultdict(list)
        for p in presences:
            if p.char_id in self.character_ids:
                by_location[p.location].append(p)

        # Track who has already conversed this tick
        conversed: set = set()
        conversations_started = 0

        for location, chars in by_location.items():
            if len(chars) < 2:
                continue

            # Try all pairs at this location
            for i in range(len(chars)):
                for j in range(i + 1, len(chars)):
                    a = chars[i]
                    b = chars[j]

                    # Each character talks at most once per tick
                    if a.char_id in conversed or b.char_id in conversed:
                        continue

                    if self._should_converse(a, b):
                        try:
                            await self._generate_conversation(a, b, location, now)
                            conversed.add(a.char_id)
                            conversed.add(b.char_id)
                            conversations_started += 1
                        except Exception as e:
                            logger.warning(
                                f"Conversation between {a.char_id} and {b.char_id} failed: {e}"
                            )

        if conversations_started:
            logger.info(f"Autonomous conversations this tick: {conversations_started}")

    def _should_converse(self, a, b) -> bool:
        """Decide whether two co-located characters should start a conversation.

        Base 30% probability, modified by energy and relationship strength.
        """
        # Base probability
        prob = 0.30

        # Energy modifier: average energy of both characters
        avg_energy = (a.energy + b.energy) / 2.0
        if avg_energy < 0.3:
            prob *= 0.3   # very unlikely when tired
        elif avg_energy < 0.5:
            prob *= 0.6

        # Relationship bonus: check familiarity/affection between them
        if self.memory_manager and hasattr(self.memory_manager, 'char_relationships'):
            rel_a_to_b = self.memory_manager.char_relationships.get(a.char_id, {}).get(b.char_id, {})
            rel_b_to_a = self.memory_manager.char_relationships.get(b.char_id, {}).get(a.char_id, {})

            # Average of key axes from both directions
            fam = (rel_a_to_b.get("familiarity", 0) + rel_b_to_a.get("familiarity", 0)) / 2.0
            aff = (rel_a_to_b.get("affection", 0) + rel_b_to_a.get("affection", 0)) / 2.0

            if fam > 0.3 or aff > 0.3:
                prob += 0.15
            if fam > 0.5 or aff > 0.5:
                prob += 0.10

        # Clamp to [0.05, 0.70]
        prob = max(0.05, min(0.70, prob))

        return random.random() < prob

    async def _generate_conversation(self, a, b, location: str, now: datetime):
        """Generate a 2-3 message exchange between two characters.

        Uses the LLM to produce natural remarks aware of location, mood,
        and existing relationship. Stores results via process_cross_talk().
        """
        llm = self._get_llm()
        if not llm:
            return

        from langchain_core.messages import HumanMessage
        from garden_graph.garden_world import _location_label

        template_a = CHARACTER_TEMPLATES.get(a.char_id, {})
        template_b = CHARACTER_TEMPLATES.get(b.char_id, {})
        name_a = template_a.get("name", a.char_id.capitalize())
        name_b = template_b.get("name", b.char_id.capitalize())
        loc_label = _location_label(location)

        # Get relationship context for both
        rel_context_a = ""
        rel_context_b = ""
        if self.memory_manager and hasattr(self.memory_manager, 'char_relationship_context'):
            rel_context_a = self.memory_manager.char_relationship_context(a.char_id)
            rel_context_b = self.memory_manager.char_relationship_context(b.char_id)

        # Get garden context
        garden_ctx = ""
        if self._garden_world:
            try:
                garden_ctx = self._garden_world.character_context(a.char_id)
            except Exception:
                pass

        # --- Message 1: A opens ---
        prompt_a = f"""You are {name_a}. {template_a.get("prompt", "")}

{garden_ctx}
{rel_context_a}

You are at {loc_label}. {name_b} is here with you.
Say something natural — a remark, observation, or question.
One or two sentences. Don't greet them formally, just talk like you already know each other.
Do not use quotation marks around your speech."""

        response_a = await asyncio.to_thread(
            llm.invoke, [HumanMessage(content=prompt_a)]
        )
        msg_a = response_a.content.strip()

        # --- Message 2: B responds ---
        prompt_b = f"""You are {name_b}. {template_b.get("prompt", "")}

{garden_ctx}
{rel_context_b}

You are at {loc_label}. {name_a} just said to you: "{msg_a}"
Respond naturally in one or two sentences.
Do not use quotation marks around your speech."""

        response_b = await asyncio.to_thread(
            llm.invoke, [HumanMessage(content=prompt_b)]
        )
        msg_b = response_b.content.strip()

        # Store the exchange via process_cross_talk (both directions)
        self.memory_manager.process_cross_talk(a.char_id, b.char_id, msg_b, msg_a)
        self.memory_manager.process_cross_talk(b.char_id, a.char_id, msg_a, msg_b)

        # Episodic memory for both
        self.episodic_store.add(
            a.char_id,
            f"[conversation with {name_b} at {loc_label}] I said: {msg_a[:80]}... "
            f"They replied: {msg_b[:80]}"
        )
        self.episodic_store.add(
            b.char_id,
            f"[conversation with {name_a} at {loc_label}] {name_a} said: {msg_a[:80]}... "
            f"I replied: {msg_b[:80]}"
        )

        logger.info(
            f"Autonomous conversation: {name_a} <-> {name_b} at {loc_label} "
            f"({2} messages)"
        )

        # --- 50% chance: A replies once more ---
        if random.random() < 0.5:
            prompt_a2 = f"""You are {name_a}. {template_a.get("prompt", "")}

You are at {loc_label} talking with {name_b}.
You said: "{msg_a}"
{name_b} replied: "{msg_b}"
Say one more brief remark to continue or wrap up the exchange.
One sentence. Do not use quotation marks."""

            response_a2 = await asyncio.to_thread(
                llm.invoke, [HumanMessage(content=prompt_a2)]
            )
            msg_a2 = response_a2.content.strip()

            # Update episodic memory with the third message
            self.episodic_store.add(
                a.char_id,
                f"[continued conversation with {name_b}] I added: {msg_a2[:100]}"
            )
            self.episodic_store.add(
                b.char_id,
                f"[continued conversation with {name_a}] {name_a} added: {msg_a2[:100]}"
            )

            logger.info(f"  {name_a} added: {msg_a2[:60]}...")
