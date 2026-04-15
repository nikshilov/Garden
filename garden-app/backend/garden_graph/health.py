"""Self-healing garden system — Phase 7 (Autonomy).

Health monitoring, self-diagnostics, and self-repair for characters.
Checks memory integrity, mood staleness, relationship bounds, and
narrative coherence. Repairs are non-destructive and logged.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger("garden.health")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
MOOD_PATH = os.path.join(DATA_DIR, "mood_states.json")
RELATIONSHIPS_PATH = os.path.join(DATA_DIR, "relationships.json")
CHAR_RELATIONSHIPS_PATH = os.path.join(DATA_DIR, "char_relationships.json")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMBEDDING_MISSING_THRESHOLD = 0.5  # fraction of records without embeddings
MOOD_EXTREME_THRESHOLD = 0.9       # abs value considered "stuck at extreme"
MOOD_STALE_DAYS = 7                # days without valence change = stale
REPETITION_OVERLAP_THRESHOLD = 0.8 # word overlap ratio for repetition
REPETITION_WINDOW = 3              # consecutive similar thoughts = problem
RELATIONSHIP_AXES = [
    "affection", "trust", "respect", "familiarity", "tension",
    "empathy", "engagement", "security", "autonomy", "admiration",
]

# Meta key in relationships.json used for housekeeping
_REL_META_KEY = "__meta__"


# ---------------------------------------------------------------------------
# HealthStatus enum
# ---------------------------------------------------------------------------

class HealthStatus(Enum):
    """Traffic-light health indicator."""

    GREEN = "green"    # healthy, no intervention needed
    YELLOW = "yellow"  # something feels off, worth investigating
    RED = "red"        # something is broken, needs human attention

    def __lt__(self, other: HealthStatus) -> bool:
        order = {HealthStatus.GREEN: 0, HealthStatus.YELLOW: 1, HealthStatus.RED: 2}
        return order[self] < order[other]


# ---------------------------------------------------------------------------
# HealthCheck dataclass
# ---------------------------------------------------------------------------

@dataclass
class HealthCheck:
    """Single health-check result."""

    char_id: str
    category: str       # "memory", "mood", "relationship", "coherence"
    status: HealthStatus
    message: str
    auto_fixable: bool
    checked_at: str     # ISO 8601

    def to_dict(self) -> dict:
        return {
            "char_id": self.char_id,
            "category": self.category,
            "status": self.status.value,
            "message": self.message,
            "auto_fixable": self.auto_fixable,
            "checked_at": self.checked_at,
        }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def overall_status(checks: List[HealthCheck]) -> HealthStatus:
    """Return the worst status from a list of checks."""
    if not checks:
        return HealthStatus.GREEN
    worst = HealthStatus.GREEN
    for check in checks:
        if check.status == HealthStatus.RED:
            return HealthStatus.RED
        if check.status == HealthStatus.YELLOW:
            worst = HealthStatus.YELLOW
    return worst


# ---------------------------------------------------------------------------
# HealthMonitor
# ---------------------------------------------------------------------------

class HealthMonitor:
    """Runs health checks across memory, mood, relationships, and coherence."""

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or DATA_DIR
        self._mood_path = os.path.join(self.data_dir, "mood_states.json")
        self._rel_path = os.path.join(self.data_dir, "relationships.json")
        self._char_rel_path = os.path.join(self.data_dir, "char_relationships.json")

    # ------------------------------------------------------------------
    # Memory health
    # ------------------------------------------------------------------

    def check_memory_health(self, char_id: str) -> List[HealthCheck]:
        """Check episodic memory integrity for *char_id*."""
        now = datetime.now(timezone.utc).isoformat()
        results: List[HealthCheck] = []

        try:
            from garden_graph.memory.episodic import EpisodicStore
            store = EpisodicStore()
            records = store._load(char_id)
        except Exception as e:
            logger.error("[%s] Failed to load episodic store: %s", char_id, e)
            results.append(HealthCheck(
                char_id=char_id,
                category="memory",
                status=HealthStatus.RED,
                message=f"Failed to load episodic memory: {e}",
                auto_fixable=False,
                checked_at=now,
            ))
            return results

        # No records at all
        if not records:
            results.append(HealthCheck(
                char_id=char_id,
                category="memory",
                status=HealthStatus.GREEN,
                message="No episodic records yet (new character).",
                auto_fixable=False,
                checked_at=now,
            ))
            return results

        # Check embedding coverage
        without_embedding = sum(1 for r in records if r.embedding is None)
        total = len(records)
        if total > 0 and without_embedding / total > EMBEDDING_MISSING_THRESHOLD:
            results.append(HealthCheck(
                char_id=char_id,
                category="memory",
                status=HealthStatus.YELLOW,
                message=(
                    f"{without_embedding}/{total} episodic records lack embeddings "
                    f"({without_embedding / total:.0%}). Semantic search degraded."
                ),
                auto_fixable=False,
                checked_at=now,
            ))

        # Check for duplicate memories (exact same summary text)
        seen_summaries: Dict[str, int] = {}
        duplicate_count = 0
        for r in records:
            key = r.summary.strip()
            seen_summaries[key] = seen_summaries.get(key, 0) + 1
        for summary, count in seen_summaries.items():
            if count > 1:
                duplicate_count += count - 1

        if duplicate_count > 0:
            results.append(HealthCheck(
                char_id=char_id,
                category="memory",
                status=HealthStatus.YELLOW,
                message=f"{duplicate_count} duplicate episodic memories detected.",
                auto_fixable=True,
                checked_at=now,
            ))

        # All clear
        if not results:
            results.append(HealthCheck(
                char_id=char_id,
                category="memory",
                status=HealthStatus.GREEN,
                message=f"Memory healthy ({total} records, {total - without_embedding} with embeddings).",
                auto_fixable=False,
                checked_at=now,
            ))

        return results

    # ------------------------------------------------------------------
    # Mood health
    # ------------------------------------------------------------------

    def check_mood_health(self, char_id: str) -> List[HealthCheck]:
        """Check mood state integrity for *char_id*."""
        now = datetime.now(timezone.utc).isoformat()
        results: List[HealthCheck] = []

        # Load mood file
        try:
            if not os.path.exists(self._mood_path):
                results.append(HealthCheck(
                    char_id=char_id,
                    category="mood",
                    status=HealthStatus.RED,
                    message="Mood state file is missing.",
                    auto_fixable=False,
                    checked_at=now,
                ))
                return results

            with open(self._mood_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            results.append(HealthCheck(
                char_id=char_id,
                category="mood",
                status=HealthStatus.RED,
                message=f"Mood state file is corrupted: {e}",
                auto_fixable=False,
                checked_at=now,
            ))
            return results

        entry = data.get(char_id)
        if entry is None:
            results.append(HealthCheck(
                char_id=char_id,
                category="mood",
                status=HealthStatus.RED,
                message=f"No mood entry found for character '{char_id}'.",
                auto_fixable=False,
                checked_at=now,
            ))
            return results

        vector = entry.get("vector", {})
        set_at = entry.get("set_at")

        # Check for extreme stuck axes
        extreme_axes: List[str] = []
        for axis, value in vector.items():
            try:
                if abs(float(value)) > MOOD_EXTREME_THRESHOLD:
                    extreme_axes.append(f"{axis}={value:.2f}")
            except (TypeError, ValueError):
                pass

        if extreme_axes:
            results.append(HealthCheck(
                char_id=char_id,
                category="mood",
                status=HealthStatus.YELLOW,
                message=f"Mood axes stuck at extremes: {', '.join(extreme_axes)}.",
                auto_fixable=True,
                checked_at=now,
            ))

        # Check for stale mood (valence unchanged for > 7 days)
        if set_at:
            try:
                last_set = datetime.fromisoformat(set_at)
                age_days = (datetime.now(timezone.utc) - last_set).total_seconds() / 86400
                if age_days > MOOD_STALE_DAYS:
                    results.append(HealthCheck(
                        char_id=char_id,
                        category="mood",
                        status=HealthStatus.YELLOW,
                        message=f"Mood hasn't been updated in {age_days:.1f} days (stale).",
                        auto_fixable=False,
                        checked_at=now,
                    ))
            except (ValueError, TypeError):
                pass

        # All clear
        if not results:
            results.append(HealthCheck(
                char_id=char_id,
                category="mood",
                status=HealthStatus.GREEN,
                message="Mood state healthy.",
                auto_fixable=False,
                checked_at=now,
            ))

        return results

    # ------------------------------------------------------------------
    # Relationship health
    # ------------------------------------------------------------------

    def check_relationship_health(self, char_id: str) -> List[HealthCheck]:
        """Check relationship axes for bounds and staleness."""
        now = datetime.now(timezone.utc).isoformat()
        results: List[HealthCheck] = []

        # --- User-facing relationships (relationships.json) ---
        results.extend(self._check_user_relationships(char_id, now))

        # --- Character-to-character relationships (char_relationships.json) ---
        results.extend(self._check_char_relationships(char_id, now))

        if not results:
            results.append(HealthCheck(
                char_id=char_id,
                category="relationship",
                status=HealthStatus.GREEN,
                message="Relationships healthy.",
                auto_fixable=False,
                checked_at=now,
            ))

        return results

    def _check_user_relationships(self, char_id: str, now: str) -> List[HealthCheck]:
        """Validate the user<->character relationship axes."""
        results: List[HealthCheck] = []

        try:
            if not os.path.exists(self._rel_path):
                return results

            with open(self._rel_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            results.append(HealthCheck(
                char_id=char_id,
                category="relationship",
                status=HealthStatus.RED,
                message=f"Relationships file corrupted: {e}",
                auto_fixable=False,
                checked_at=now,
            ))
            return results

        rel = data.get(char_id)
        if rel is None or char_id == _REL_META_KEY:
            return results

        if not isinstance(rel, dict):
            return results

        # Check out-of-bounds axes
        oob_axes: List[str] = []
        for axis, value in rel.items():
            try:
                v = float(value)
                if v < -1.0 or v > 1.0:
                    oob_axes.append(f"{axis}={v:.3f}")
            except (TypeError, ValueError):
                pass

        if oob_axes:
            results.append(HealthCheck(
                char_id=char_id,
                category="relationship",
                status=HealthStatus.YELLOW,
                message=f"User relationship axes out of bounds: {', '.join(oob_axes)}.",
                auto_fixable=True,
                checked_at=now,
            ))

        # Check if all axes are zero (no relationship formed)
        all_zero = all(
            float(rel.get(axis, 0.0)) == 0.0
            for axis in RELATIONSHIP_AXES
            if axis in rel
        )
        if all_zero and rel:
            results.append(HealthCheck(
                char_id=char_id,
                category="relationship",
                status=HealthStatus.YELLOW,
                message="All user relationship axes are zero — no relationship formed.",
                auto_fixable=False,
                checked_at=now,
            ))

        return results

    def _check_char_relationships(self, char_id: str, now: str) -> List[HealthCheck]:
        """Validate the character-to-character relationship axes."""
        results: List[HealthCheck] = []

        try:
            if not os.path.exists(self._char_rel_path):
                return results

            with open(self._char_rel_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            results.append(HealthCheck(
                char_id=char_id,
                category="relationship",
                status=HealthStatus.RED,
                message=f"Char-relationships file corrupted: {e}",
                auto_fixable=False,
                checked_at=now,
            ))
            return results

        targets = data.get(char_id)
        if targets is None or char_id == _REL_META_KEY:
            return results

        if not isinstance(targets, dict):
            return results

        for target_id, rel in targets.items():
            if target_id == _REL_META_KEY or not isinstance(rel, dict):
                continue

            # Out-of-bounds check
            oob_axes: List[str] = []
            for axis, value in rel.items():
                try:
                    v = float(value)
                    if v < -1.0 or v > 1.0:
                        oob_axes.append(f"{axis}={v:.3f}")
                except (TypeError, ValueError):
                    pass

            if oob_axes:
                results.append(HealthCheck(
                    char_id=char_id,
                    category="relationship",
                    status=HealthStatus.YELLOW,
                    message=(
                        f"Char relationship {char_id}->{target_id} axes out of bounds: "
                        f"{', '.join(oob_axes)}."
                    ),
                    auto_fixable=True,
                    checked_at=now,
                ))

            # All-zero check
            all_zero = all(
                float(rel.get(axis, 0.0)) == 0.0
                for axis in RELATIONSHIP_AXES
                if axis in rel
            )
            if all_zero and rel:
                results.append(HealthCheck(
                    char_id=char_id,
                    category="relationship",
                    status=HealthStatus.YELLOW,
                    message=(
                        f"Char relationship {char_id}->{target_id}: "
                        f"all axes zero — no relationship formed."
                    ),
                    auto_fixable=False,
                    checked_at=now,
                ))

        return results

    # ------------------------------------------------------------------
    # Coherence health
    # ------------------------------------------------------------------

    def check_coherence(self, char_id: str) -> List[HealthCheck]:
        """Detect repetitive internal thoughts in recent episodic memory."""
        now = datetime.now(timezone.utc).isoformat()
        results: List[HealthCheck] = []

        try:
            from garden_graph.memory.episodic import EpisodicStore
            store = EpisodicStore()
            records = store._load(char_id)
        except Exception as e:
            logger.error("[%s] Failed to load episodic store for coherence check: %s", char_id, e)
            results.append(HealthCheck(
                char_id=char_id,
                category="coherence",
                status=HealthStatus.YELLOW,
                message=f"Could not load episodic memory for coherence check: {e}",
                auto_fixable=False,
                checked_at=now,
            ))
            return results

        # Take the last 20 records
        recent = records[-20:] if len(records) > 20 else records

        if len(recent) < REPETITION_WINDOW + 1:
            results.append(HealthCheck(
                char_id=char_id,
                category="coherence",
                status=HealthStatus.GREEN,
                message="Too few records for coherence analysis.",
                auto_fixable=False,
                checked_at=now,
            ))
            return results

        # Sliding window: check for consecutive highly-similar summaries
        max_streak = 1
        current_streak = 1
        for i in range(1, len(recent)):
            overlap = self._word_overlap(recent[i - 1].summary, recent[i].summary)
            if overlap > REPETITION_OVERLAP_THRESHOLD:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 1

        if max_streak > REPETITION_WINDOW:
            results.append(HealthCheck(
                char_id=char_id,
                category="coherence",
                status=HealthStatus.YELLOW,
                message=(
                    f"Detected {max_streak} consecutive similar memories "
                    f"(word overlap > {REPETITION_OVERLAP_THRESHOLD}). "
                    f"Character may be stuck in a thought loop."
                ),
                auto_fixable=False,
                checked_at=now,
            ))

        if not results:
            results.append(HealthCheck(
                char_id=char_id,
                category="coherence",
                status=HealthStatus.GREEN,
                message="Narrative coherence looks good.",
                auto_fixable=False,
                checked_at=now,
            ))

        return results

    @staticmethod
    def _word_overlap(a: str, b: str) -> float:
        """Compute word-level overlap ratio between two strings.

        Returns the size of the intersection divided by the size of the
        smaller set, so identical strings yield 1.0 and completely
        different strings yield 0.0.
        """
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = len(words_a & words_b)
        smaller = min(len(words_a), len(words_b))
        return intersection / smaller if smaller > 0 else 0.0

    # ------------------------------------------------------------------
    # Aggregate checks
    # ------------------------------------------------------------------

    def check_all(self, char_id: str) -> List[HealthCheck]:
        """Run all health checks for a single character."""
        results: List[HealthCheck] = []
        results.extend(self.check_memory_health(char_id))
        results.extend(self.check_mood_health(char_id))
        results.extend(self.check_relationship_health(char_id))
        results.extend(self.check_coherence(char_id))
        return results

    def check_all_characters(
        self, character_ids: List[str]
    ) -> Dict[str, List[HealthCheck]]:
        """Run all health checks for multiple characters."""
        report: Dict[str, List[HealthCheck]] = {}
        for char_id in character_ids:
            try:
                report[char_id] = self.check_all(char_id)
            except Exception as e:
                logger.error("[%s] Unexpected error during health check: %s", char_id, e)
                report[char_id] = [
                    HealthCheck(
                        char_id=char_id,
                        category="general",
                        status=HealthStatus.RED,
                        message=f"Health check crashed: {e}",
                        auto_fixable=False,
                        checked_at=datetime.now(timezone.utc).isoformat(),
                    )
                ]
        return report


# ---------------------------------------------------------------------------
# SelfRepair
# ---------------------------------------------------------------------------

class SelfRepair:
    """Non-destructive self-repair operations for character data."""

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or DATA_DIR
        self._mood_path = os.path.join(self.data_dir, "mood_states.json")
        self._rel_path = os.path.join(self.data_dir, "relationships.json")
        self._char_rel_path = os.path.join(self.data_dir, "char_relationships.json")

    # ------------------------------------------------------------------
    # Duplicate memory pruning
    # ------------------------------------------------------------------

    def prune_duplicate_memories(self, char_id: str) -> bool:
        """Remove exact duplicate summaries from episodic store, keeping the newest.

        Returns True if any duplicates were removed.
        """
        try:
            from garden_graph.memory.episodic import EpisodicStore
            store = EpisodicStore()
            records = store._load(char_id)
        except Exception as e:
            logger.error("[%s] Failed to load episodic store for pruning: %s", char_id, e)
            return False

        if not records:
            return False

        # Group by summary text, keep the newest record in each group
        seen: Dict[str, int] = {}  # summary -> index of newest
        to_remove: set = set()

        for i, record in enumerate(records):
            key = record.summary.strip()
            if key in seen:
                # Compare timestamps: keep the newer one
                existing_idx = seen[key]
                existing_ts = records[existing_idx].created_at
                current_ts = record.created_at
                if current_ts > existing_ts:
                    to_remove.add(existing_idx)
                    seen[key] = i
                else:
                    to_remove.add(i)
            else:
                seen[key] = i

        if not to_remove:
            return False

        original_count = len(records)
        pruned = [r for i, r in enumerate(records) if i not in to_remove]
        store._cache[char_id] = pruned
        store._save(char_id)

        removed = original_count - len(pruned)
        logger.info(
            "[%s] Pruned %d duplicate episodic memories (%d -> %d)",
            char_id, removed, original_count, len(pruned),
        )
        return True

    # ------------------------------------------------------------------
    # Stuck mood reset
    # ------------------------------------------------------------------

    def reset_stuck_mood(self, char_id: str) -> bool:
        """Reset any mood axis that is stuck at an extreme (abs > 0.9) to 0.0.

        Returns True if any reset happened.
        """
        try:
            if not os.path.exists(self._mood_path):
                logger.warning("[%s] Mood file not found, cannot reset", char_id)
                return False

            with open(self._mood_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error("[%s] Failed to load mood file: %s", char_id, e)
            return False

        entry = data.get(char_id)
        if entry is None:
            return False

        vector = entry.get("vector", {})
        changed = False
        reset_axes: List[str] = []

        for axis, value in vector.items():
            try:
                v = float(value)
                if abs(v) > MOOD_EXTREME_THRESHOLD:
                    vector[axis] = 0.0
                    reset_axes.append(f"{axis}: {v:.2f} -> 0.0")
                    changed = True
            except (TypeError, ValueError):
                pass

        if not changed:
            return False

        entry["set_at"] = datetime.now(timezone.utc).isoformat()
        try:
            with open(self._mood_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("[%s] Reset stuck mood axes: %s", char_id, "; ".join(reset_axes))
        except OSError as e:
            logger.error("[%s] Failed to save mood file after reset: %s", char_id, e)
            return False

        return True

    # ------------------------------------------------------------------
    # Relationship axis clamping
    # ------------------------------------------------------------------

    def clamp_relationship_axes(self, char_id: str) -> bool:
        """Clamp all relationship axes to [-1, 1] for both user and char relationships.

        Returns True if any clamping happened.
        """
        changed = False

        # Clamp user-facing relationships
        if self._clamp_user_relationships(char_id):
            changed = True

        # Clamp character-to-character relationships
        if self._clamp_char_relationships(char_id):
            changed = True

        return changed

    def _clamp_user_relationships(self, char_id: str) -> bool:
        """Clamp user<->character relationship axes to [-1, 1]."""
        try:
            if not os.path.exists(self._rel_path):
                return False

            with open(self._rel_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error("[%s] Failed to load relationships: %s", char_id, e)
            return False

        rel = data.get(char_id)
        if rel is None or not isinstance(rel, dict):
            return False

        changed = False
        clamped: List[str] = []
        for axis, value in rel.items():
            try:
                v = float(value)
                clamped_v = max(-1.0, min(1.0, v))
                if clamped_v != v:
                    rel[axis] = clamped_v
                    clamped.append(f"{axis}: {v:.3f} -> {clamped_v:.3f}")
                    changed = True
            except (TypeError, ValueError):
                pass

        if not changed:
            return False

        try:
            with open(self._rel_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("[%s] Clamped user relationship axes: %s", char_id, "; ".join(clamped))
        except OSError as e:
            logger.error("[%s] Failed to save relationships after clamping: %s", char_id, e)
            return False

        return True

    def _clamp_char_relationships(self, char_id: str) -> bool:
        """Clamp character-to-character relationship axes to [-1, 1]."""
        try:
            if not os.path.exists(self._char_rel_path):
                return False

            with open(self._char_rel_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error("[%s] Failed to load char relationships: %s", char_id, e)
            return False

        targets = data.get(char_id)
        if targets is None or not isinstance(targets, dict):
            return False

        changed = False
        for target_id, rel in targets.items():
            if target_id == _REL_META_KEY or not isinstance(rel, dict):
                continue

            for axis, value in rel.items():
                try:
                    v = float(value)
                    clamped_v = max(-1.0, min(1.0, v))
                    if clamped_v != v:
                        rel[axis] = clamped_v
                        changed = True
                        logger.debug(
                            "[%s] Clamped %s->%s.%s: %.3f -> %.3f",
                            char_id, char_id, target_id, axis, v, clamped_v,
                        )
                except (TypeError, ValueError):
                    pass

        if not changed:
            return False

        try:
            with open(self._char_rel_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("[%s] Clamped char-to-char relationship axes", char_id)
        except OSError as e:
            logger.error("[%s] Failed to save char relationships after clamping: %s", char_id, e)
            return False

        return True

    # ------------------------------------------------------------------
    # Aggregate repair
    # ------------------------------------------------------------------

    def repair_all(self, char_id: str, checks: List[HealthCheck]) -> List[str]:
        """Attempt automatic repair for every auto_fixable check.

        Returns a list of human-readable repair descriptions.
        """
        repairs: List[str] = []

        for check in checks:
            if not check.auto_fixable:
                continue

            try:
                if check.category == "memory" and "duplicate" in check.message.lower():
                    if self.prune_duplicate_memories(char_id):
                        repairs.append(f"Pruned duplicate episodic memories for {char_id}.")

                elif check.category == "mood" and "extreme" in check.message.lower():
                    if self.reset_stuck_mood(char_id):
                        repairs.append(f"Reset stuck mood axes for {char_id}.")

                elif check.category == "relationship" and "out of bounds" in check.message.lower():
                    if self.clamp_relationship_axes(char_id):
                        repairs.append(f"Clamped out-of-bounds relationship axes for {char_id}.")

            except Exception as e:
                logger.error(
                    "[%s] Repair failed for %s check: %s",
                    char_id, check.category, e,
                )
                repairs.append(f"FAILED: {check.category} repair for {char_id}: {e}")

        if repairs:
            logger.info("[%s] Completed %d repairs", char_id, len(repairs))
        else:
            logger.debug("[%s] No auto-fixable issues found", char_id)

        return repairs
