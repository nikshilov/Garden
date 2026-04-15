"""
Tests for the reflection subsystem in garden_graph.memory.reflection
"""
import os
import sys
import tempfile
import json
from pathlib import Path
import datetime as dt
from unittest import mock

import pytest

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from garden_graph.memory.reflection import ReflectionRecord, ReflectionManager
from garden_graph.memory.manager import MemoryRecord

# Test fixture for temp directory
@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

# Sample memory records for testing
@pytest.fixture
def memory_records():
    now = dt.datetime.now(dt.timezone.utc)
    return [
        MemoryRecord(
            id=f"mem_{i}",
            character_id="test_char",
            event_text=f"Test memory {i}",
            sentiment=1 if i % 2 == 0 else -1,
            sentiment_label="positive" if i % 2 == 0 else "negative",
            weight=0.8 - (i * 0.1),
            created_at=now,
            last_touched=now,
            archived=False,
            emotions={"joy": 0.8} if i % 2 == 0 else {"anger": 0.7}
        )
        for i in range(3)
    ]

def test_reflection_record_creation():
    """Test creating a ReflectionRecord with basic properties"""
    reflection = ReflectionRecord.create(
        source_mem_ids=["mem_1", "mem_2"],
        summary="These memories show a pattern of interest in AI",
        traits_delta={"curiosity": 0.2, "intelligence": 0.1}
    )
    
    assert reflection.id is not None
    assert len(reflection.id) > 0
    assert reflection.created_at is not None
    assert reflection.source_mem_ids == ["mem_1", "mem_2"]
    assert reflection.summary == "These memories show a pattern of interest in AI"
    assert reflection.traits_delta == {"curiosity": 0.2, "intelligence": 0.1}

def test_reflection_manager_persistence(temp_dir):
    """Test saving and loading reflection records"""
    manager = ReflectionManager(temp_dir)
    
    # Create and save a reflection
    reflection = ReflectionRecord.create(
        source_mem_ids=["mem_1"],
        summary="Test reflection",
        traits_delta={"empathy": 0.5}
    )
    manager._reflections["test_char"] = [reflection]
    manager.save("test_char")
    
    # Check if file exists
    assert (temp_dir / "reflections_test_char.json").exists()
    
    # Create new manager and load
    new_manager = ReflectionManager(temp_dir)
    new_manager.load("test_char")
    
    # Check loaded data
    assert len(new_manager._reflections["test_char"]) == 1
    loaded = new_manager._reflections["test_char"][0]
    assert loaded.id == reflection.id
    assert loaded.summary == "Test reflection"
    assert loaded.traits_delta == {"empathy": 0.5}

def test_reflection_trigger(temp_dir, memory_records):
    """Test triggering reflection after threshold is reached"""
    manager = ReflectionManager(temp_dir)
    
    # Add memories up to threshold
    for i in range(ReflectionManager.REFLECTION_THRESHOLD - 1):
        manager.on_new_memory("test_char")
    
    # Check no reflection triggered yet
    reflection = manager.maybe_reflect("test_char", memory_records)
    assert reflection is None
    assert "test_char" not in manager._reflections
    
    # Add one more memory to reach threshold
    manager.on_new_memory("test_char")
    reflection = manager.maybe_reflect("test_char", memory_records)
    
    # Now should have reflection
    assert reflection is not None
    assert "test_char" in manager._reflections
    assert len(manager._reflections["test_char"]) == 1
    assert len(reflection.source_mem_ids) == len(memory_records)
    
    # Counter should reset
    assert manager._mem_counter["test_char"] == 0

def test_last_summaries(temp_dir):
    """Test retrieving last N reflection summaries"""
    manager = ReflectionManager(temp_dir)
    
    # Create several reflections
    reflections = [
        ReflectionRecord.create(
            source_mem_ids=[f"mem_{i}"],
            summary=f"Reflection {i}",
            traits_delta={"trait_{i}": 0.1 * i}
        )
        for i in range(5)
    ]
    
    manager._reflections["test_char"] = reflections
    
    # Get last 3
    summaries = manager.last_summaries("test_char", 3)
    assert len(summaries) == 3
    assert summaries == ["Reflection 2", "Reflection 3", "Reflection 4"]
    
    # Get with empty reflections
    assert manager.last_summaries("nonexistent") == []

def test_integration_with_memory_manager(temp_dir):
    """Test integration between MemoryManager and ReflectionManager"""
    # We need to patch the ReflectionManager before importing MemoryManager
    with mock.patch("garden_graph.memory.manager.ReflectionManager") as mock_refl_mgr:
        from garden_graph.memory.manager import MemoryManager
        
        mock_instance = mock_refl_mgr.return_value
        mock_instance.on_new_memory.return_value = None
        mock_instance.maybe_reflect.return_value = None
        mock_instance.last_summaries.return_value = ["Reflection 1", "Reflection 2"]
        
        # Also patch save_to_file to avoid actual file operations
        with mock.patch.object(MemoryManager, 'save_to_file', return_value=True):
            # Create memory manager with temp directory
            mem_dir = temp_dir / "memories.json"
            mem_manager = MemoryManager(str(mem_dir))
            
            # Verify ReflectionManager was created
            mock_refl_mgr.assert_called_once()
            
            # Create a memory and verify reflection updates
            mem_manager.create(
                character_id="test_char",
                event_text="Test memory for reflection",
                sentiment=1,
                sentiment_label="positive"
            )
        
        # Verify reflection methods were called
        mock_instance.on_new_memory.assert_called_with("test_char")
        mock_instance.maybe_reflect.assert_called_once()
        
        # Test prompt segment includes reflections
        mock_instance.last_summaries.return_value = ["Reflection 1", "Reflection 2"]
        prompt = mem_manager.prompt_segment("test_char")
        assert "REFLECTIONS:" in prompt
        assert "• Reflection 1" in prompt
        assert "• Reflection 2" in prompt
