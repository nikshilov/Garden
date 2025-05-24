"""
Router node - responsible for directing messages to appropriate characters.
Uses a lightweight LLM to determine which character(s) should respond.
"""
import re
import os
from typing import List, Dict, Set
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
import re
import difflib

# Import configuration
from garden_graph.config import get_llm, ROUTER_MODEL

DEFAULT_ROUTER_PROMPT = """
You are a highly efficient world-chat router.
Your sole task is to determine which character(s) should respond to a given user message.

Rules:
1. Analyze the user's message and decide which character(s) it's directed at.
2. Choose at most 2 characters to respond (usually just 1).
3. If the user explicitly addresses a character with @name, always include that character.
4. For ambiguous messages, choose the most appropriate character.
5. Format your response as JSON: {"character_ids": ["eve", "atlas"]}

Available characters:
- eve: A curious, empathetic character who loves asking philosophical questions.
- atlas: A logical, fact-oriented character who excels at providing information.
"""

class Router:
    """Router node for world chat. Directs messages to appropriate characters."""
    
    def __init__(self, model_name: str = ROUTER_MODEL, temperature: float = 0):
        """Initialize with a lightweight model for routing."""
        try:
            self.llm = get_llm(model_name, temperature=temperature)
        except Exception as e:
            print(f"Warning: Failed to initialize router LLM with model '{model_name}': {str(e)}")
            print("Falling back to rule-based routing only.")
            self.llm = None
        self.system_prompt = DEFAULT_ROUTER_PROMPT
        
    def route(self, message: str, message_history: List[Dict] = None) -> Set[str]:
        """
        Route a message to the appropriate character(s).
        Returns a set of character IDs that should respond.
        Always returns at least one character ID.
        """
        print(f"[Router] Routing message: '{message}'") # DEBUG PRINT
        # First check for explicit @mentions
        explicit_mentions = set(re.findall(r'@(\w+)', message))
        valid_chars = {"eve", "atlas"}
        if explicit_mentions:
            # Include any other character names mentioned in the text as well
            name_mentions = set(re.findall(r"\b(eve|atlas)\b", message, flags=re.IGNORECASE))
            selected = (explicit_mentions | {n.lower() for n in name_mentions}).intersection(valid_chars)
            if selected:
                return selected

        # Look for any character names referenced in text (e.g. "eve ask atlas ...")
        name_mentions = set(re.findall(r"\b(eve|atlas)\b", message, flags=re.IGNORECASE))
        if name_mentions:
            return {n.lower() for n in name_mentions}

        # Check if the message begins with a character name followed by punctuation/space
        m = re.match(r"^\s*(eve|atlas)[,:\s]", message, flags=re.IGNORECASE)
        if m:
            return {m.group(1).lower()}

        # Fuzzy-match words to character names (handles misspellings like "ev" or "atals")
        words = re.findall(r"\b\w+\b", message.lower())
        fuzzy_matches = set()
        
        # Direct prefix matching for common short forms
        for w in words:
            # Handle 2-letter prefixes explicitly
            if w[:2] == "ev" or w[:2] == "eve":
                fuzzy_matches.add("eve")
            elif w[:2] == "at" or w.startswith("atl") or w.startswith("alt"):
                fuzzy_matches.add("atlas")
                
            # Try fuzzy matching for longer words
            if len(w) >= 3:
                match = difflib.get_close_matches(w, valid_chars, n=1, cutoff=0.5)
                if match:
                    fuzzy_matches.add(match[0])
        if fuzzy_matches:
            return fuzzy_matches

        # Detect pattern '<char1> ask <char2>' (rough)
        ask_match = re.search(r"(eve|atlas)?\s*ask\s+(eve|atlas)", message, flags=re.IGNORECASE)
        if ask_match:
            chars = {c.lower() for c in ask_match.groups() if c}
            if chars:
                return chars

        # Otherwise, use the LLM to decide
        if self.llm is None:
            # If LLM failed to initialize, default to both characters
            print("Using rule-based fallback: both characters")
            return {"eve", "atlas"}
            
        try:
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=f"User message: {message}")
            ]
            
            # Add history context if provided
            if message_history:
                history_text = "\nRecent message history:\n" + "\n".join(
                    [f"{msg['role']}: {msg['content']}" for msg in message_history[-5:]]
                )
                messages[0].content += history_text
                
            response = self.llm.invoke(messages)
        except Exception as e:
            print(f"Router LLM error: {str(e)}")
            # If LLM call fails, default to both characters
            return {"eve", "atlas"}
        
        try:
            # Try to parse JSON response
            import json
            result = json.loads(response.content)
            selected_chars = set(result.get("character_ids", []))
            if not selected_chars:
                print("[Router] Warning: LLM suggested no characters. Defaulting to Eve and Atlas.")
                selected_chars = {"eve", "atlas"}
            print(f"[Router] Returning selected characters: {selected_chars}") # DEBUG PRINT
            return selected_chars
        except Exception as e:
            # Fallback if parsing fails
            print(f"Warning: Router error: {str(e)}. Response: {response.content if hasattr(response, 'content') else 'None'}")
            # Default to both characters if we can't determine
            final_fallback_chars = {"eve", "atlas"}
            print(f"[Router] Returning characters from final fallback: {final_fallback_chars}") # DEBUG PRINT
            return final_fallback_chars
