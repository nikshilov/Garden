"""Unit tests for Supervisor module."""

import importlib
from datetime import datetime, timedelta, timezone

import pytest

from garden_graph.memory.manager import MemoryManager, MemoryRecord
from garden_graph.supervisor import Supervisor


@pytest.fixture()
def mm():
    mm = MemoryManager()
    mm._records.clear()  # ensure empty
    return mm


def _add_memory(mm: MemoryManager, character: str, sentiment: int, weight: float = 0.5, days_ago: int = 0):
    rec = MemoryRecord(
        id=f"m{len(mm._records)+1}",
        character_id=character,
        event_text="stub",
        weight=weight,
        sentiment=sentiment,
        sentiment_label="test",
        emotions={},
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
        last_touched=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    mm._records[rec.id] = rec


def test_energy_calculation(mm):
    _add_memory(mm, "eve", 2, weight=1.0)
    _add_memory(mm, "eve", -1, weight=0.5)
    sup = Supervisor(mm)
    energy = sup.get_energy("eve")
    # expected: |2|*1 + | -1|*0.5 = 2 + 0.5 = 2.5
    assert abs(energy - 2.5) < 1e-6


def test_prompt_refresh(monkeypatch, mm):
    # lower threshold to 1.0 for test
    monkeypatch.setenv("PROMPT_REFRESH_ENERGY_THRESHOLD", "1.0")
    # reload config and supervisor to adopt new env var
    import garden_graph.config as cfg
    importlib.reload(cfg)
    import garden_graph.supervisor as sup_mod
    importlib.reload(sup_mod)

    # re-import supervisor class after reload
    SupervisorReloaded = sup_mod.Supervisor

    # create memory to exceed energy
    _add_memory(mm, "atlas", 2, weight=1.0)
    sup = SupervisorReloaded(mm)

    # Monkeypatch scheduler to capture calls
    called = {}
    def fake_schedule_event(**kwargs):
        called['ok'] = True
        return "evt-1"
    mm.scheduler.schedule_event = fake_schedule_event  # type: ignore

    assert sup.maybe_schedule_prompt_refresh("atlas") is True
    assert called.get('ok') is True


def test_evaluate_message(monkeypatch, mm):
    sup = Supervisor(mm)
    # patch analyze to return specific score
    monkeypatch.setattr(mm, "_analyze_message_llm", lambda cid, txt, llm=None: (1.2, "test", {}))
    res = sup.evaluate_message("eve", "hi")
    assert res["action"] == "highlight"
    assert res["score"] == 1.2
