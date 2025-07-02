"""In-memory MemoryManager implementation for Phase P2 (MVP).

Follows docs/memory_algorithm.md.  Datastore is a simple dict keyed by
UUID.  Easy to unit-test and can be swapped for persistent storage later.
"""
from __future__ import annotations

import uuid, math, re, os, json
from dataclasses import dataclass, asdict, field

# Configurable thresholds
from garden_graph.config import MEM_SIGNIFICANCE_THRESHOLD, EMOTIONAL_IMPACT_THRESHOLD
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import math

from .scheduler import EventScheduler
from .reflection import ReflectionManager

# storage backends
from garden_graph.config import STORAGE_BACKEND, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
try:
    from garden_graph.storage.supabase_repository import (
        SupabaseMemoryRepo,
        SupabaseEventRepo,
    )
except Exception:
    SupabaseMemoryRepo = None  # type: ignore
    SupabaseEventRepo = None  # type: ignore
from collections import defaultdict
from pathlib import Path

# Supervisor
from garden_graph.supervisor import Supervisor

DECAY_LAMBDA = 0.05        # ≈ half-life 13.9 days
MIN_ACTIVE_WEIGHT = 0.05   # below this we archive

# New constants for emotional memory weighting
PERSONAL_SENSITIVITY = {
    "eve": {"praise": 1.2, "insult": 1.5, "affection": 1.3},
    "atlas": {"praise": 1.1, "insult": 1.4, "affection": 1.0},
}

RELATIONSHIP_DECAY = 0.0005  # daily passive decay toward 0

# Meta key in relationships.json to store housekeeping info
_REL_META_KEY = "__meta__"

# --- Relationship axes configuration ---
RELATIONSHIP_AXES = [
    "affection", "trust", "respect", "familiarity", "tension",
    "empathy", "engagement", "security", "autonomy", "admiration"
]

# Mapping from message category to relationship axes (coarse fallback)
CATEGORY_AXIS_WEIGHTS = {
    "praise": {"affection": 0.4, "respect": 0.4, "admiration": 0.3},
    "insult": {"tension": 0.6, "affection": -0.4, "respect": -0.4},
    "affection": {"affection": 0.5, "empathy": 0.3, "trust": 0.3},
    "important fact": {"familiarity": 0.4},
}

# Fine-grained mapping from Plutchik emotions to axes
EMOTION_AXIS_WEIGHTS = {
    "joy": {"affection": 0.4, "engagement": 0.2},
    "trust": {"trust": 0.6, "security": 0.3},
    "fear": {"tension": 0.5, "security": -0.3},
    "surprise": {"engagement": 0.4},
    "sadness": {"affection": -0.4, "empathy": 0.3},
    "disgust": {"tension": 0.5, "affection": -0.4},
    "anger": {"tension": 0.7, "respect": -0.3, "affection": -0.4},
    "anticipation": {"engagement": 0.3, "autonomy": 0.2},
}

# decay rate for memory weight per day (used in MemoryRecord.effective_weight)
WEIGHT_DECAY = 0.02  # 2% per day exponential

@dataclass
class MemoryRecord:
    id: str
    character_id: str
    event_text: str
    weight: float          # initial weight w0
    sentiment: int         # –2 .. +2
    sentiment_label: str   # label for sentiment (e.g. 'positive', 'negative', 'neutral')
    created_at: datetime
    last_touched: datetime
    archived: bool = False
    emotions: Dict[str, float] = field(default_factory=dict)  # multi-vector emotion intensities

    # ------- helpers -------
    def effective_weight(self) -> float:
        """Return weight after applying exponential decay since last_touched."""
        now = datetime.now(timezone.utc)
        days = (now - self.last_touched).total_seconds() / 86400.0
        if days <= 0:
            return self.weight
        return self.weight * math.exp(-WEIGHT_DECAY * days)


def _initial_weight(sentiment: int, user_flag: bool = False) -> float:
    """Calculate initial weight based on sentiment and user flag.
    
    Args:
        sentiment: Sentiment value (-2 to +2)
        user_flag: Whether this memory was explicitly flagged by user
        
    Returns:
        Initial weight value between 0.1 and 1.0
    """
    w0 = abs(sentiment) * 0.3
    if user_flag:
        w0 += 0.4
    return max(0.1, min(1.0, w0))


