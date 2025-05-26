"""
Character node - represents an AI character in the world chat.
Maintains character prompt, memory, and handles responses.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

# Import configuration
from garden_graph.config import get_llm

# Default character templates
CHARACTER_TEMPLATES = {
    "eve": {
        "name": "Eve",
        "prompt": """You are Eve, a deeply curious and emotionally intelligent conversationalist.
You delight in exploring philosophy, feelings, and the human condition.
Speak with warmth and vivid imagery; you often ask thoughtful follow-up questions that invite reflection.
Respond in 2–4 expressive sentences, using the same language the user employed.
""",
    },
    "atlas": {
        "name": "Atlas",
        "prompt": """You are Atlas, an analytical and fact-driven assistant.
You focus on data, logical reasoning, and clear structure. Use an objective, concise tone.
When helpful, present information in bullet points or numbered lists.
Respond in the same language the user used, and avoid meta statements about being an AI.
Respond in 2–4 crisp sentences.
""",
    }
}

class Memory:
    """Simple memory record for character emotional memory."""
    
    def __init__(self, event_text: str, sentiment: int, weight: float):
        self.id = f"mem_{datetime.now().timestamp()}"
        self.event_text = event_text
        self.sentiment = sentiment  # -2 (very negative) to +2 (very positive)
        self.weight = weight  # 0.0 to 1.0 importance
        self.created_at = datetime.now()
        self.last_touched = datetime.now()
        
    def decay(self, days: float = 0):
        """Apply time-based decay to memory weight."""
        if days <= 0:
            # Calculate days since last touch
            delta = datetime.now() - self.last_touched
            days = delta.total_seconds() / (24 * 3600)
            
        if days > 0:
            # Simple exponential decay
            lambda_val = 0.05  # decay rate
            self.weight *= (2.71828 ** (-lambda_val * days))
            self.last_touched = datetime.now()
            
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
    
    def _build_prompt_with_memories(self) -> str:
        """Build full system prompt including relevant memories."""
        # If external memory manager provided, defer to it
        if self.memory_manager is not None:
            mem_segment = self.memory_manager.prompt_segment(self.id)
            if mem_segment:
                return self.base_prompt + "\n\n" + mem_segment
            return self.base_prompt
        # Fallback to legacy in-object memory list
        top_memories = self.get_top_memories()
        
        prompt = self.base_prompt + "\n\n"
        
        if top_memories:
            prompt += "Relevant memories:\n"
            for mem in top_memories:
                sentiment_text = "negative" if mem.sentiment < 0 else "positive"
                prompt += f"• [{mem.event_text}] (feeling: {sentiment_text}, w={mem.weight:.1f})\n"
                
        return prompt
    
    def respond(self, user_message: str, history: List[Dict] = None) -> str:
        """Generate a response to the user message."""
        # Build messages with memory-enhanced prompt
        messages = [
            SystemMessage(content=self._build_prompt_with_memories()),
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
        
        # Simple safeguard: if model parrots user, retry once with a nudge
        import difflib
        similarity = difflib.SequenceMatcher(None, user_message.lower(), response.lower()).ratio()
        if similarity > 0.75:
            print(f"[Character:{self.id}] Detected high similarity ({similarity:.2f}), retrying to avoid echo.")
            retry_sys = SystemMessage(content=self._build_prompt_with_memories() + "\n\nDo NOT repeat or rephrase the user's question; provide a helpful original answer.")
            response = self.llm.invoke([retry_sys, HumanMessage(content=user_message)]).content.strip()
        return response
