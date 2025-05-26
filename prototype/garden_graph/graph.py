"""
Main LangGraph orchestration for Garden world chat.
"""
from typing import Dict, List, Tuple, Set, Any, Optional, TypedDict, Annotated, cast
from langchain_core.messages import BaseMessage
import langgraph
from langgraph.graph import StateGraph, END
import json

from garden_graph.router import Router
from garden_graph.character import Character
from garden_graph.cost_tracker import CostTracker
from garden_graph.config import ROUTER_MODEL
from datetime import datetime

# Define state schema
class ChatState(TypedDict):
    user_message: str
    message_history: List[Dict]
    active_characters: Set[str]
    selected_characters: Set[str]  # This preserves the original selection for display
    character_responses: Dict[str, str]
    final_response: Optional[str]
    costs: Dict

# Create the World Chat graph
def create_world_chat_graph(
    router_model: str = ROUTER_MODEL,
    character_models: Dict[str, str] = None,
    cost_tracker: Optional[CostTracker] = None,
    memory_manager=None
) -> StateGraph:
    """Create the main LangGraph for world chat."""
    
    # Initialize components
    router = Router(model_name=router_model)
    
    # Use provided cost tracker or create a new one
    if cost_tracker is None:
        cost_tracker = CostTracker()
    
    # Initialize characters with specified models
    if character_models is None:
        character_models = {
            "eve": "gpt-3.5-turbo",
            "atlas": "gpt-3.5-turbo"
        }
        
    characters = {
        char_id: Character(char_id, model_name=model, memory_manager=memory_manager)
        for char_id, model in character_models.items()
    }
    
    # Define nodes
    def route_node(state: ChatState) -> Dict[str, Any]:
        user_message_content = state.get("user_message", "USER_MESSAGE_NOT_FOUND_IN_STATE")
        active_chars_in_state = state.get('active_characters', set())
        print(f"[Graph:route_node] Entered. User message: '{user_message_content}'. Current active_characters in state: {active_chars_in_state}")
        
        # user_message is a required key in ChatState, history is List[Dict]
        user_message = state["user_message"] 
        history = state.get("message_history", [])

        # Route only if no active characters yet
        # The router.py's route method is guaranteed to return a non-empty set
        if not active_chars_in_state: # Use the variable fetched safely
            print("[Graph:route_node] No active characters in state, calling router.route().")
            selected_character_ids = router.route(user_message, history) # router.py returns a set
            
            # Ensure we're returning a set, not a dict
            # Also save a copy to selected_characters for display in CLI
            update_payload = {
                "active_characters": selected_character_ids,
                "selected_characters": selected_character_ids.copy() if hasattr(selected_character_ids, 'copy') else set(selected_character_ids)
            }
            print(f"[Graph:route_node] router.route() returned: {selected_character_ids}. Returning update to graph state: {update_payload}")
            return update_payload # Return only the changed part of the state
        else:
            print(f"[Graph:route_node] Characters {active_chars_in_state} already active. Skipping router.route(). Returning empty update.")
            return {} # Return empty dict if no changes are made
    
    def character_node(state: ChatState, character_id: str) -> Dict[str, Any]:
        """Character node generates a response for a specific character."""
        print(f"[Graph:character_node:{character_id}] Entered with active_characters: {state.get('active_characters')}, selected_characters: {state.get('selected_characters')}")
            
        user_message = state["user_message"]
        history = state["message_history"]
        
        # Get character response
        character = characters[character_id]
        print(f"[Graph:character_node:{character_id}] Generating response for '{user_message}'")
        response = character.respond(user_message, history)
        print(f"[Graph:character_node:{character_id}] Generated response: '{response[:30]}...'")
        
        # Record cost for this character model interaction
        model = character_models.get(character_id, "gpt-3.5-turbo")
        # We don't have exact token counts, but we can estimate based on length
        prompt_tokens = len(user_message) // 4  # Rough estimate
        completion_tokens = len(response) // 4   # Rough estimate
        cost_tracker.record(model, prompt_tokens, completion_tokens)
        
        # Create new history entry
        new_message = {
            "role": character.name,
            "content": response,
            "character_id": character_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Return updates - don't modify state directly
        # Add this character's response and the new message to history
        updates = {
            "character_responses": {**state.get("character_responses", {}), character_id: response},
            "message_history": [*state.get("message_history", []), new_message]
        }
        
        print(f"[Graph:character_node:{character_id}] Returning updates: {str(updates)[:100]}...")
        return updates
    
    def collate_node(state: ChatState) -> Dict[str, Any]:
        """Collate responses from all active characters."""
        print(f"[Graph:collate_node] Entered with character_responses: {list(state.get('character_responses', {}).keys())}")
        print(f"[Graph:collate_node] selected_characters: {state.get('selected_characters')}")
        
        responses = state.get("character_responses", {})
        
        # Format the final output
        final_response = ""
        # Use selected_characters instead of active_characters (which gets emptied)
        for char_id in state.get("selected_characters", set()):
            if char_id in responses:
                char_name = characters[char_id].name
                final_response += f"**{char_name}**: {responses[char_id]}\n\n"
        
        print(f"[Graph:collate_node] Final response: '{final_response[:30]}...'")
        # Reflection – simple stub for now
        if memory_manager is not None:
            for char_id in state.get("selected_characters", set()):
                memory_manager.reflect_stub(char_id, context=state["user_message"])
        return {"final_response": final_response}
        
    # Build the graph - simplified for latest LangGraph API
    builder = StateGraph(ChatState)
    
    # Add nodes
    builder.add_node("router", route_node)
    builder.add_node("collator", collate_node)
    
    # Add character nodes
    for char_id in characters:
        builder.add_node(f"character_{char_id}", 
                         lambda state, char_id=char_id: character_node(state, char_id))
    
    # Define router branch - sequential processing
    def router_branch(state: ChatState) -> str:
        """Return next node to handle one character at a time."""
        print(f"[Graph:router_branch] Entered with active_characters: {state['active_characters']}")
        if not state["active_characters"]:
            print(f"[Graph:router_branch] No active characters left, going to collator")
            return "collator"
        # Pop one character to handle now
        next_char = state["active_characters"].pop()
        print(f"[Graph:router_branch] Popped character: {next_char}, remaining: {state['active_characters']}")
        # Keep the remaining characters in state for later
        return f"character_{next_char}"
    
    # Add conditional routing
    builder.add_conditional_edges("router", router_branch)
    
    # For each character node add conditional edge: back to router if more chars else collate
    for char_id in characters:
        def _after_char(state: ChatState, *, _char_id=char_id):
            # If there are still characters left, process next, else collate
            if state["active_characters"]:
                return "router"
            return "collator"
        builder.add_conditional_edges(f"character_{char_id}", _after_char)
    
    # Connect collator to END
    builder.add_edge("collator", END)
    
    # Set entry point
    builder.set_entry_point("router")
    
    # Compile the graph
    return builder.compile()

def format_cost_summary(costs: Dict) -> str:
    """Format cost summary for display."""
    total_usd = sum(cost["usd"] for cost in costs.values())
    
    summary = f"Cost: ${total_usd:.6f}\n"
    for model, cost in costs.items():
        prompt_tokens = cost.get("prompt_tokens", 0)
        completion_tokens = cost.get("completion_tokens", 0)
        total_tokens = prompt_tokens + completion_tokens
        model_usd = cost.get("usd", 0)
        
        summary += f"  {model}: {total_tokens} tokens, ${model_usd:.6f}\n"
        
    return summary
