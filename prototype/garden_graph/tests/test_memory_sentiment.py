"""
Tests for memory sentiment analysis and forgiveness/amplification.
"""
import pytest
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from garden_graph.memory.manager import MemoryManager, _analyze_sentiment


@pytest.fixture
def mm():
    return MemoryManager()


def test_sentiment_analysis():
    """Test basic sentiment analysis function."""
    # Positive sentiment
    assert _analyze_sentiment("I really love this, it's excellent!") > 0
    # Negative sentiment
    assert _analyze_sentiment("This is terrible, I hate it.") < 0
    # Neutral sentiment
    assert _analyze_sentiment("This is just a regular statement.") == 0
    
    # Test intensity
    strong_pos = _analyze_sentiment("I absolutely love this! It's wonderful, excellent, and makes me so happy!")
    mild_pos = _analyze_sentiment("I like this, it's good.")
    assert strong_pos > mild_pos > 0
    
    strong_neg = _analyze_sentiment("This is horrible! I hate it, it's awful and terrible!")
    mild_neg = _analyze_sentiment("I dislike this, it's not good.")
    assert strong_neg < mild_neg < 0


def test_forgiveness_amplification(mm):
    """Test the forgiveness and amplification mechanism."""
    # Create two memories with opposite sentiments
    mem_pos = mm.create(character_id="c", event_text="User was kind to me", sentiment=2)
    mem_neg = mm.create(character_id="c", event_text="User was rude to me", sentiment=-2)
    
    # Record initial weights
    pos_weight_before = mem_pos.weight
    neg_weight_before = mem_neg.weight
    
    # Apply opposite sentiment to positive memory (forgiveness)
    mm._apply_forgiveness_amplification("c", -2)
    
    # Check that positive memory weight decreased (forgiveness)
    assert mem_pos.weight < pos_weight_before
    # Check that negative memory weight increased (amplification)
    assert mem_neg.weight > neg_weight_before
    
    # Reset weights for next test
    mem_pos.weight = pos_weight_before
    mem_neg.weight = neg_weight_before
    
    # Apply positive sentiment (should have opposite effect)
    mm._apply_forgiveness_amplification("c", 2)
    
    # Check that positive memory weight increased (amplification)
    assert mem_pos.weight > pos_weight_before
    # Check that negative memory weight decreased (forgiveness)
    assert mem_neg.weight < neg_weight_before


def test_analyze_message(mm):
    """Test the analyze_message function for creating memories from messages."""
    # Test message that's too short
    result = mm.analyze_message("char1", "Short msg", is_user_message=True)
    assert result is None  # No memory should be created
    
    # Test neutral message
    result = mm.analyze_message("char1", "This is a regular message with no strong sentiment.", is_user_message=True)
    assert result is None  # No memory should be created
    
    # Test message with strong positive sentiment
    result = mm.analyze_message("char1", "I absolutely love talking to you! You're so helpful and kind!", is_user_message=True)
    assert result is not None  # Memory should be created
    memory = mm.get(result)
    assert memory.sentiment > 0
    
    # Test explicit #remember command
    result = mm.analyze_message("char1", "#remember This is important information to remember", is_user_message=True)
    assert result is not None
    memory = mm.get(result)
    assert "important information" in memory.event_text
    
    # Test Russian #запомни command
    result = mm.analyze_message("char1", "#запомни Это важная информация", is_user_message=True)
    assert result is not None
    memory = mm.get(result)
    assert "важная информация" in memory.event_text


def test_process_conversation_update(mm):
    """Test processing entire conversation updates."""
    # Test conversation with significant sentiment
    memories = mm.process_conversation_update(
        character_id="char1",
        user_message="I really enjoyed our conversation today, you're so helpful!",
        character_response="I'm glad you found our discussion valuable. I'm here to help anytime!",
    )
    
    # Should create at least one memory
    assert len(memories) > 0
    
    # Both messages have positive sentiment, so memory should be positive
    for mem_id in memories:
        memory = mm.get(mem_id)
        assert memory.sentiment > 0
