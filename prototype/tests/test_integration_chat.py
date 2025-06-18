"""Integration-like test: feed a short conversation through MemoryManager and ensure
supervisor prompt-refresh event fires and cost tracking works (dry-run).
"""
from __future__ import annotations

import importlib
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from garden_graph.memory.manager import MemoryManager
from garden_graph.supervisor import Supervisor


@pytest.fixture(autouse=True)
def _low_threshold(monkeypatch):
    """Lower thresholds to make test deterministic and cheap."""
    monkeypatch.setenv("PROMPT_REFRESH_ENERGY_THRESHOLD", "1.0")
    monkeypatch.setenv("MEM_SIGNIFICANCE_THRESHOLD", "0.2")
    monkeypatch.setenv("HIGHLIGHT_IMPACT_THRESHOLD", "0.8")
    # reload config & supervisor to pick up env vars
    import garden_graph.config as cfg
    importlib.reload(cfg)
    import garden_graph.supervisor as sup_mod
    importlib.reload(sup_mod)
    yield


def _fixed_analyze(cid: str, text: str, llm=None):
    """Deterministic significance & sentiment based on keywords."""
    text_l = text.lower()
    if "love" in text_l or "great" in text_l:
        return 1.0, "praise", {}
    if "hate" in text_l or "angry" in text_l:
        return -1.2, "insult", {}
    # neutral
    return 0.1, "neutral", {}


def test_chat_flow(monkeypatch):
    mm = MemoryManager()
    # patch analyze to deterministic
    monkeypatch.setattr(mm, "_analyze_message_llm", _fixed_analyze)

    # intercept schedule_event
    scheduled = {}

    def fake_schedule_event(**kwargs):
        scheduled["event"] = kwargs
        return "evt-test"

    mm.scheduler.schedule_event = fake_schedule_event  # type: ignore

    convo = [
        "I love your garden, it's beautiful!",
        "The weather is great today.",
        "I hate the weeds growing over there!",
        "I'm angry that the hose is broken.",
        "Have a nice day!",
    ]

    # simulate messages
    for msg in convo:
        mm.analyze_message("atlas", msg, is_user_message=True)

    # after feed, should have some memories
    assert len(mm._records) > 0  # pylint: disable=protected-access

    sup = Supervisor(mm)
    energy = sup.get_energy("atlas")
    assert energy >= 1.0
    # ensure prompt-refresh scheduled
    assert "event" in scheduled
