import math
from datetime import datetime, timedelta, timezone

import pytest

from garden_graph.memory.manager import MemoryManager, EMOTION_AXIS_WEIGHTS, RELATIONSHIP_AXES


def _fresh_manager():
    """Return MemoryManager with empty in-memory structures (no disk IO heavy)."""
    mm = MemoryManager()
    mm._records.clear()
    mm.relationships.clear()
    return mm


def test_passive_decay():
    mm = _fresh_manager()
    mm.relationships["char"] = {axis: 0.5 for axis in RELATIONSHIP_AXES}
    # pretend last decay was 48h ago
    mm._last_decay_ts = datetime.now(timezone.utc) - timedelta(days=2)
    mm._apply_passive_decay()
    # All axes should be lower than original 0.5
    for val in mm.relationships["char"].values():
        assert val < 0.5


def test_update_relationship_with_anger():
    mm = _fresh_manager()
    emotions = {"anger": 1.0}
    mm._update_relationship("char", emotions, category="other", significance=-1.0, personal_factor=1.0)
    # Anger should increase tension and reduce affection by mapping
    assert mm.relationships["char"]["tension"] > 0
    assert mm.relationships["char"]["affection"] < 0
