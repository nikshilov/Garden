"""
Tests for memory persistence and file operations.
"""
import pytest
import os
import tempfile
import json
from datetime import datetime, timezone, timedelta
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from garden_graph.memory.manager import MemoryManager


@pytest.fixture
def mm_with_data():
    """Create a memory manager with test data."""
    mm = MemoryManager()
    mm.create(character_id="eve", event_text="User shared a happy story", sentiment=1)
    mm.create(character_id="atlas", event_text="User asked a scientific question", sentiment=0)
    mm.create(character_id="eve", event_text="User was argumentative", sentiment=-1)
    return mm


def test_save_and_load():
    """Test saving and loading memory records from file."""
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp:
        try:
            # Create memory manager and add test data
            mm_original = MemoryManager()
            rec1 = mm_original.create(character_id="eve", event_text="Test memory 1", sentiment=1)
            rec2 = mm_original.create(character_id="eve", event_text="Test memory 2", sentiment=-1)
            
            # Save to file
            mm_original.save_to_file(temp.name)
            
            # Ensure file exists and has content
            assert os.path.exists(temp.name)
            with open(temp.name, 'r') as f:
                data = json.load(f)
                assert len(data) == 2
                
            # Load into a new manager
            mm_loaded = MemoryManager.load_from_file(temp.name)
            
            # Verify data integrity
            assert len(mm_loaded._records) == 2
            assert mm_loaded.get(rec1.id) is not None
            assert mm_loaded.get(rec2.id) is not None
            assert mm_loaded.get(rec1.id).event_text == "Test memory 1"
            assert mm_loaded.get(rec2.id).event_text == "Test memory 2"
            
        finally:
            # Clean up
            if os.path.exists(temp.name):
                os.remove(temp.name)


def test_serialization_formats(mm_with_data):
    """Test that datetime objects are properly serialized and deserialized."""
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp:
        try:
            # Save to file
            mm_with_data.save_to_file(temp.name)
            
            # Check raw JSON format
            with open(temp.name, 'r') as f:
                data = json.load(f)
                # Verify datetimes are stored as ISO format strings
                for record_id, record in data.items():
                    assert isinstance(record['created_at'], str)
                    assert isinstance(record['last_touched'], str)
                    # Try parsing the ISO format
                    datetime.fromisoformat(record['created_at'])
                    datetime.fromisoformat(record['last_touched'])
            
            # Load back and check datetime objects
            mm_loaded = MemoryManager.load_from_file(temp.name)
            for rec_id, rec in mm_loaded._records.items():
                assert isinstance(rec.created_at, datetime)
                assert isinstance(rec.last_touched, datetime)
                
        finally:
            # Clean up
            if os.path.exists(temp.name):
                os.remove(temp.name)


def test_default_filepath():
    """Test the default filepath generation."""
    mm = MemoryManager()
    filepath = mm.get_default_filepath()
    
    # Should be in a data directory
    assert "data" in filepath
    assert filepath.endswith(".json")
    
    # Directory should exist
    directory = os.path.dirname(filepath)
    assert os.path.exists(directory)


def test_load_nonexistent_file():
    """Test loading from a nonexistent file returns an empty manager."""
    mm = MemoryManager.load_from_file("/path/that/does/not/exist.json")
    assert len(mm._records) == 0
