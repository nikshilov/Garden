import pytest
from garden_graph.memory.manager import MemoryManager
from unittest.mock import patch

CHAR_ID = "eve"

@pytest.fixture()
def mem_mgr():
    """Return a fresh in-memory MemoryManager with monkey-patched helpers.
    We disable external persistence backends and heavy LLM calls so the tests
    run entirely offline and deterministically.
    """
    mm = MemoryManager(autoload=False)

    # Stub out costly / random helpers to deterministic versions
    mm._compute_novelty = lambda cid, text, window=20: 1.0  # type: ignore
    mm._get_personal_factor = lambda cid, cat: 1.0  # type: ignore
    mm._summarize_text = lambda txt, max_length=200, llm=None: txt  # type: ignore
    # Force high significance so memories are always created
    mm._analyze_message_llm = lambda cid, text, llm=None: (1.0, "general", {})  # type: ignore
    return mm


def _patch_mood(mm: MemoryManager, **axes):
    """Monkey-patch _get_mood_vector on the given manager to return axes."""
    mm._get_mood_vector = lambda cid: axes  # type: ignore


def test_bias_factor_weight(mem_mgr):
    """Positive valence+flirt should yield higher initial weight than shadow-heavy mood."""
    # First scenario: positive mood (valence & flirt)
    _patch_mood(mem_mgr, valence=0.4, flirt=0.4, shadow=0.0)
    rec_id = mem_mgr.analyze_message(CHAR_ID, "A memorable event")
    assert rec_id is not None, "memory not created"
    pos_weight = mem_mgr.get(rec_id).weight  # type: ignore

    # Second scenario: shadow-weighted negative bias
    _patch_mood(mem_mgr, valence=0.0, flirt=0.0, shadow=0.4)
    rec_id2 = mem_mgr.analyze_message(CHAR_ID, "Another event")
    assert rec_id2 is not None
    neg_weight = mem_mgr.get(rec_id2).weight  # type: ignore

    assert pos_weight > neg_weight, (
        f"Expected weight to be greater with positive valence/flirt (got {pos_weight:.3f} vs {neg_weight:.3f})"
    )


def test_shadow_amplifies_negative_relationship(mem_mgr):
    """Negative relationship deltas should be magnified when shadow is high."""
    # Baseline with no shadow
    _patch_mood(mem_mgr, shadow=0.0)
    emotions = {"sadness": 1.0}  # maps to affection -0.4 in EMOTION_AXIS_WEIGHTS
    mem_mgr._update_relationship(CHAR_ID, emotions, category="general", significance=-1.0, personal_factor=1.0)
    baseline_affection = mem_mgr.relationships[CHAR_ID]["affection"]

    # Reset relationships and run with shadow mood
    mem_mgr.relationships[CHAR_ID] = {ax: 0.0 for ax in mem_mgr.relationships[CHAR_ID]}
    _patch_mood(mem_mgr, shadow=0.5)
    mem_mgr._update_relationship(CHAR_ID, emotions, category="general", significance=-1.0, personal_factor=1.0)
    shadow_affection = mem_mgr.relationships[CHAR_ID]["affection"]

    assert abs(shadow_affection) > abs(baseline_affection), (
        "Shadow mood should amplify magnitude of negative relationship deltas"
    )
