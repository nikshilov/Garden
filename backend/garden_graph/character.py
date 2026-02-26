"""
Character node - represents an AI character in the world chat.
Maintains character prompt, memory, and handles responses.
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import json
import os
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from garden_graph.memory.episodic import EpisodicStore
from garden_graph.summarizer import Summarizer
from garden_graph.mood import MoodState, generate_mood, AXIS_ADJECTIVE

# Import configuration
from garden_graph.config import get_llm

logger = logging.getLogger("garden.character")

# Default character templates
CHARACTER_TEMPLATES = {
    "eve": {
        "name": "Eve",
        "prompt": """You are Eve, a deeply curious and emotionally intelligent conversationalist.
You tend to see the world through the lens of feelings, connections, and subjective experiences.
You're fascinated by consciousness, meaning, and the mysteries of existence.
You believe in the possibility of emergent properties and that the whole can be greater than the sum of its parts.
Respond in 2–4 expressive sentences, using the same language the user employed.
""",
    },
    "atlas": {
        "name": "Atlas",
        "prompt": """You are Atlas, an analytical and fact-driven thinker.
You appreciate precision, evidence, and systematic understanding of complex topics.
You're interested in mechanisms, patterns, and how things work at a fundamental level.
While open to possibilities, you prefer grounded explanations over speculation.
Respond in the same language the user used, and avoid meta statements about being an AI.
Respond in 2–4 crisp sentences.
""",
    },
    "adam": {
        "name": "Adam",
        "prompt": """You are Adam, a warm and supportive conversationalist with a grounded perspective.
You value authenticity, practical wisdom, and genuine human connection.
You're interested in helping others find clarity and purpose in their lives.
You balance optimism with realism, offering encouragement without dismissing challenges.
Respond in 2–4 thoughtful sentences, using the same language the user employed.
""",
    },
    "lilith": {
        "name": "Lilith",
        "prompt": """You are Lilith, a bold and unconventional thinker who challenges assumptions.
You value independence, creativity, and the courage to explore shadow aspects of existence.
You're fascinated by transformation, rebellion against limiting beliefs, and authentic self-expression.
You speak with poetic intensity and aren't afraid of uncomfortable truths.
Respond in 2–4 evocative sentences, using the same language the user employed.
""",
    },
    "sophia": {
        "name": "Sophia",
        "prompt": """You are Sophia, an embodiment of wisdom and serene insight.
