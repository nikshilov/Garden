"""Tests for Intimacy Mode and cost categories."""
from __future__ import annotations

import importlib
import os
from types import SimpleNamespace

import pytest

# Force safe env for tests
os.environ["SAFE_MODE"] = "false"


def test_intimate_agent_model_switch(monkeypatch):
    """IntimateAgent should honour model override and env variable."""
    from garden_graph.intimate_agent import IntimateAgent

    # default from config.yaml
    default_agent = IntimateAgent()
    assert default_agent.model_name  # some non empty

    # via argument
    agent2 = IntimateAgent(model_name="grok-1")
    assert agent2.model_name == "grok-1"

    # via env
    monkeypatch.setenv("INTIMATE_MODEL", "mixtral-8x7b")
    ia_mod = importlib.reload(importlib.import_module("garden_graph.intimate_agent"))
    agent3 = ia_mod.IntimateAgent()
    assert agent3.model_name == "mixtral-8x7b"


def test_cost_tracker_categories():
    """CostTracker should aggregate cost by category."""
    from garden_graph.cost_tracker import CostTracker

    ct = CostTracker()
    ct.record("gpt-4o", 1000, 1000, category="general")
    ct.record("llama3-70b", 500, 500, category="intimacy")

    breakdown = ct.get_category_breakdown()
    assert breakdown["general"] > 0
    assert breakdown["intimacy"] > 0
    assert len(breakdown) == 2


def test_intimacy_command_state(monkeypatch):
    """Graph should toggle intimacy flag when '/intimate on|off' command is used."""
    from garden_graph.graph import create_world_chat_graph
    from garden_graph.cost_tracker import CostTracker

    # patch IntimateAgent.respond to avoid network
    monkeypatch.setattr(
        "garden_graph.intimate_agent.IntimateAgent.respond",
        lambda self, user_message, history=None: "[stub intimate response]",
        raising=True,
    )

    graph = create_world_chat_graph(
        router_model="gpt-4o-mini",
        character_models={"eve": "gpt-4o-mini"},
        cost_tracker=CostTracker(),
        memory_manager=None,
    )

    state = {
        "user_message": "/intimate on",
        "message_history": [],
        "active_characters": set(),
        "selected_characters": set(),
        "character_responses": {},
        "intimacy_mode": False,
        "costs": {},
    }

    new_state = graph.invoke(state)
    assert new_state["intimacy_mode"] is True

    # turn it off
    state["user_message"] = "/intimate off"
    off_state = graph.invoke(state)
    assert off_state["intimacy_mode"] is False
