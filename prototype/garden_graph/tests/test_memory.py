import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import math
from datetime import datetime, timezone, timedelta

import pytest

from garden_graph.memory.manager import MemoryManager, MIN_ACTIVE_WEIGHT


@pytest.fixture
def mm():
    return MemoryManager()


def test_crud_cycle(mm):
    rec = mm.create(character_id="char1", event_text="hello", sentiment=1)
    assert mm.get(rec.id) is rec

    mm.update(rec.id, weight=0.8, event_text="hi")
    assert math.isclose(mm.get(rec.id).weight, 0.8, rel_tol=1e-6)
    assert mm.get(rec.id).event_text == "hi"

    assert mm.delete(rec.id) is True
    assert mm.get(rec.id) is None


def test_top_k_order(mm):
    # weights 0.9, 0.3, 0.6 → expect order 0.9, 0.6, 0.3
    mm.create(character_id="c", event_text="a", sentiment=3)  # 0.9
    mm.create(character_id="c", event_text="b", sentiment=1)  # 0.3
    mm.create(character_id="c", event_text="c", sentiment=2)  # 0.6
    weights = [r.weight for r in mm.top_k("c", k=3)]
    assert weights == sorted(weights, reverse=True)


def test_decay_archives(mm):
    rec = mm.create(character_id="c", event_text="old", sentiment=1)  # 0.3
    rec.last_touched = datetime.now(timezone.utc) - timedelta(days=200)
    mm.decay_all()
    assert rec.archived is True
    assert rec.effective_weight() < MIN_ACTIVE_WEIGHT


def test_reflect_stub(mm):
    rec_pos = mm.create(character_id="c", event_text="nice", sentiment=1)
    rec_neg = mm.create(character_id="c", event_text="bad", sentiment=-1)

    w_pos_before = rec_pos.weight
    w_neg_before = rec_neg.weight

    mm.reflect_stub("c", context="bla")

    assert rec_pos.weight > w_pos_before
    assert rec_neg.weight < w_neg_before
