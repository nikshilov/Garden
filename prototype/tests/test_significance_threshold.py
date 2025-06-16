"""Unit tests for configurable memory significance threshold.

These tests verify that MemoryManager respects the MEM_SIGNIFICANCE_THRESHOLD
setting coming from ``garden_graph.config`` (which itself reads the
``MEM_SIGNIFICANCE_THRESHOLD`` environment variable).
"""

import importlib
import os
from typing import Optional

import pytest

# Helper -----------------------------------------------------------

def _fresh_manager() -> "MemoryManager":
    from garden_graph.memory.manager import MemoryManager  # local import to capture reloads

    mm = MemoryManager()
    mm._records.clear()
    return mm


def _analyze(mm: "MemoryManager", sig: float, llm: Optional[object] = None):
    """Call analyze_message with a stub significance value by patching
    the private _analyze_message_llm to return (sig, "test", {})."""

    original = mm._analyze_message_llm
    mm._analyze_message_llm = lambda cid, text, llm=None: (sig, "test", {})
    try:
        return mm.analyze_message("eve", "dummy text", is_user_message=True, llm=None)
    finally:
        mm._analyze_message_llm = original


# Tests ------------------------------------------------------------

@pytest.mark.parametrize("threshold,significance,should_create", [
    (0.9, 0.5, False),   # Below threshold, no memory
    (0.1, 0.5, True),    # Above threshold, create memory
])

def test_mem_threshold(monkeypatch, threshold, significance, should_create):
    # Set env var before (re)importing config & manager
    monkeypatch.setenv("MEM_SIGNIFICANCE_THRESHOLD", str(threshold))

    # Reload config to pick up new env var
    import garden_graph.config as config
    importlib.reload(config)

    # Reload manager so the constants are re-read
    import garden_graph.memory.manager as manager_module
    importlib.reload(manager_module)

    mm = _fresh_manager()

    mem_id = _analyze(mm, significance)

    if should_create:
        assert mem_id is not None and len(mm._records) == 1
    else:
        assert mem_id is None and len(mm._records) == 0
