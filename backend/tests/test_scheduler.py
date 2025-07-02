"""
Tests for the EventScheduler in garden_graph.memory.scheduler.
"""
import unittest
import os
import json
import tempfile
from datetime import datetime, timedelta, timezone

from garden_graph.memory.scheduler import EventScheduler, ScheduledEvent

class TestEventScheduler(unittest.TestCase):
    """Test cases for EventScheduler functionality."""
    
    def setUp(self):
        """Set up temporary file for events."""
        self.temp_dir = tempfile.mkdtemp()
        self.events_file = os.path.join(self.temp_dir, "test_events.json")
        self.scheduler = EventScheduler(self.events_file)
        
    def tearDown(self):
        """Clean up temp files."""
        if os.path.exists(self.events_file):
            os.remove(self.events_file)
        os.rmdir(self.temp_dir)
    
    def test_schedule_event_basic(self):
        """Test scheduling a basic event."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(hours=1)
        
        event_id = self.scheduler.schedule_event(
            character_id="eve",
            event_time=future,
            description="Test meeting"
        )
        
        self.assertIsNotNone(event_id)
        self.assertEqual(len(self.scheduler._events), 1)
        self.assertEqual(self.scheduler._events[event_id].character_id, "eve")
        self.assertEqual(self.scheduler._events[event_id].description, "Test meeting")
    
    def test_save_and_load_events(self):
        """Test saving and loading events."""
        # Create an event
        now = datetime.now(timezone.utc)
        future = now + timedelta(hours=1)
        
        event_id = self.scheduler.schedule_event(
            character_id="eve",
            event_time=future,
            description="Test meeting"
        )
        
        # Save events to file
        self.scheduler.save_to_file(self.events_file)
        
        # Create a new scheduler that loads from file
        new_scheduler = EventScheduler(self.events_file)
        
        # Check if event was loaded correctly
        self.assertEqual(len(new_scheduler._events), 1)
        self.assertIn(event_id, new_scheduler._events)
        self.assertEqual(new_scheduler._events[event_id].description, "Test meeting")
    
    def test_get_pending_events(self):
        """Test retrieving pending events."""
        now = datetime.now(timezone.utc)
        
        # Create events in the past, present, and future
        past = now - timedelta(hours=1)
        future = now + timedelta(hours=1)
        
        past_id = self.scheduler.schedule_event(
            character_id="eve",
            event_time=past,
            description="Past event"
        )
        
        future_id = self.scheduler.schedule_event(
            character_id="eve",
            event_time=future,
            description="Future event"
        )
        
        # Get pending events (should include past events)
        pending = self.scheduler.get_pending_events(now)
        
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].id, past_id)
    
    def test_get_pending_reminders(self):
        """Test retrieving pending reminders."""
        now = datetime.now(timezone.utc)
        
        # Create an event with reminder
        event_time = now + timedelta(hours=1)
        reminder_time = now - timedelta(minutes=5)  # Reminder time in the past
        
        event_id = self.scheduler.schedule_event(
            character_id="eve",
            event_time=event_time,
            description="Event with reminder",
            reminder_minutes=65  # 1h5m before event, which is 5 min ago
        )
        
        # Calculate reminder time in scheduler
        event = self.scheduler._events[event_id]
        self.assertIsNotNone(event.reminder_time)
        
        # Time difference should be around 5 min (plus/minus a few seconds for test execution)
        time_diff = (event.reminder_time - reminder_time).total_seconds()
        self.assertLess(abs(time_diff), 10)  # Less than 10 seconds difference
        
        # Get pending reminders
        reminders = self.scheduler.get_pending_reminders(now)
        
        self.assertEqual(len(reminders), 1)
        self.assertEqual(reminders[0].id, event_id)
    
    def test_mark_event_completed(self):
        """Test marking events as completed."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(hours=1)
        
        event_id = self.scheduler.schedule_event(
            character_id="eve",
            event_time=future,
            description="Test meeting"
        )
        
        # Mark as completed
        result = self.scheduler.mark_event_completed(event_id, user_responded=True)
        self.assertTrue(result)
        
        # Verify event is marked as completed
        self.assertTrue(self.scheduler._events[event_id].completed)
        self.assertTrue(self.scheduler._events[event_id].user_responded)
        
        # Completed events should not be in pending list
        pending = self.scheduler.get_pending_events(future + timedelta(hours=1))
        self.assertEqual(len(pending), 0)
    
    def test_extract_event_details(self):
        """Test extracting event details from text."""
        # Since this relies on LLM, we'll test the fallback regex
        text = "Давай встретимся завтра в 15:00 чтобы обсудить проект"
        
        details = self.scheduler._extract_event_details_regex(text)
        
        self.assertIsNotNone(details)
        self.assertIn("description", details)
        self.assertIn("event_time", details)
        
        # The description should contain the meeting topic
        self.assertIn("проект", details["description"])
        
        # Test another format
        text2 = "Remind me at 9:30 about the conference call"
        details2 = self.scheduler._extract_event_details_regex(text2)
        
        self.assertIsNotNone(details2)
        self.assertIn("conference call", details2["description"])

if __name__ == "__main__":
    unittest.main()
