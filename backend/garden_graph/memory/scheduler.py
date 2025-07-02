"""Event scheduler for character interactions.

This module provides a calendar functionality for characters
to remember specific times when they should initiate interactions.
"""

import datetime
import json
import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


@dataclass
class ScheduledEvent:
    """Represents a scheduled event or appointment."""
    id: str
    character_id: str
    event_time: datetime.datetime
    description: str
    reminder_time: Optional[datetime.datetime] = None
    completed: bool = False
    user_responded: bool = False
    created_at: datetime.datetime = datetime.datetime.now(datetime.timezone.utc)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ScheduledEvent':
        """Create a ScheduledEvent from a dictionary."""
        # Convert string times back to datetime objects
        data['event_time'] = datetime.datetime.fromisoformat(data['event_time'])
        if data.get('reminder_time'):
            data['reminder_time'] = datetime.datetime.fromisoformat(data['reminder_time'])
        if data.get('created_at'):
            data['created_at'] = datetime.datetime.fromisoformat(data['created_at'])
        return cls(**data)


class EventScheduler:
    """Manages scheduled events for characters."""
    
    def __init__(self, filepath: Optional[str] = None, event_repo=None):
        """Initialize the event scheduler.
        
        Args:
            filepath: Path to load/save events from/to
        """
        self._events: Dict[str, ScheduledEvent] = {}
        self.repo = event_repo
        self.filepath = filepath

        # Pre-load persisted events
        if self.repo:
            try:
                for row in self.repo.load_all():
                    evt = ScheduledEvent.from_dict(row)
                    self._events[evt.id] = evt
            except Exception as err:  # pragma: no cover
                print(f"[EventScheduler] Failed to preload from Supabase: {err}")

        if filepath:
            self.load_from_file(filepath)
    
    def schedule_event(self, 
                      character_id: str, 
                      event_time: datetime.datetime, 
                      description: str,
                      reminder_minutes: Optional[int] = None) -> str:
        """Schedule a new event.
        
        Args:
            character_id: ID of the character scheduling the event
            event_time: When the event should occur
            description: Description of the event
            reminder_minutes: Optional minutes before event to send reminder
            
        Returns:
            ID of the created event
        """
        import uuid
        
        event_id = str(uuid.uuid4())
        reminder_time = None
        if reminder_minutes:
            reminder_time = event_time - datetime.timedelta(minutes=reminder_minutes)
            
        event = ScheduledEvent(
            id=event_id,
            character_id=character_id,
            event_time=event_time,
            description=description,
            reminder_time=reminder_time
        )
        
        self._events[event_id] = event

        # Persist to Supabase if configured
        if self.repo:
            try:
                from dataclasses import asdict
                self.repo.save(asdict(event))
            except Exception as err:  # pragma: no cover
                print(f"[EventScheduler] Supabase save error: {err}")

        if self.filepath:
            self.save_to_file(self.filepath)

        return event_id
    
    def get_pending_events(self, 
                          current_time: Optional[datetime.datetime] = None) -> List[ScheduledEvent]:
        """Get events that are due based on the current time.
        
        Args:
            current_time: Current time to check against, defaults to now
            
        Returns:
            List of events that are due
        """
        if current_time is None:
            current_time = datetime.datetime.now(datetime.timezone.utc)
            
        pending = []
        for event in self._events.values():
            if not event.completed and event.event_time <= current_time:
                pending.append(event)
                
        return pending
    
    def get_pending_reminders(self, 
                            current_time: Optional[datetime.datetime] = None) -> List[ScheduledEvent]:
        """Get reminders that are due based on the current time.
        
        Args:
            current_time: Current time to check against, defaults to now
            
        Returns:
            List of events with due reminders
        """
        if current_time is None:
            current_time = datetime.datetime.now(datetime.timezone.utc)
            
        pending = []
        for event in self._events.values():
            if (not event.completed and event.reminder_time and 
                event.reminder_time <= current_time < event.event_time):
                pending.append(event)
                
        return pending
    
    def mark_event_completed(self, event_id: str, user_responded: bool = True) -> bool:
        """Mark an event as completed.
        
        Args:
            event_id: ID of the event to mark
            user_responded: Whether the user responded to the event
            
        Returns:
            True if successful, False otherwise
        """
        if event_id not in self._events:
            return False
            
        self._events[event_id].completed = True
        self._events[event_id].user_responded = user_responded

        # Persist update to Supabase
        if self.repo:
            try:
                from dataclasses import asdict
                self.repo.save(asdict(self._events[event_id]))
            except Exception as err:  # pragma: no cover
                print(f"[EventScheduler] Supabase save error: {err}")

        if self.filepath:
            self.save_to_file(self.filepath)

        return True
    
    def get_events_for_character(self, character_id: str) -> List[ScheduledEvent]:
        """Get all events for a specific character.
        
        Args:
            character_id: ID of the character to get events for
            
        Returns:
            List of events for the character
        """
        return [
            event for event in self._events.values()
            if event.character_id == character_id
        ]
    
    def extract_event_details_from_text(self, text: str, llm=None) -> Optional[Dict]:
        """Extract event details from a text message using an LLM.
        
        Args:
            text: The message text to analyze
            llm: Language model to use for extraction
            
        Returns:
            Dictionary with extracted event details or None if no event found
        """
        if not llm:
            # Simple regex-based fallback when LLM is not available
            import re
            
            # Look for time patterns like "10:00", "10am", "10 am", etc.
            time_pattern = r'(\d{1,2})[:\s]?(\d{2})?\s*(am|pm|AM|PM)?'
            time_matches = re.findall(time_pattern, text)
            
            if not time_matches:
                return None
                
            # Basic extraction with defaults
            return {
                "event_time": datetime.datetime.now(datetime.timezone.utc).replace(
                    hour=int(time_matches[0][0]), 
                    minute=int(time_matches[0][1] or 0)
                ),
                "description": text[:100],  # Just use first 100 chars as description
                "reminder_minutes": 5  # Default 5 min reminder
            }
        
        try:
            # Use LLM to extract detailed event information
            messages = [
                {"role": "system", "content": """
                Extract scheduling information from the message.
                If there is a specific time mentioned for a meeting or event, extract it.
                If there is a reminder time or condition mentioned, extract it.
                Format your response as JSON with the following fields:
                {
                    "event_time": "YYYY-MM-DD HH:MM:SS",
                    "description": "Brief description of the event",
                    "reminder_minutes": Number of minutes before event for reminder (optional)
                }
                Return null if no scheduling information is found.
                """},
                {"role": "user", "content": text}
            ]
            
            response = llm.invoke(messages)
            
            # Extract JSON from response
            import re
            import json
            
            match = re.search(r'{.*}', response.content, re.DOTALL)
            if not match:
                return None
                
            event_data = json.loads(match.group(0))
            
            # Convert string time to datetime
            if "event_time" in event_data:
                event_data["event_time"] = datetime.datetime.fromisoformat(event_data["event_time"])
                
            return event_data
            
        except Exception as e:
            print(f"Error extracting event details: {e}")
            return None
    
    # -----------------------------------------------------------------
    # Backward-compatibility: earlier code/tests expected a private
    # `_extract_event_details_regex` method for regex-only extraction.
    # It now simply delegates to the public method with `llm=None`.
    def _extract_event_details_regex(self, text: str):
        """Legacy wrapper – retained for test suite compatibility."""
        return self.extract_event_details_from_text(text, llm=None)
    
    def save_to_file(self, filepath: str) -> bool:
        """Save scheduled events to a JSON file.
        
        Args:
            filepath: Path to save the events to
            
        Returns:
            True if successful, False otherwise
        """
        try:
            import os
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Convert to serializable format
            serializable_events = {}
            for eid, event in self._events.items():
                ev_dict = asdict(event)
                # Convert datetime objects to ISO format strings
                ev_dict['event_time'] = ev_dict['event_time'].isoformat()
                if ev_dict['reminder_time']:
                    ev_dict['reminder_time'] = ev_dict['reminder_time'].isoformat()
                ev_dict['created_at'] = ev_dict['created_at'].isoformat()
                serializable_events[eid] = ev_dict
            
            # Write to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(serializable_events, f, indent=2, ensure_ascii=False)
                
            print(f"Saved {len(serializable_events)} scheduled events to {filepath}")
            return True
            
        except Exception as e:
            print(f"Error saving scheduled events: {e}")
            return False
    
    def load_from_file(self, filepath: str) -> bool:
        """Load scheduled events from a JSON file.
        
        Args:
            filepath: Path to load the events from
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(filepath):
                print(f"Events file not found: {filepath}")
                return False
                
            with open(filepath, 'r', encoding='utf-8') as f:
                events_data = json.load(f)
                
            self._events = {}
            for eid, event_data in events_data.items():
                self._events[eid] = ScheduledEvent.from_dict(event_data)
                
            print(f"Loaded {len(self._events)} scheduled events from {filepath}")
            return True
            
        except Exception as e:
            print(f"Error loading scheduled events: {e}")
            return False
