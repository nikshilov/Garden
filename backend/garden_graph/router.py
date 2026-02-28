"""
Router node - responsible for directing messages to appropriate characters.
Uses a lightweight LLM to determine which character(s) should respond.
"""
import json
import logging
import re
import os
from typing import List, Dict, Set, Optional
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import difflib

# Import configuration
from garden_graph.config import get_llm, ROUTER_MODEL

logger = logging.getLogger("garden.router")

# All known character IDs
ALL_CHARACTER_IDS = {"eve", "atlas", "adam", "lilith", "sophia"}

# Default characters for world chat (when no specific character selected)
DEFAULT_CHARACTERS = {"eve", "atlas"}

DEFAULT_ROUTER_PROMPT = """
You are a highly efficient world-chat router.
Your sole task is to determine which character(s) should respond to a given user message.

Rules:
1. Analyze the user's message and decide which character(s) it's directed at.
2. Choose at most 2 characters to respond (usually just 1).
3. If the user explicitly addresses a character with @name, always include that character.
4. If the user uses a plural/group address (e.g. "guys", "друзья", or generally speaks to everyone) **and** no names are mentioned, select **all** available characters.
5. Format your response as JSON: {"character_ids": ["eve", "atlas"]}

Available characters:
- eve: A curious, empathetic character who loves asking philosophical questions.
- atlas: A logical, fact-oriented character who excels at providing information.
- adam: A warm, supportive character who values authenticity and practical wisdom.
- lilith: A bold, unconventional thinker who challenges assumptions.
- sophia: An embodiment of wisdom who sees patterns across disciplines.
"""