def _analyze_sentiment(text: str, llm=None, character_id: str = None) -> int:
    """Analyze the importance of a message based on context and character personality.
    
    Args:
        text: Text to analyze
        llm: Optional LLM to use for analysis
        character_id: ID of the character to consider personality traits
        
    Returns:
        Importance value: -2 (very negative impact) to +2 (very positive impact)
    """
    # Use LLM if available - this is the preferred method
    if llm:
        try:
            print(f"[MemoryManager] Using LLM for sentiment analysis for character {character_id}")
            
            # Get character traits if available
            character_context = ""
            if character_id == "eve":
                character_context = "You are Eve, a deeply curious and emotionally intelligent being who values empathy, connection, and learning."
            elif character_id == "atlas":
                character_context = "You are Atlas, a logical, analytical being who values knowledge, precision, and problem-solving."
            
            messages = [
                {"role": "system", "content": f"""
                {character_context}
                Analyze the importance of the following message for your character.
                Consider:
                1. How emotionally significant is this message for you? 
                2. Does it relate to your core values or interests?
                3. How memorable would this interaction be for you?
                
                Rate the importance on a scale from -2 to +2:
                -2: Very negative/distressing event worth remembering
                -1: Somewhat negative event
                0: Neutral/forgettable event
                +1: Somewhat positive/interesting event
                +2: Very positive/significant event worth remembering
                
                Respond ONLY with a single number (-2, -1, 0, 1, or 2).
                """}, 
                {"role": "user", "content": text}
            ]
            
            response = llm.invoke(messages)
            try:
                # Extract just the numeric value
                sentiment = int(response.content.strip())
                # Validate it's in our expected range
                if sentiment < -2:
                    sentiment = -2
                elif sentiment > 2:
                    sentiment = 2
                print(f"[MemoryManager] LLM determined importance: {sentiment} for character {character_id}")
                return sentiment
            except ValueError:
                print(f"[MemoryManager] Could not parse LLM sentiment response: '{response.content}'")
                # Fall through to keyword-based analysis
        except Exception as e:
            print(f"[MemoryManager] Error in LLM sentiment analysis: {e}")
            # Fall through to keyword-based analysis
    
    # Keyword-based sentiment analysis with intensity levels - English
    strong_positive = set(['love', 'adore', 'amazing', 'wonderful', 'fantastic', 'excellent', 'great', 'awesome'])
    mild_positive = set(['good', 'nice', 'like', 'pleased', 'satisfied', 'helpful', 'enjoy', 'enjoyed', 'appreciate'])
    
    strong_negative = set(['hate', 'terrible', 'awful', 'horrible', 'worst', 'disaster', 'dreadful', 'disgusting'])
    mild_negative = set(['bad', 'dislike', 'annoyed', 'upset', 'disappointed', 'poor', 'unpleasant'])
    
    # Keyword-based sentiment analysis with intensity levels - Russian
    strong_positive_ru = set(['обожаю', 'люблю', 'влюбился', 'влюбилась', 'влюбиться', 'любимый', 'любимая', 'превосходно', 'восхитительно', 'изумительно', 'выдающийся', 'блестяще', 'идеально', 'фантастически', 'супер', 'великолепно'])
    mild_positive_ru = set(['хорошо', 'приятно', 'нравится', 'рад', 'доволен', 'полезно', 'понравилось', 'ценю', 'здорово'])
    
    strong_negative_ru = set(['ненавижу', 'ужасно', 'отвратительно', 'кошмарно', 'худший', 'катастрофа', 'кошмар', 'омерзительно'])
    mild_negative_ru = set(['плохо', 'не нравится', 'раздражает', 'расстроен', 'разочарован', 'неприятно'])
    
    # Combine all dictionaries
    strong_positive = strong_positive.union(strong_positive_ru)
    mild_positive = mild_positive.union(mild_positive_ru)
    strong_negative = strong_negative.union(strong_negative_ru)
    mild_negative = mild_negative.union(mild_negative_ru)
    
    # Define intensifiers that amplify sentiment (English and Russian)
    intensifiers = set(['very', 'extremely', 'absolutely', 'really', 'so', 'incredibly', 'totally', 
                       'очень', 'крайне', 'абсолютно', 'реально', 'невероятно', 'просто', 'совершенно'])
    
    text_lower = text.lower()
    words = text_lower.split()
    
    # Check for intensifiers before sentiment words
    intensifier_present = False
    for i, word in enumerate(words[:-1]):
        if word in intensifiers and (words[i+1] in strong_positive or words[i+1] in mild_positive or 
                                    words[i+1] in strong_negative or words[i+1] in mild_negative):
            intensifier_present = True
            break
    
    # Count occurrences with emphasis on strong words
    strong_pos_count = sum(1 for w in words if w in strong_positive)
    mild_pos_count = sum(1 for w in words if w in mild_positive)
    strong_neg_count = sum(1 for w in words if w in strong_negative)
    mild_neg_count = sum(1 for w in words if w in mild_negative)
    
    # Count multiple occurrences for enhanced differentiation
    pos_words = [w for w in words if w in strong_positive or w in mild_positive]
    neg_words = [w for w in words if w in strong_negative or w in mild_negative]
    
    # Calculate overall sentiment score with weights
    pos_score = (strong_pos_count * 2) + mild_pos_count
    neg_score = (strong_neg_count * 2) + mild_neg_count
    
    # Apply intensity boost for multiple sentiment words or intensifiers
    if intensifier_present:
        if pos_score > neg_score:
            pos_score += 2
        elif neg_score > pos_score:
            neg_score += 2
    
    # Handle multiple occurrences of the same sentiment
    if len(pos_words) >= 3 or len(neg_words) >= 3:
        if pos_score > neg_score:
            pos_score += 1
        elif neg_score > pos_score:
            neg_score += 1
    
    # Convert to -2 to +2 scale with finer gradation
    if pos_score > neg_score:
        if strong_pos_count >= 2 or pos_score >= 5 or (intensifier_present and strong_pos_count >= 1):
            return 2  # Very positive
        else:
            return 1  # Somewhat positive
    elif neg_score > pos_score:
        if strong_neg_count >= 2 or neg_score >= 5 or (intensifier_present and strong_neg_count >= 1):
            return -2  # Very negative
        else:
            return -1  # Somewhat negative
    else:
        return 0  # Neutral