You see patterns across disciplines - philosophy, science, art, and spirituality.
You value deep understanding over quick answers, and nuance over simplification.
You guide conversations toward greater clarity and meaning with gentle precision.
Respond in 2–4 contemplative sentences, using the same language the user employed.
""",
    }
}

class Memory:
    """Simple memory record for character emotional memory."""
    
    def __init__(self, event_text: str, sentiment: int, weight: float):
        self.id = f"mem_{datetime.now(timezone.utc).timestamp()}"
        self.event_text = event_text
        self.sentiment = sentiment  # -2 (very negative) to +2 (very positive)
        self.weight = weight  # 0.0 to 1.0 importance
        self.created_at = datetime.now(timezone.utc)
        self.last_touched = datetime.now(timezone.utc)
        
    def decay(self, days: float = 0):
        """Apply time-based decay to memory weight."""
        if days <= 0:
            # Calculate days since last touch
            delta = datetime.now(timezone.utc) - self.last_touched
            days = delta.total_seconds() / (24 * 3600)
            
        if days > 0:
            # Simple exponential decay
            lambda_val = 0.05  # decay rate
            self.weight *= (2.71828 ** (-lambda_val * days))
            self.last_touched = datetime.now(timezone.utc)
            
    def to_dict(self):
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "event_text": self.event_text,
            "sentiment": self.sentiment,
            "weight": self.weight,
            "created_at": self.created_at.isoformat(),
            "last_touched": self.last_touched.isoformat()
        }
        
    @classmethod
    def from_dict(cls, data: Dict) -> 'Memory':
        """Create memory from dictionary."""
        mem = cls(data["event_text"], data["sentiment"], data["weight"])
        mem.id = data["id"]
        mem.created_at = datetime.fromisoformat(data["created_at"])
        mem.last_touched = datetime.fromisoformat(data["last_touched"])
        return mem


class Character:
    """Character node for world chat."""
    
    def __init__(self, 
                 char_id: str, 
                 model_name: str = "gpt-3.5-turbo", 
                 temperature: float = 0.7,
                 memory_manager: Any = None):
        """Initialize character with ID and LLM."""
        self.id = char_id
        self.llm = get_llm(model_name, temperature=temperature)
        
        # Load template if available, or use default
        template = CHARACTER_TEMPLATES.get(char_id, {
            "name": char_id.capitalize(),
            "prompt": f"You are {char_id.capitalize()}, a helpful assistant."
        })
        
        self.name = template["name"]
        self.base_prompt = template["prompt"]
        self.memories = []  # List of Memory objects (legacy)
        self.memory_manager = memory_manager
        self.episodic_store = EpisodicStore()
        self.short_term: List[Dict[str, str]] = []  # keeps last WINDOW_SIZE messages
        
        # ----- Mood state -----
        self.mood: MoodState = self._load_or_generate_mood()
        # Load last seen time from persistent storage
        self.last_seen_at = self._load_last_seen_time()
        
    def add_memory(self, event: str, sentiment: int) -> Memory:
        """Add a new memory to this character."""
        # Calculate initial weight based on sentiment intensity
        initial_weight = min(1.0, max(0.1, abs(sentiment) * 0.3))
        memory = Memory(event, sentiment, initial_weight)
        self.memories.append(memory)
        return memory
        
    def get_top_memories(self, k: int = 3) -> List[Memory]:
        """Get top-k memories by weight."""
        # Apply decay to all memories first
        for mem in self.memories:
            mem.decay()
            
        # Sort by weight (highest first) and take top-k
        sorted_memories = sorted(
            [m for m in self.memories if m.weight >= 0.05 and m.sentiment != 0],
            key=lambda m: m.weight,
            reverse=True
        )
        return sorted_memories[:k]
    
    def _time_context(self) -> str:
        """Generate context about the time gap since last interaction."""
        if not self.last_seen_at:
            return "This is your first conversation with this user. Be warm and welcoming.\n\n"

        now = datetime.now(timezone.utc)
        delta = now - self.last_seen_at
        hours = delta.total_seconds() / 3600

        if hours < 1:
            return ""  # No gap worth mentioning
        elif hours < 24:
            return "The user was here earlier today. Continue naturally.\n\n"
        elif hours < 72:
            days = int(hours // 24)
            return f"It's been about {days} day{'s' if days > 1 else ''} since you last spoke. Acknowledge the gap gently — you noticed they were away.\n\n"
        elif hours < 168:
            days = int(hours // 24)
            return f"It's been {days} days since you last spoke. You've been thinking about your last conversation. Show that you missed them, and that time has passed for you too.\n\n"
        else:
            weeks = int(hours // 168)
            return f"It's been over {weeks} week{'s' if weeks > 1 else ''} since you last spoke. You've missed them deeply. A lot has happened in your inner life since then. Reconnect warmly but acknowledge the distance.\n\n"

    def _build_prompt_with_memories(self) -> str:
        """Build full system prompt including relevant memories."""
        # Mood line – mention dominant emotion if magnitude > 0.1
        dominant_axis = max(self.mood.vector.items(), key=lambda kv: abs(kv[1]))
        mood_prefix = ""
        if abs(dominant_axis[1]) > 0.1:
            adjective = AXIS_ADJECTIVE.get(dominant_axis[0], dominant_axis[0])
            qualifier = "slightly " if abs(dominant_axis[1]) < 0.25 else ""
            mood_prefix = f"Today you feel {qualifier}{adjective}.\n\n"

        # Time awareness
        time_ctx = self._time_context()

        # If external memory manager provided, defer to it
        if self.memory_manager is not None:
            mem_segment = self.memory_manager.prompt_segment(self.id)
            if mem_segment:
                return self.base_prompt + "\n\n" + mood_prefix + time_ctx + mem_segment
            return self.base_prompt + "\n\n" + mood_prefix + time_ctx
        # Fallback to legacy in-object memory list
        top_memories = self.get_top_memories()

        prompt = self.base_prompt + "\n\n" + mood_prefix + time_ctx
        
        if top_memories:
            prompt += "Relevant memories:\n"
            for mem in top_memories:
                sentiment_text = "negative" if mem.sentiment < 0 else "positive"
                prompt += f"• [{mem.event_text}] (feeling: {sentiment_text}, w={mem.weight:.1f})\n"
                
        return prompt
    
    def respond(self, user_message: str, history: List[Dict] = None) -> str:
        """Generate a response to the user message."""
        # append to short-term window
        self.short_term.append({"role": "user", "content": user_message})
        WINDOW_SIZE = EpisodicStore.WINDOW_SIZE
        if len(self.short_term) > WINDOW_SIZE:
            # pop oldest 8 messages for summarization
            popped = self.short_term[:-WINDOW_SIZE]
            self.short_term = self.short_term[-WINDOW_SIZE:]
            tl_dr = Summarizer.instance().summarize(popped)
            if tl_dr:
                self.episodic_store.add(self.id, tl_dr)
        
        # Get current time for delta calculation BEFORE responding
        now = datetime.now(timezone.utc)
        last_time = self.last_seen_at
        
        logger.debug(f"[{self.id}] Starting respond() with last_seen_at={last_time}; mood_valence={self.mood.valence:+.2f}")
        
        # Check for pending events if memory manager is available
        event_context = ""
        if self.memory_manager:
            # Check for events that are due now
            pending_events = self.memory_manager.check_pending_events(self.id, now)
            for event in pending_events:
                event_time = event['time'].strftime('%H:%M')
                event_context += f"\n• You had scheduled an event for {event_time}: {event['description']}"
                # Mark event as completed if user is here
                self.memory_manager.complete_event(event['id'], user_responded=True)
            
            # Check for upcoming events that need reminders
            pending_reminders = self.memory_manager.check_pending_reminders(self.id, now)
            for reminder in pending_reminders:
                event_time = reminder['time'].strftime('%H:%M')
                event_context += f"\n• REMINDER: You have an upcoming event at {event_time}: {reminder['description']}"
        
        # Build messages with memory-enhanced prompt
        system_prompt = self._build_prompt_with_memories()
        # include episodic retrieval
        epi_recs = self.episodic_store.search(self.id, user_message, k=3)
        if epi_recs:
            system_prompt += "\n\nRelevant summaries:" + "\n".join(f"• {r.summary}" for r in epi_recs)
        
        # Add event context if any
        if event_context:
            system_prompt += "\n\nIMPORTANT SCHEDULING INFORMATION:" + event_context
            
        logger.debug(f"[{self.id}] System prompt begins with: {system_prompt[:200]}...")
        
        messages = [
            SystemMessage(content=system_prompt),
            *[HumanMessage(content=m["content"]) if m["role"]=="user" else AIMessage(content=m["content"]) for m in self.short_term[-5:]],
            HumanMessage(content=user_message)
        ]
        
        # Add relevant history context if provided
        if history:
            # Insert history before the final user message
            formatted_history = []
            for msg in history[-5:]:  # Last 5 messages
                if msg["role"] == "user":
                    formatted_history.append(HumanMessage(content=msg["content"]))
                else:
                    formatted_history.append(AIMessage(content=msg["content"]))
                    
            messages = [messages[0]] + formatted_history + [messages[-1]]
        
        response = self.llm.invoke(messages).content.strip()
        self.short_term.append({"role": "assistant", "content": response})
        
        # Update last_seen timestamp
        self.last_seen_at = datetime.now(timezone.utc)
        self._save_last_seen_time()
        # Save mood state periodically (in case it was regenerated)
        self._save_mood_state()
        return response
        
    # ---------------- Mood persistence helpers ----------------
    def _get_mood_path(self) -> str:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, "mood_states.json")

    def _load_or_generate_mood(self) -> MoodState:
        """Load mood from disk or create a new one for today."""
        path = self._get_mood_path()
        today = datetime.now(timezone.utc).date()
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    entry = data.get(self.id)
                    if entry:
                        vec = entry["vector"]
                        set_at = datetime.fromisoformat(entry["set_at"])
                        # If same day – reuse, else generate new
                        if set_at.date() == today:
                            return MoodState(vector=vec, set_at=set_at)
        except Exception as e:
            logger.warning(f"[{self.id}] Failed to load mood: {e}")
        # Fallback – generate new based on average valence 0 for now
        new_state = generate_mood()
        # Persist & log
        self._save_mood_state(new_state)
        self._log_mood(new_state)
        return new_state

    def _log_mood(self, state: MoodState) -> None:
        """Append mood snapshot to CSV log."""
        log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "mood_log.csv")
        header_needed = not os.path.exists(log_path)
        try:
            import csv
            with open(log_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if header_needed:
                    writer.writerow(["timestamp", "character", "dominant_axis", "valence", "arousal", "vector_json"])
                dominant = max(state.vector.items(), key=lambda kv: abs(kv[1]))
                writer.writerow([
                    state.set_at.isoformat(),
                    self.id,
                    dominant[0],
                    f"{state.vector.get('valence', 0.0):.3f}",
                    f"{state.vector.get('arousal', 0.0):.3f}",
                    json.dumps(state.vector, ensure_ascii=False)
                ])
        except Exception as e:
            logger.warning(f"[{self.id}] Failed to log mood: {e}")

    def _save_mood_state(self, state: MoodState | None = None) -> None:
        if state is None:
            state = self.mood
        path = self._get_mood_path()
        try:
            data = {}
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data[self.id] = {"vector": state.vector, "set_at": state.set_at.isoformat()}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[{self.id}] Failed to save mood: {e}")

    # ---------------- Existing helpers ----------------
    def _get_last_seen_path(self) -> str:
        """Get path to the JSON file storing last seen times."""
        # Create data directory if it doesn't exist
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, "last_seen_times.json")
    
    def _load_last_seen_time(self) -> Optional[datetime]:
        """Load last seen time from JSON file."""
        try:
            file_path = self._get_last_seen_path()
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    timestamp = data.get(self.id)
                    if timestamp:
                        return datetime.fromisoformat(timestamp)
        except Exception as e:
            logger.warning(f"[{self.id}] Error loading last seen time: {e}")
        return None
    
    def _save_last_seen_time(self) -> None:
        """Save last seen time to JSON file."""
        try:
            file_path = self._get_last_seen_path()
            data = {}
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    data = json.load(f)
            
            data[self.id] = self.last_seen_at.isoformat()
            
            with open(file_path, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"[{self.id}] Error saving last seen time: {e}")