class Router:
    """Router node for world chat. Directs messages to appropriate characters."""

    def __init__(self, model_name: str = ROUTER_MODEL, temperature: float = 0,
                 characters: Dict[str, Dict] = None, default_characters: Set[str] = None):
        """Initialize with a lightweight model for routing.

        Args:
            characters: Dict mapping char_id to {"name": str, "description": str}
                       If None, uses hardcoded defaults for backward compatibility.
            default_characters: Set of default character IDs when no routing match found.
        """
        try:
            self.llm = get_llm(model_name, temperature=temperature)
        except Exception as e:
            logger.warning(f"Failed to initialize router LLM: {e}")
            self.llm = None

        if characters:
            self.available_characters = set(characters.keys())
            self.default_characters = default_characters or self.available_characters
            # Build dynamic prompt
            char_descriptions = "\n".join(
                f"- {cid}: {info.get('description', info.get('name', cid))}"
                for cid, info in characters.items()
            )
            self.system_prompt = DEFAULT_ROUTER_PROMPT.split("Available characters:")[0] + f"Available characters:\n{char_descriptions}\n"
            # Build prefix map dynamically (2, 3, and 4-char prefixes)
            self.prefix_map = {}
            for cid in characters:
                if len(cid) >= 2:
                    self.prefix_map[cid[:2]] = cid
                if len(cid) >= 3:
                    self.prefix_map[cid[:3]] = cid
                if len(cid) >= 4:
                    self.prefix_map[cid[:4]] = cid
        else:
            self.available_characters = ALL_CHARACTER_IDS
            self.default_characters = default_characters or DEFAULT_CHARACTERS
            self.system_prompt = DEFAULT_ROUTER_PROMPT
            self.prefix_map = {
                "ev": "eve", "at": "atlas", "atl": "atlas", "alt": "atlas",
                "ad": "adam", "lil": "lilith", "soph": "sophia", "sof": "sophia"
            }
        
    def route(self, message: str, message_history: List[Dict] = None, available_chars: Set[str] = None) -> Set[str]:
        """
        Route a message to the appropriate character(s).
        Returns a set of character IDs that should respond.
        Always returns at least one character ID.

        Args:
            message: The user message to route
            message_history: Optional conversation history
            available_chars: Set of available character IDs (defaults to self.available_characters)
        """
        if available_chars is None:
            available_chars = self.available_characters

        logger.debug(f"Routing message: '{message}'")
        logger.debug(f"Available characters: {available_chars}")

        # Build regex pattern for all character names
        char_pattern = "|".join(available_chars)

        # First check for explicit @mentions
        explicit_mentions = set(re.findall(r'@(\w+)', message.lower()))
        if explicit_mentions:
            # Include any other character names mentioned in the text as well
            name_mentions = set(re.findall(rf"\b({char_pattern})\b", message, flags=re.IGNORECASE))
            selected = (explicit_mentions | {n.lower() for n in name_mentions}).intersection(available_chars)
            if selected:
                logger.debug(f"Found explicit @mentions: {selected}")
                return selected

        # Look for any character names referenced in text (e.g. "eve ask atlas ...")
        name_mentions = set(re.findall(rf"\b({char_pattern})\b", message, flags=re.IGNORECASE))
        if name_mentions:
            result = {n.lower() for n in name_mentions}
            logger.debug(f"Found name mentions: {result}")
            return result

        # Check if the message begins with a character name followed by punctuation/space
        m = re.match(rf"^\s*({char_pattern})[,:\s]", message, flags=re.IGNORECASE)
        if m:
            return {m.group(1).lower()}

        # Fuzzy-match words to character names (handles misspellings)
        words = re.findall(r"\b\w+\b", message.lower())
        fuzzy_matches = set()

        # Direct prefix matching for common short forms
        for w in words:
            for prefix, char in self.prefix_map.items():
                if w.startswith(prefix) and char in available_chars:
                    fuzzy_matches.add(char)
                    break
            else:
                # Try fuzzy matching for longer words
                if len(w) >= 3:
                    match = difflib.get_close_matches(w, available_chars, n=1, cutoff=0.5)
                    if match:
                        fuzzy_matches.add(match[0])
        if fuzzy_matches:
            logger.debug(f"Found fuzzy matches: {fuzzy_matches}")
            return fuzzy_matches

        # Detect pattern '<char1> ask <char2>'
        ask_match = re.search(rf"({char_pattern})?\s*ask\s+({char_pattern})", message, flags=re.IGNORECASE)
        if ask_match:
            chars = {c.lower() for c in ask_match.groups() if c}
            if chars:
                return chars

        # Otherwise, use the LLM to decide
        if self.llm is None:
            # If LLM failed to initialize, default to self.default_characters
            logger.warning(f"Using rule-based fallback: {self.default_characters}")
            return self.default_characters.intersection(available_chars) or {next(iter(available_chars))}
            
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
            logger.error(f"Router LLM error: {e}")
            # If LLM call fails, default to available characters
            fallback = self.default_characters.intersection(available_chars)
            return fallback or {next(iter(available_chars))}

        try:
            result = json.loads(response.content)
            selected_chars = set(result.get("character_ids", []))
            # Filter to only available characters
            selected_chars = selected_chars.intersection(available_chars)

            if len(selected_chars) == 1:
                plural_re = re.compile(r"\b(guys|everyone|folks|team|all|друзья|ребят|ребята|вы оба|вы все)\b", re.IGNORECASE)
                if plural_re.search(message):
                    logger.debug("LLM chose one but plural cue present - expanding to all available characters.")
                    selected_chars = available_chars.copy()

            if not selected_chars:
                logger.warning(f"LLM suggested no valid characters. Defaulting to {self.default_characters}.")
                selected_chars = self.default_characters.intersection(available_chars) or {next(iter(available_chars))}

            logger.debug(f"Returning selected characters: {selected_chars}")
            return selected_chars
        except Exception as e:
            # Fallback if parsing fails
            logger.warning(f"Router parse error: {e}. Response: {response.content if hasattr(response, 'content') else 'None'}")
            final_fallback = self.default_characters.intersection(available_chars) or {next(iter(available_chars))}
            logger.warning(f"Returning characters from final fallback: {final_fallback}")
            return final_fallback
