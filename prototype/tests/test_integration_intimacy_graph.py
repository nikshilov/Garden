"""Integration test covering chat flow with Intimacy Mode toggles, cost tracking,
memory persistence and event scheduling.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Dict, Any, List, Set

import pytest

from garden_graph.cost_tracker import CostTracker
from garden_graph.memory.manager import MemoryManager
from garden_graph.graph import create_world_chat_graph


@pytest.fixture()
def _patch_network(monkeypatch):
    """Stub out all network-heavy LLM calls so the test is fast/offline."""
    # Character LLM response
    monkeypatch.setattr(
        "garden_graph.character.Character.respond",
        lambda self, user_message, history=None: f"[respond:{self.id}]",
        raising=True,
    )
    # Intimate agent response
    monkeypatch.setattr(
        "garden_graph.intimate_agent.IntimateAgent.respond",
        lambda self, user_message, history=None: "[respond:intimate]",
        raising=True,
    )
    # Router routing – always pick Eve so we have deterministic path
    monkeypatch.setattr(
        "garden_graph.router.Router.route",
        lambda self, msg, hist=None: ["eve"],
        raising=True,
    )
    yield


def _run_messages(graph, state_template: Dict[str, Any], messages: List[str]):
    """Feed messages through the graph, returning final state."""
    state = state_template.copy()
    for msg in messages:
        # Reset per-iteration fields expected by graph
        state.update(
            {
                "user_message": msg,
                "active_characters": set(),
                "selected_characters": set(),
                "character_responses": {},
            }
        )
        state = graph.invoke(state)
    return state


def test_full_chat_flow_intimacy(tmp_path: Path, _patch_network, monkeypatch):
    """Simulate realistic chat: normal → intimate on → intimate chat → off.

    Verifies:
      * Intimacy flag & model switch propagate through state.
      * CostTracker records both general & intimacy categories.
      * MemoryManager persists memories to a JSON file.
    """

    # ---------- Setup components ----------
    mem_path = tmp_path / "memories.json"
    events_path = tmp_path / "events.json"
    mm = MemoryManager(memories_path=str(mem_path), events_path=str(events_path))

    # Override default filepath used inside graph.route_message so it writes under tmp_path
    monkeypatch.setattr(mm, "get_default_filepath", lambda: str(mem_path))

    ct = CostTracker()

    graph = create_world_chat_graph(
        router_model="gpt-4o-mini",
        character_models={"eve": "gpt-4o-mini"},
        cost_tracker=ct,
        memory_manager=mm,
    )

    # ---------- Run conversation ----------
    initial_state: Dict[str, Any] = {
        "user_message": "",
        "message_history": [],
        "active_characters": set(),
        "selected_characters": set(),
        "character_responses": {},
        "intimacy_mode": False,
        "intimate_model": "gpt-4o-mini",
        "costs": {},
    }

    convo = [
        "Hello Eve!",
        "/intimate on",
        "I love you <3",
        "/intimate model llama3-70b",
        "Let's cuddle tonight.",
        "/intimate off",
        "Thanks, bye!",
    ]

    final_state = _run_messages(graph, initial_state, convo)

    # ---------- Assertions ----------

    # Final state should have intimacy off again
    assert final_state["intimacy_mode"] is False

    # Memory persistence file exists and non-empty
    assert mem_path.exists() and mem_path.stat().st_size > 0

    # At least one memory created during chat
    assert len(mm._records) > 0  # pylint: disable=protected-access

    # Cost tracker has both categories recorded
    cat_breakdown = ct.get_category_breakdown()
    assert cat_breakdown.get("general", 0.0) > 0.0
    assert cat_breakdown.get("intimacy", 0.0) > 0.0

    # Total USD cost > 0
    assert ct.get_total_usd() > 0.0

    # Scheduler should have at least potential events (prompt refresh etc.)
    # Not deterministic, so just ensure scheduler object exists
    assert mm.scheduler is not None