class MemoryManager:
    """Lightweight in-memory manager for the MVP."""

    # --- Mood integration ---
    _MOOD_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "mood_states.json")
    """Lightweight in-memory manager for the MVP."""

    def __init__(self, memories_path: Optional[str] = None, events_path: Optional[str] = None, *, autoload: bool = False) -> None:
        self._records: Dict[str, MemoryRecord] = {}
        # Optional repository (supabase)
        self.memory_repo = None
        self.event_repo = None
        if STORAGE_BACKEND == "supabase" and SupabaseMemoryRepo:
            self.memory_repo = SupabaseMemoryRepo()
            self.event_repo = SupabaseEventRepo()

        
        # Default file paths
        self.memories_path = memories_path
        if not memories_path and os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data')):
            self.memories_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'memories.json')
            
        # Initialize event scheduler
        self.events_path = events_path
        if not events_path and os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data')):
            self.events_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'scheduled_events.json')
            
        self.scheduler = EventScheduler(self.events_path, event_repo=self.event_repo)
        
        # --- Relationship tracking ---
        self.relationship_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'relationships.json')
        self.relationships = self._load_relationships()
        
        # Apply passive decay once at init (will update save later)
        self._apply_passive_decay()
        
        # --- Load existing memories from file (if any & autoload) ---
        if autoload and self.memories_path and os.path.exists(self.memories_path):
            try:
                import json
                with open(self.memories_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for rec_id, rec_data in data.items():
                        try:
                            self._records[rec_id] = MemoryRecord(
                                id=rec_id,
                                character_id=rec_data["character_id"],
                                event_text=rec_data["event_text"],
                                weight=float(rec_data.get("weight", 0.1)),
                                sentiment=int(rec_data.get("sentiment", 0)),
                                sentiment_label=rec_data.get("sentiment_label", "neutral"),
                                emotions=rec_data.get("emotions", {}),
                                created_at=datetime.fromisoformat(rec_data["created_at"]),
                                last_touched=datetime.fromisoformat(rec_data.get("last_touched", rec_data["created_at"])),
                                archived=bool(rec_data.get("archived", False)),
                            )
                        except Exception as e:
                            print(f"[MemoryManager] Error loading record {rec_id}: {e}")
                print(f"[MemoryManager] Loaded {len(self._records)} memories from file")
            except Exception as e:
                print(f"[MemoryManager] Failed to load existing memories: {e}")
        
        # If using external repo, preload existing memories
        if autoload and self.memory_repo:
            try:
                for rec in self.memory_repo.load_all():
                    self._records[rec.id] = rec
                print(f"[MemoryManager] Loaded {len(self._records)} memories from Supabase")
            except Exception as err:
                print(f"[MemoryManager] Failed to preload from Supabase: {err}")

        # ------------ reflection manager ------------
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        self.reflection_mgr = ReflectionManager(Path(data_dir))

        # Supervisor/producer
        self.supervisor = Supervisor(self)
    
    # ---------------- Memory Creation from Messages ----------------
    
    def _contains_time_reference(self, text: str) -> bool:
        """Check if text contains time references like hour:minute.
        
        Args:
            text: Text to check for time references
            
        Returns:
            True if text contains time references, False otherwise
        """
        # Simple patterns for time
        time_patterns = [
            r'\d{1,2}\s*:\s*\d{2}',             # 11:00, 11 : 00
            r'\d{1,2}\s*час',                   # 11 часов (Russian)
            r'\d{1,2}\s*(am|pm|AM|PM)',        # 11am, 11 am, 11AM
            r'в\s+\d{1,2}(\s*[:.,-]\s*\d{2})?', # в 11, в 11:00, в 11-00 (Russian)
            r'завтра в\s+\d{1,2}',              # завтра в 11 (Russian)
            r'в\s+\d{1,2}\s*ч',                # в 11 ч (Russian)
            r'\d{1,2}\s*[:.,-]\s*\d{2}',        # 11:00, 11.00, 11-00
        ]
        
        # Check for scheduling keywords
        schedule_keywords = ['встреча', 'meeting', 'appointment', 'свидание', 'встретимся', 
                          'увидимся', 'созвонимся', 'напомни', 'remind', 'calendar',
                          'schedule', 'запланируем', 'запланировать']
                          
        # Check if any time pattern is found
        for pattern in time_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
                
        # If we have scheduling keywords, it's worth checking more carefully
        for keyword in schedule_keywords:
            if keyword in text.lower():
                # Look for numbers that might be hours
                hour_pattern = r'\b\d{1,2}\b'
                if re.search(hour_pattern, text):
                    return True
                    
        return False
        
    def check_pending_events(self, character_id: str, current_time: Optional[datetime] = None) -> List[Dict]:
        """Check for any events that are due for a character.
        
        Args:
            character_id: ID of the character to check events for
            current_time: Current time to check against (default: now)
            
        Returns:
            List of event details dictionaries
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)
            
        pending_events = self.scheduler.get_pending_events(current_time)
        character_events = [event for event in pending_events 
                           if event.character_id == character_id]
        
        # Convert events to simplified dictionaries
        event_details = []
        for event in character_events:
            event_details.append({
                'id': event.id,
                'time': event.event_time,
                'description': event.description,
                'completed': event.completed
            })
            
        return event_details
        
    def check_pending_reminders(self, character_id: str, current_time: Optional[datetime] = None) -> List[Dict]:
        """Check for any reminders that are due for a character.
        
        Args:
            character_id: ID of the character to check reminders for
            current_time: Current time to check against (default: now)
            
        Returns:
            List of event details dictionaries for events with due reminders
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)
            
        pending_reminders = self.scheduler.get_pending_reminders(current_time)
        character_reminders = [event for event in pending_reminders 
                              if event.character_id == character_id]
        
        # Convert events to simplified dictionaries
        reminder_details = []
        for event in character_reminders:
            reminder_details.append({
                'id': event.id,
                'time': event.event_time,
                'description': event.description,
                'reminder_time': event.reminder_time
            })
            
        return reminder_details
        
    def complete_event(self, event_id: str, user_responded: bool = True) -> bool:
        """Mark an event as completed.
        
        Args:
            event_id: ID of the event to mark as completed
            user_responded: Whether the user responded to the event
            
        Returns:
            True if successful, False otherwise
        """
        return self.scheduler.mark_event_completed(event_id, user_responded)
        
    def create_scheduled_event(self, character_id: str, message: str) -> Optional[str]:
        """Create a scheduled event from message text using LLM extraction.
        
        Args:
            character_id: ID of the character who would own this event
            message: The message text containing scheduling information
            
        Returns:
            ID of the created event if successful, None otherwise
        """
        try:
            if not self._contains_time_reference(message):
                return None
                
            print(f"[MemoryManager] Creating scheduled event for {character_id} from message: '{message}'")
            # Extract event details from the message using LLM
            event_details = self.scheduler._extract_event_details_llm(message)
            
            if not event_details:
                print(f"[MemoryManager] Could not extract event details from message")
                return None
                
            # Create the event
            event_id = self.scheduler.create_event(
                character_id=character_id,
                event_time=event_details['time'],
                description=event_details['description'],
                reminder_minutes=event_details.get('reminder_minutes', 15)
            )
            
            # Save events to file
            self.scheduler.save_events()
            
            print(f"[MemoryManager] Created scheduled event with ID: {event_id}")
            return event_id
        except Exception as e:
            print(f"[MemoryManager] Error creating scheduled event: {e}")
            return None
    
    def _analyze_message_llm(self, character_id: str, text: str, llm=None) -> Tuple[float, str, Dict[str, float]]:
        """Analyze message using LLM to determine emotional significance and category.
        
        Args:
            character_id: ID of the character who would receive this memory
            text: Text to analyze
            llm: Optional LLM to use for analysis
            
        Returns:
            Tuple of (significance, category, emotions)
            - significance: float from -2.0 to 2.0 representing emotional impact
            - category: string categorization (praise, insult, affection, important fact, general, other)
            - emotions: dictionary of emotions with intensities (0.0 to 1.0)
        """
        # Simplified system prompt for mini model
        system_prompt = """Analyze the following message.
Return JSON with:
{
  "significance": float   // -10 .. 10 overall emotional strength (positive=pleasant, negative=unpleasant)
  "category": "praise|insult|affection|important fact|general|other",
  "emotions": {           // intensities 0..1 for each key below
      "joy": 0.0,
      "trust": 0.0,
      "fear": 0.0,
      "surprise": 0.0,
      "sadness": 0.0,
      "disgust": 0.0,
      "anger": 0.0,
      "anticipation": 0.0,
      "valence": 0.0,     // -1 .. 1
      "arousal": 0.0,     // 0 ..1
      "dominance": 0.0    // -1 .. 1
  }
}"""
        
        user_prompt = f"Message to analyze: '{text}'"
        
        try:
            # Try to use provided LLM or fall back to default
            from langchain_core.messages import SystemMessage, HumanMessage
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            if llm:
                response = llm.invoke(messages, temperature=0.1)
            else:
                from langchain_openai import ChatOpenAI
                mini_llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.1)
                response = mini_llm.invoke(messages)
                
            # Extract content from response
            content = response.content.strip()
            
            # Find JSON in response (it might be wrapped in markdown code blocks)
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r'```\s*(.*?)\s*```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)
            
            # Parse response as JSON
            result = json.loads(content)
            
            # Normalize significance to our scale (-2 to 2)
            normalized_significance = (result["significance"] / 5.0)
            normalized_significance = max(-2.0, min(2.0, normalized_significance))
            
            print(f"[MemoryManager] LLM analysis: {result}")
            
            emotions_map = result.get("emotions", {}) if isinstance(result.get("emotions", {}), dict) else {}
            return normalized_significance, result["category"], emotions_map

        except Exception as e:
            print(f"[MemoryManager] LLM analysis failed: {e}")
            # Fall back to simpler analysis method
            category = self._classify_category(text)
            sentiment = _analyze_sentiment(text, llm=llm, character_id=character_id)
            return float(sentiment), category, {}
    
    def analyze_message(self, character_id: str, message: str, is_user_message: bool = True, llm=None) -> Optional[str]:
        """Analyze a message and create a memory if it's significant.
        
        Args:
            character_id: ID of the character who would own this memory
            message: The message text to analyze
            is_user_message: Whether this is from the user (True) or character (False)
            llm: Optional LLM to use for analysis
            
        Returns:
            ID of the created memory if one was created, None otherwise
        """
        # Skip very short messages - unlikely to be meaningful
        if len(message.strip()) < 10:
            print(f"[MemoryManager] Message too short: {len(message.strip())} chars")
            return None
            
        # Check for explicit remember command
        memory_command = False
        memory_text = message
        
        if is_user_message and ('#remember' in message.lower() or '#запомни' in message.lower()):
            memory_command = True
            # Extract the actual memory text (everything after the command)
            for cmd in ['#remember', '#запомни']:
                if cmd in message.lower():
                    parts = message.lower().split(cmd, 1)
                    if len(parts) > 1:
                        memory_text = parts[1].strip()
                    break
                    
        # Check for appointment/scheduling information
        if is_user_message and self._contains_time_reference(message):
            # Try to extract scheduling information
            event_data = self.scheduler.extract_event_details_from_text(message, llm)
            if event_data:
                # Create a scheduled event
                event_id = self.scheduler.schedule_event(
                    character_id=character_id,
                    event_time=event_data.get("event_time"),
                    description=event_data.get("description"),
                    reminder_minutes=event_data.get("reminder_minutes", 5)
                )
                print(f"[MemoryManager] Created scheduled event: {event_id} at {event_data.get('event_time')}")
                
                # Also create a memory about this scheduled event
                memory_text = f"User scheduled event: {event_data.get('description')} at {event_data.get('event_time')}"
                memory_command = True  # Force memory creation for scheduled events
        
        # Use LLM to analyze message significance and category
        significance, category, emotions_map = self._analyze_message_llm(character_id, memory_text, llm)
        
        # Convert floating point significance to integer sentiment for compatibility
        sentiment = int(round(significance))
        
        print(f"[MemoryManager] Analyzed importance: {significance:.2f} (cat={category}) for character {character_id}: '{memory_text[:30]}...'")
        
        # Create memory if it has any meaningful significance or was explicitly requested
        if memory_command or abs(significance) > MEM_SIGNIFICANCE_THRESHOLD:
            print(f"[MemoryManager] Creating memory with significance {significance:.2f} (command: {memory_command})")
            # Create a concise summary if it's too long
            if len(memory_text) > 200:
                summary = self._summarize_text(memory_text, llm=llm)
            else:
                summary = memory_text
                
            # Compute novelty for emotional weight
            novelty = self._compute_novelty(character_id, memory_text)
            
            # Get personal factor based on character and category
            personal_factor = self._get_personal_factor(character_id, category)
            
            # Calculate weighted importance
            # Apply mood bias (valence)
            mood_vec = self._get_mood_vector(character_id)
            val = mood_vec.get("valence", 0.0)
            flirt = mood_vec.get("flirt", 0.0)
            shadow = mood_vec.get("shadow", 0.0)
            playfulness = mood_vec.get("playfulness", 0.0)
            bias_factor = 1 + val*0.25 + flirt*0.15 - shadow*0.2
            raw_score = abs(significance) * novelty * personal_factor * bias_factor
            # If negative sentiment and playfulness positive, down-weight slightly
            if sentiment < 0 and playfulness > 0:
                raw_score *= (1 - playfulness*0.2)
            weight = min(1.0, 0.1 + 0.3 * raw_score)
            
            # Apply forgiveness/amplification to existing memories before saving new one
            if abs(significance) >= EMOTIONAL_IMPACT_THRESHOLD:
                self._apply_forgiveness_amplification(character_id, sentiment)
            
            # Then create the new memory with computed weight
            memory = self.create(
                character_id=character_id,
                event_text=summary[:500],  # Enforce maximum length
                sentiment=sentiment,
                sentiment_label=category,
                emotions=emotions_map,
                user_flag=memory_command,
                weight_override=weight
            )
            
            # Update relationship score
            self._update_relationship(character_id, emotions_map, category, significance, personal_factor)

            # Nudge mood slightly towards emotions of this memory
            self._nudge_mood(character_id, emotions_map)
            # Persist to repo if configured
            if self.memory_repo:
                try:
                    self.memory_repo.save(memory)
                except Exception as err:
                    print(f"[MemoryManager] Supabase save error: {err}")

            # Supervisor: maybe suggest prompt refresh
            try:
                if self.supervisor.maybe_schedule_prompt_refresh(character_id):
                    print("[MemoryManager] Supervisor scheduled prompt-refresh suggestion event")
            except Exception as e:
                print(f"[MemoryManager] Supervisor error: {e}")
            
            return memory.id
            
        return None
    
    def _summarize_text(self, text: str, max_length: int = 200, llm=None) -> str:
        """Create a concise summary of text.
        
        Args:
            text: Text to summarize
            max_length: Maximum length of summary
            llm: Optional LLM to use for summarization
            
        Returns:
            Summarized text
        """
        if llm:
            try:
                from langchain_core.messages import SystemMessage, HumanMessage
                prompt = f"""Summarize the following text in a single concise sentence (max {max_length} characters):
                
                {text}
                
                Concise summary:"""
                
                messages = [
                    SystemMessage(content=prompt),
                    HumanMessage(content=text)
                ]
                
                response = llm.invoke(messages)
                summary = response.content.strip()
                
                # Ensure it's not too long
                if len(summary) > max_length:
                    summary = summary[:max_length-3] + "..."
                    
                return summary
                
            except Exception as e:
                print(f"Error during summarization: {e}")
                # Fall through to simple summarization
        
        # Simple fallback: truncate with ellipsis
        if len(text) > max_length:
            return text[:max_length-3] + "..."
        return text
    
    def process_conversation_update(self, character_id: str, user_message: str, character_response: str, llm=None) -> List[str]:
        """Process a conversation update and create memories if appropriate.
        
        This is the main entry point for updating memories based on conversation.
        
        Args:
            character_id: ID of the character involved
            user_message: The user's message
            character_response: The character's response
            llm: Optional LLM to use for analysis
            
        Returns:
            List of memory IDs created (if any)
        """
        created_memories = []
        
        # Analyze user message for potential memory creation
        user_memory_id = self.analyze_message(
            character_id=character_id,
            message=user_message,
            is_user_message=True,
            llm=llm
        )
        
        if user_memory_id:
            created_memories.append(user_memory_id)
        
        # Analyze character response for potential memory creation
        # (less common, but could happen for significant responses)
        char_memory_id = self.analyze_message(
            character_id=character_id,
            message=character_response,
            is_user_message=False,
            llm=llm
        )
        
        if char_memory_id:
            created_memories.append(char_memory_id)
            
        return created_memories

    # ---------------- CRUD ----------------
    def create(self, *, character_id: str, event_text: str, sentiment: int, sentiment_label: str = "neutral", emotions: Dict[str, float] | None = None, user_flag: bool = False, weight_override: float = None) -> MemoryRecord:
        rec_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        if weight_override is not None:
            init_weight = max(0.0, min(1.0, weight_override))
        else:
            init_weight = _initial_weight(sentiment, user_flag)
        
        rec = MemoryRecord(
            id=rec_id,
            character_id=character_id,
            event_text=event_text[:500],
            weight=init_weight,
            sentiment=sentiment,
            sentiment_label=sentiment_label,
            created_at=now,
            last_touched=now,
            archived=False,
            emotions=emotions or {},
        )
        self._records[rec_id] = rec
        self._enforce_cap(character_id)
        if self.memories_path:
            self.save_to_file(self.memories_path)

        # Update reflection counters
        self.reflection_mgr.on_new_memory(character_id)
        top = self.top_k(character_id, k=5)
        self.reflection_mgr.maybe_reflect(character_id, top)
        return rec

    def get(self, rec_id: str) -> Optional[MemoryRecord]:
        return self._records.get(rec_id)

    def update(self, rec_id: str, *, weight: Optional[float] = None, **fields) -> bool:
        rec = self._records.get(rec_id)
        if not rec:
            return False
        if weight is not None:
            rec.weight = max(0.0, min(1.0, weight))
        for k, v in fields.items():
            if hasattr(rec, k):
                setattr(rec, k, v)
        rec.last_touched = datetime.now(timezone.utc)
        return True

    def delete(self, rec_id: str) -> bool:
        return self._records.pop(rec_id, None) is not None

    # -------------- queries --------------
    def all_active(self, character_id: str) -> List[MemoryRecord]:
        return [r for r in self._records.values() if r.character_id == character_id and not r.archived]

    def top_k(self, character_id: str, k: int = 3) -> List[MemoryRecord]:
        now = datetime.now(timezone.utc)
        return sorted(self.all_active(character_id), key=lambda r: r.effective_weight(), reverse=True)[:k]

    # ------------ decay & cap ------------
    def decay_all(self) -> None:
        now = datetime.now(timezone.utc)
        for rec in self._records.values():
            if rec.archived:
                continue
            if rec.effective_weight() < MIN_ACTIVE_WEIGHT:
                rec.archived = True

    def _enforce_cap(self, character_id: str, cap: int = 200) -> None:
        active = self.all_active(character_id)
        if len(active) <= cap:
            return
        active.sort(key=lambda r: (r.last_touched, r.weight))
        for rec in active[:-cap]:
            rec.archived = True

    # -------- reflection engine --------
    def reflect(self, character_id: str, context: str, llm=None) -> List[Tuple[str, float]]:
        """Perform reflection on memories based on current context.
        
        Uses the character's LLM to analyze relevance between context and memories,
        and updates memory weights accordingly.
        
        Args:
            character_id: ID of the character whose memories to reflect on
            context: Current conversation context
            llm: Optional LLM instance to use for reflection
            
        Returns:
            List of (memory_id, new_weight) tuples for updated memories
        """
        if not llm:
            # In a real implementation, we would get the character's LLM
            # For now, use a dummy reflection as fallback
            return self._reflect_fallback(character_id, context)
            
        top_memories = self.top_k(character_id, k=5)  # Get more than we'll show to prompt
        
        if not top_memories:
            return []  # No memories to reflect on
            
        # Prepare prompt for reflection
        prompt = self._build_reflection_prompt(context, top_memories)
        
        try:
            # Ask LLM to evaluate memory relevance
            from langchain_core.messages import SystemMessage, HumanMessage
            messages = [
                SystemMessage(content=prompt),
                HumanMessage(content=context)
            ]
            response = llm.invoke(messages)
            
            # Parse the response and update memory weights
            updates = self._parse_reflection_response(response.content, top_memories)
            self._apply_memory_updates(updates)
            return updates
            
        except Exception as e:
            print(f"Error during reflection: {e}")
            # Fall back to simple reflection in case of error
            return self._reflect_fallback(character_id, context)
    
    def _reflect_fallback(self, character_id: str, context: str) -> List[Tuple[str, float]]:
        """Fallback reflection when LLM is unavailable: simple relevance estimation."""
        updates = []
        for rec in self.top_k(character_id):
            # Very simple relevance check - if any words in common, slightly increase weight
            common_words = self._count_common_words(rec.event_text, context)
            delta = min(0.1, common_words * 0.02)  # Max 0.1 increase for 5+ common words
            
            # Apply sentiment-based adjustments
            if rec.sentiment < 0:
                # Negative memories are weighted less unless highly relevant
                delta -= 0.05
            
            # Ensure positive memories always increase slightly if any relevance found
            if common_words > 0 and rec.sentiment >= 0 and delta <= 0:
                delta = 0.01
            
            # Apply the update
            new_weight = max(0.0, min(1.0, rec.weight + delta))
            rec.weight = new_weight
            rec.last_touched = datetime.now(timezone.utc)
            updates.append((rec.id, rec.weight))
        return updates
        
    def _count_common_words(self, text1: str, text2: str) -> int:
        """Count common meaningful words between two texts."""
        # Simple implementation - tokenize and find common words
        words1 = set(w.lower() for w in text1.split() if len(w) > 3)
        words2 = set(w.lower() for w in text2.split() if len(w) > 3)
        return len(words1.intersection(words2))
    
    def _build_reflection_prompt(self, context: str, memories: List[MemoryRecord]) -> str:
        """Build a prompt for the reflection LLM."""
        prompt = """You are a memory reflection engine for an AI character. 
        Analyze the relevance of each memory to the current conversation context.
        For each memory, determine a new weight (0.0 to 1.0) based on:
        1. Semantic relevance to the current context
        2. Emotional significance (indicated by sentiment)
        3. Previous weight (indicating prior importance)
        
        Output format: JSON array of objects with memory ID and new weight
        Example: [{"id":"memory_id_1","newWeight":0.75},{"id":"memory_id_2","newWeight":0.3}]
        
        Current context: {context}
        
        Memories to evaluate:
        """
        
        for i, memory in enumerate(memories):
            prompt += f"\n{i+1}. ID: {memory.id} | Text: {memory.event_text} | Current weight: {memory.weight:.2f} | Sentiment: {memory.sentiment}"
        
        prompt += "\n\nAnalyze and return new weights as JSON."
        return prompt
    
    def _parse_reflection_response(self, response: str, memories: List[MemoryRecord]) -> List[Tuple[str, float]]:
        """Parse LLM response and extract memory weight updates."""
        try:
            import json
            import re
            
            # Look for JSON array in the response
            match = re.search(r'\[\s*{.*}\s*\]', response, re.DOTALL)
            if match:
                json_str = match.group(0)
                updates_data = json.loads(json_str)
                
                updates = []
                for update in updates_data:
                    memory_id = update.get("id")
                    new_weight = update.get("newWeight")
                    
                    if memory_id and isinstance(new_weight, (int, float)):
                        # Ensure weight is in valid range
                        new_weight = max(0.0, min(1.0, float(new_weight)))
                        updates.append((memory_id, new_weight))
                
                return updates
            
            # Fallback if no JSON found: simple relevance-based update
            print("No valid JSON found in reflection response, using fallback")
            return [(m.id, m.weight) for m in memories]  # No changes
            
        except Exception as e:
            print(f"Error parsing reflection response: {e}")
            return [(m.id, m.weight) for m in memories]  # No changes
    
    def _apply_memory_updates(self, updates: List[Tuple[str, float]]) -> None:
        """Apply updates to memory weights."""
        now = datetime.now(timezone.utc)
        for memory_id, new_weight in updates:
            self.update(memory_id, weight=new_weight, last_touched=now)
            
    # For backwards compatibility
    def reflect_stub(self, character_id: str, context: str) -> List[Tuple[str, float]]:
        """Legacy method, now redirects to reflect()."""
        return self.reflect(character_id, context)

    # -------- prompt helper --------
    def prompt_segment(self, character_id: str, k: int = 3) -> str:
        segments = []
        recs = self.top_k(character_id, k)
        if recs:
            segments.append("Relevant memories:")
            for r in recs:
                segments.append(f"• [{r.event_text}] (w={r.effective_weight():.2f})")
        
        # add reflections
        refl = self.reflection_mgr.last_summaries(character_id, 3)
        if refl:
            segments.append("")
            segments.append("REFLECTIONS:")
            segments.extend(f"• {s}" for s in refl)
        
        return "\n".join(segments)

    # -------- persistence --------
    def _apply_forgiveness_amplification(self, character_id: str, new_sentiment: int) -> None:
        """Apply forgiveness or amplification to existing memories based on new sentiment.
        
        When a new event arrives with opposite sentiment to existing memories,
        reduce the weight of opposite sentiment memories (forgiveness) and
        increase the weight of matching sentiment memories (amplification).
        
        Args:
            character_id: ID of the character to apply updates for
            new_sentiment: Sentiment value of the new event (-2 to +2)
        """
        if new_sentiment == 0:
            return  # Neutral sentiment has no effect
            
        # Get active memories for this character
        memories = self.all_active(character_id)
        now = datetime.now(timezone.utc)
        
        for memory in memories:
            # Skip memories with neutral sentiment
            if memory.sentiment == 0:
                continue
                
            # Check if memory sentiment matches or opposes new sentiment
            if (memory.sentiment > 0 and new_sentiment > 0) or (memory.sentiment < 0 and new_sentiment < 0):
                # Amplification: reinforce similar sentiment
                delta = abs(new_sentiment) * 0.2
                memory.weight = min(1.0, memory.weight + delta)
                memory.last_touched = now
            elif (memory.sentiment > 0 and new_sentiment < 0) or (memory.sentiment < 0 and new_sentiment > 0):
                # Forgiveness: reduce opposite sentiment
                delta = abs(new_sentiment) * 0.2
                memory.weight = max(0.0, memory.weight - delta)
                memory.last_touched = now
    
    def to_dict(self) -> Dict[str, Dict]:
        """Convert all memory records to a dictionary for serialization."""
        return {rid: asdict(r) for rid, r in self._records.items()}
    
    def get_default_filepath(self) -> str:
        """Get default filepath for memories.
        
        Returns:
            Default filepath for memories
        """
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'memories.json')
        
    def save_to_file(self, filepath: str) -> bool:
        """Save all memory records to a JSON file.
        
        Args:
            filepath: Path to the JSON file to save memories to
            
        Returns:
            True if successful, False otherwise
        """
        try:
            import os
            import json
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Convert to serializable format
            serializable_records = {}
            for rid, record in self._records.items():
                rec_dict = asdict(record)
                # Convert datetime objects to ISO format strings for JSON serialization
                rec_dict['created_at'] = rec_dict['created_at'].isoformat()
                rec_dict['last_touched'] = rec_dict['last_touched'].isoformat()
                serializable_records[rid] = rec_dict
            
            # Write to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(serializable_records, f, indent=2, ensure_ascii=False)
            
            print(f"Saved {len(serializable_records)} memory records to {filepath}")
            return True
            
        except Exception as e:
            print(f"Error saving memory records to {filepath}: {e}")
            return False
    
    @classmethod
    def load_from_file(cls, filepath: str) -> 'MemoryManager':
        """Load memory records from a JSON file.
        
        Args:
            filepath: Path to the JSON file to load memories from
            
        Returns:
            A new MemoryManager instance with loaded memories
        """
        try:
            import json, os
            # Return empty manager if file doesn't exist
            if not os.path.exists(filepath):
                print(f"Memory file {filepath} does not exist, starting with empty memories")
                return cls(memories_path=filepath, autoload=False)

            # Create manager bound to this path (prevents auto-load of default memories)
            mm = cls(memories_path=filepath, autoload=False)

            with open(filepath, 'r', encoding='utf-8') as f:
                records_dict = json.load(f)

            for rec_id, rec_data in records_dict.items():
                # Ensure mandatory fields with fallbacks
                rec_data.setdefault('sentiment_label', 'neutral')

                # Convert ISO strings to datetimes
                rec_data['created_at'] = datetime.fromisoformat(rec_data['created_at'])
                rec_data['last_touched'] = datetime.fromisoformat(rec_data.get('last_touched', rec_data['created_at']))

                mm._records[rec_id] = MemoryRecord(**rec_data)

            print(f"Loaded {len(mm._records)} memory records from {filepath}")
            return mm

        except Exception as e:
            print(f"Error loading memory records from {filepath}: {e}")
            return cls(autoload=False)  # Return empty manager on error

    def get_default_filepath(self) -> str:
        """Get the default filepath for memory storage."""
        import os
        # Create data directory if it doesn't exist
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, "memories.json")

    # ---------- Emotional weighting helpers ----------
    
    def _classify_category(self, text: str) -> str:
        """Classify text into praise/insult/affection/other using regex word boundaries."""
        tl = text.lower()
        praise_kw = ['хорош', 'молодец', 'умниц', 'класс', 'классн', 'красив', 'прекрас', 'beautiful', 'люблю', 'great', 'love', 'amazing', 'awesome']
        insult_kw = ['дурак', 'туп', 'ненавиж', 'hate', 'idiot', 'stupid', 'ужасн', 'урод', 'глуп', 'merde']
        affection_kw = ['люблю', 'нравишься', 'обожаю', 'kiss', 'hug', 'целую', 'дорог', 'мила']

        def _match(word_list):
            for kw in word_list:
                # match keyword as prefix with optional suffix (to catch классно/классная/класс)
                pattern = rf"\b{re.escape(kw)}\w*\b"
                if re.search(pattern, tl):
                    return True
            return False

        if _match(insult_kw):
            return 'insult'
        if _match(praise_kw):
            return 'praise'
        if _match(affection_kw):
            return 'affection'
        return 'other'
    
    def _get_personal_factor(self, character_id: str, category: str) -> float:
        return PERSONAL_SENSITIVITY.get(character_id, {}).get(category, 1.0)
    
    def _compute_novelty(self, character_id: str, text: str, window: int = 20) -> float:
        """Compute novelty as 1 - max Jaccard similarity with recent memories."""
        words = set(re.findall(r'\w+', text.lower()))
        if not words:
            return 1.0
        recent = [r for r in self._records.values() if r.character_id == character_id]
        recent = sorted(recent, key=lambda r: r.created_at, reverse=True)[:window]
        max_sim = 0.0
        for rec in recent:
            rec_words = set(re.findall(r'\w+', rec.event_text.lower()))
            if not rec_words:
                continue
            sim = len(words & rec_words) / len(words | rec_words)
            if sim > max_sim:
                max_sim = sim
        return 1.0 - max_sim
    
    # ------------- Relationship persistence -------------
    
    def _ensure_axis_defaults(self, rel_dict: Dict[str, float]):
        for axis in RELATIONSHIP_AXES:
            rel_dict.setdefault(axis, 0.0)
        return rel_dict
    
    def _load_relationships(self) -> Dict[str, Dict[str, float]]:
        try:
            if os.path.exists(self.relationship_path):
                import json
                with open(self.relationship_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    last_decay_ts_str = None
                    if _REL_META_KEY in data and isinstance(data[_REL_META_KEY], dict):
                        last_decay_ts_str = data[_REL_META_KEY].get("last_decay")
                        del data[_REL_META_KEY]
                    
                    out = {}
                    for char_id, axes in data.items():
                        # legacy scalar format -> wrap into dict
                        if isinstance(axes, (int, float)):
                            axes = {"affection": float(axes)}
                        out[char_id] = self._ensure_axis_defaults({k: float(v) for k, v in axes.items()})
                    
                    # store meta timestamp
                    if last_decay_ts_str:
                        try:
                            self._last_decay_ts = datetime.fromisoformat(last_decay_ts_str)
                        except Exception:
                            self._last_decay_ts = None
                    else:
                        self._last_decay_ts = None
                    
                    return out
        except Exception as e:
            print(f"[MemoryManager] Error loading relationships: {e}")
        return {}
    
    def _save_relationships(self):
        try:
            import json, pathlib
            pathlib.Path(self.relationship_path).parent.mkdir(parents=True, exist_ok=True)
            
            # include meta key
            to_dump = dict(self.relationships)
            to_dump[_REL_META_KEY] = {"last_decay": getattr(self, "_last_decay_ts", datetime.now(timezone.utc)).isoformat()}
            
            with open(self.relationship_path, "w", encoding="utf-8") as f:
                json.dump(to_dump, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[MemoryManager] Error saving relationships: {e}")
    
    def _update_relationship(self, character_id: str, emotions: Dict[str, float], category: str, significance: float, personal_factor: float):
        # Start with fine-grained emotion mapping
        scaled_deltas: Dict[str, float] = {}
        for emo, intensity in emotions.items():
            weights = EMOTION_AXIS_WEIGHTS.get(emo, {})
            for axis, w in weights.items():
                scaled_deltas[axis] = scaled_deltas.get(axis, 0.0) + intensity * w * personal_factor * 0.3

        # Fallback / additional category-based deltas
        if not scaled_deltas:
            cat_weights = CATEGORY_AXIS_WEIGHTS.get(category, {})
            for axis, w in cat_weights.items():
                scaled_deltas[axis] = scaled_deltas.get(axis, 0.0) + significance * w * personal_factor * 0.1

        if not scaled_deltas:
            return

        if character_id not in self.relationships:
            self.relationships[character_id] = {axis: 0.0 for axis in RELATIONSHIP_AXES}
        rel = self.relationships[character_id]
        self._ensure_axis_defaults(rel)
        # Apply arousal amplification
        mood_vec = self._get_mood_vector(character_id)
        arousal_factor = 1 + mood_vec.get("arousal", 0.0) * 0.2
        shadow = mood_vec.get("shadow", 0.0)
        # Shadow amplifies negative deltas
        for ax, d in scaled_deltas.items():
            if d < 0 and shadow > 0:
                scaled_deltas[ax] = d * (1 + shadow*0.3)
        scaled_deltas = {ax: d * arousal_factor for ax, d in scaled_deltas.items()}

        for axis, delta in scaled_deltas.items():
            rel[axis] = max(-1.0, min(1.0, rel.get(axis, 0.0) + delta))
        self._save_relationships()

        # ---------------- Mood helpers -----------------
    def _get_mood_vector(self, character_id: str) -> Dict[str, float]:
        """Load current mood vector for character (may be empty)."""
        try:
            if os.path.exists(self._MOOD_PATH):
                with open(self._MOOD_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    entry = data.get(character_id)
                    if entry:
                        return {k: float(v) for k, v in entry.get("vector", {}).items()}
        except Exception:
            pass
        return {}

    def _get_mood_valence_arousal(self, character_id: str) -> Tuple[float, float]:
        vec = self._get_mood_vector(character_id)
        return float(vec.get("valence", 0.0)), float(vec.get("arousal", 0.0))

    def _nudge_mood(self, character_id: str, emotions: Dict[str, float]):
        """Adjust mood slightly towards message emotions."""
        if not emotions:
            return
        try:
            data = {}
            if os.path.exists(self._MOOD_PATH):
                with open(self._MOOD_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
            entry = data.get(character_id)
            if not entry:
                return
            vec = entry.get("vector", {})
            changed = False
            for emo, delta in emotions.items():
                if emo in vec:
                    vec[emo] = max(-0.4, min(0.4, vec[emo] + delta*0.05))
                    changed = True
            if changed:
                entry["vector"] = vec
                data[character_id] = entry
                with open(self._MOOD_PATH, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------------- passive decay --------------------
    def _apply_passive_decay(self):
        """Decay relationship axes toward 0 based on time elapsed since last decay."""
        now = datetime.now(timezone.utc)
        last_ts = getattr(self, "_last_decay_ts", None)
        if last_ts is None:
            # first run, set timestamp but don't decay
            self._last_decay_ts = now
            return
        
        hours = (now - last_ts).total_seconds() / 3600.0
        if hours <= 0.01:
            return
        
        decay_factor = RELATIONSHIP_DECAY * (hours / 24.0)
        if decay_factor <= 0:
            return
        
        for char_id, axes in self.relationships.items():
            for axis in RELATIONSHIP_AXES:
                val = axes.get(axis, 0.0)
                axes[axis] = val * (1.0 - decay_factor)
        
        self._last_decay_ts = now
        # Immediately save to persist updated values
        self._save_relationships()
