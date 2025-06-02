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


def test_reflect_fallback(mm):
    """Test the fallback reflection mechanism."""
    rec_pos = mm.create(character_id="c", event_text="nice weather today", sentiment=1)
    rec_neg = mm.create(character_id="c", event_text="bad experience yesterday", sentiment=-1)

    w_pos_before = rec_pos.weight
    w_neg_before = rec_neg.weight

    # Use context with some common words
    mm._reflect_fallback("c", context="The weather today is really nice")

    # Positive memory with common words should increase in weight
    assert rec_pos.weight > w_pos_before
    # Negative memory tends to decrease unless highly relevant
    assert rec_neg.weight < w_neg_before


def test_count_common_words(mm):
    """Test the word similarity counting function."""
    text1 = "The quick brown fox jumps over the lazy dog"
    text2 = "My quick brown dog is playing in the yard"
    text3 = "Something completely different and unrelated"
    
    assert mm._count_common_words(text1, text2) > 0  # Should have common words
    assert mm._count_common_words(text1, text3) == 0  # Should have no common words
    assert mm._count_common_words(text1, text1) >= 5  # Identical text has 5+ common words


def test_build_reflection_prompt(mm):
    """Test that the reflection prompt is correctly built."""
    # Create some test memories
    rec1 = mm.create(character_id="c", event_text="memory one", sentiment=1)
    rec2 = mm.create(character_id="c", event_text="memory two", sentiment=-1)
    
    memories = [rec1, rec2]
    context = "test context"
    
    prompt = mm._build_reflection_prompt(context, memories)
    
    # Check that the prompt contains essential elements
    assert "memory one" in prompt
    assert "memory two" in prompt
    assert rec1.id in prompt
    assert rec2.id in prompt
    assert "JSON" in prompt  # Should mention JSON format


def test_reflection_with_llm(mm):
    """Test reflection with a mock LLM."""
    from unittest.mock import MagicMock
    
    # Create test memories
    rec1 = mm.create(character_id="c", event_text="user complimented me", sentiment=2)
    rec2 = mm.create(character_id="c", event_text="user criticized my answer", sentiment=-1)
    
    # Initial weights
    w1_before = rec1.weight
    w2_before = rec2.weight
    
    # Create a mock LLM that returns a valid response
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = f'[{{"id": "{rec1.id}", "newWeight": 0.9}}, {{"id": "{rec2.id}", "newWeight": 0.3}}]'
    mock_llm.invoke.return_value = mock_response
    
    # Context that's relevant to rec1 but not rec2
    context = "You're doing a great job!"
    
    # Run reflection with our mock LLM
    updates = mm.reflect("c", context, llm=mock_llm)
    
    # Verify expected behavior
    assert len(updates) == 2
    assert updates[0][0] == rec1.id
    assert updates[1][0] == rec2.id
    
    # Weights should be updated according to mock response
    assert rec1.weight == 0.9
    assert rec2.weight == 0.3


def test_reflection_json_parsing(mm):
    """Test parsing of various JSON formats in reflection responses."""
    # Create a test memory
    rec = mm.create(character_id="c", event_text="test memory", sentiment=1)
    
    # Test different JSON formats
    valid_json = f'[{{"id": "{rec.id}", "newWeight": 0.75}}]'
    updates = mm._parse_reflection_response(valid_json, [rec])
    assert len(updates) == 1
    assert updates[0][0] == rec.id
    assert updates[0][1] == 0.75
    
    # Test with JSON embedded in text
    embedded_json = f'Here is my analysis: [{{"id": "{rec.id}", "newWeight": 0.6}}]. Hope this helps!'
    updates = mm._parse_reflection_response(embedded_json, [rec])
    assert len(updates) == 1
    assert updates[0][1] == 0.6
    
    # Test with invalid JSON
    invalid_json = "This is not valid JSON"
    updates = mm._parse_reflection_response(invalid_json, [rec])
    assert len(updates) == 1  # Should fall back to returning original memories with no changes
    assert updates[0][0] == rec.id
    assert updates[0][1] == rec.weight  # Weight should be unchanged
