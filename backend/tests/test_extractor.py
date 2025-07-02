"""Tests for MessageSignificanceExtractor"""

import importlib

from garden_graph.memory.extractor import MessageSignificanceExtractor
from garden_graph.memory.manager import MemoryManager


def _fresh_mm():
    mm = MemoryManager()
    mm._records.clear()
    return mm


def test_extract_indices(monkeypatch):
    mm = _fresh_mm()

    # Patch analysis to return predictable scores
    scores = [0.1, 0.8, -0.9, 0.2]
    def fake_analyze(cid, text, llm=None):
        return scores.pop(0), "cat", {}
    monkeypatch.setattr(mm, "_analyze_message_llm", fake_analyze)

    extractor = MessageSignificanceExtractor(mm, threshold=0.5)
    msgs = ["a", "b", "c", "d"]
    idx = extractor.extract("eve", msgs)

    assert idx == [1, 2]
