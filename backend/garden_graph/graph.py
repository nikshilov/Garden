"""
Main LangGraph orchestration for Garden world chat.
"""
import logging
from typing import Dict, List, Tuple, Set, Any, Optional, TypedDict, Annotated, cast
from langchain_core.messages import BaseMessage
import langgraph
from langgraph.graph import StateGraph, END
import json

logger = logging.getLogger("garden.graph")

from garden_graph.router import Router
from garden_graph.character import Character, CHARACTER_TEMPLATES
from garden_graph.cost_tracker import CostTracker
from garden_graph.config import ROUTER_MODEL, INTIMACY_AFFECTION_THRESHOLD, INTIMACY_AROUSAL_THRESHOLD
from datetime import datetime, timezone



# Define state schema
class ChatState(TypedDict):
    user_message: str
    intimacy_mode: bool
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

    # Build character info for router
    char_info = {}
    for char_id in character_models:
        template = CHARACTER_TEMPLATES.get(char_id, {})
        char_info[char_id] = {
            "name": template.get("name", char_id.capitalize()),
            "description": template.get("prompt", "")[:100]  # First 100 chars as description
        }
    router = Router(model_name=router_model, characters=char_info)

    # Define nodes
    def _should_auto_intimate(char_id: str) -> bool:
        """Return True if intimacy mode should auto-activate for this character."""
        if memory_manager is None:
            return False
        rel = memory_manager.relationships.get(char_id, {})
        affection = rel.get("affection", 0.0)
        mood_vec = memory_manager._get_mood_vector(char_id)
        arousal = mood_vec.get("arousal", 0.0)
        return affection >= INTIMACY_AFFECTION_THRESHOLD and arousal >= INTIMACY_AROUSAL_THRESHOLD

    def route_message(state: ChatState) -> Dict:
        """Router node decides which characters should respond."""
        # If we already have a routing queue, skip re-routing (prevents duplicate routing on re-entry)
        if state.get("active_characters"):
            # No update – let remaining queue be processed
            return {}
        
        user_message = state["user_message"].strip()
        # Early handle '/intimate' commands before routing/LLM usage
        if user_message.lower().startswith("/intimate"):
            parts = user_message.split()
            if len(parts) == 2 and parts[1] in {"on", "off"}:
                enabled = parts[1] == "on"
                return {"intimacy_mode": enabled, "final_response": f"[Intimacy mode {'ON' if enabled else 'OFF'}]"}
            if len(parts) == 3 and parts[1] == "model":
                model_name = parts[2]
                return {"intimate_model": model_name, "final_response": f"[Intimacy model set to {model_name}]"}
        history = state.get("message_history", [])
        
        # Используем существующий метод router.route для определения активных персонажей
        active_chars = router.route(user_message, history)
        # Auto-trigger intimacy if not already active
        intimacy_triggered = False
        if not state.get("intimacy_mode"):
            for cid in active_chars:
                if _should_auto_intimate(cid):
                    intimacy_triggered = True
                    active_chars = [cid]
                    logger.info(f"Auto-activated Intimacy Mode for {cid}")
                    break
        # If intimacy mode already on, limit to the first character
        if state.get("intimacy_mode") or intimacy_triggered:
            active_chars = active_chars[:1] if active_chars else []
        logger.info(f"Router selected: {active_chars}")
        
        # Analyze message and create memories / schedule events
        if memory_manager and active_chars:
            for char_id in active_chars:
                try:
                    memory_manager.analyze_message(char_id, user_message, is_user_message=True)
                except Exception as e:
                    logger.error(f"Error analyzing message for {char_id}: {e}")
        
        # Save memory and events state after processing a message
        if memory_manager:
            try:
                memory_manager.save_to_file(memory_manager.get_default_filepath())
                logger.debug(f"Saved memory state")
            except Exception as e:
                logger.error(f"Error saving memory state: {e}")
        
        # Update active characters in state
        # Return both the active queue and the original selection for downstream nodes
        result = {
            "active_characters": set(active_chars),
            "selected_characters": set(active_chars),
        }
        if intimacy_triggered:
            result["intimacy_mode"] = True
        return result
    
    def character_node(state: ChatState, character_id: str) -> Dict[str, Any]:
        """Character node generates a response for a specific character."""
        logger.debug(f"character_node:{character_id} entered with active_characters: {state.get('active_characters')}, selected_characters: {state.get('selected_characters')}")
            
        user_message = state["user_message"]
        history = state["message_history"]
        
        # Get character response
        if state.get("intimacy_mode"):
            from garden_graph.intimate_agent import IntimateAgent
            agent = IntimateAgent(model_name=state.get("intimate_model"))
            response = agent.respond(user_message, history)
        else:
            character = characters[character_id]
            response = character.respond(user_message, history)
        logger.debug(f"character_node:{character_id} generating response for '{user_message}'")
        logger.info(f"character_node:{character_id} generated response: '{response[:30]}...'")
        
        # Record cost for this character model interaction
        if state.get("intimacy_mode"):
            model = agent.model_name
        else:
            model = character_models.get(character_id, "gpt-3.5-turbo")
        # We don't have exact token counts, but we can estimate based on length
        prompt_tokens = len(user_message) // 4  # Rough estimate
        completion_tokens = len(response) // 4   # Rough estimate
        cost_tracker.record(model, prompt_tokens, completion_tokens, category="intimacy" if state.get("intimacy_mode") else "general")
        
        # Create new history entry
        new_message = {
            "role": characters[character_id].name,
            "content": response,
            "character_id": character_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Return updates - don't modify state directly
        # Add this character's response, new message to history, and remove self from active queue
        remaining = state.get("active_characters", set()) - {character_id}
        updates = {
            "character_responses": {**state.get("character_responses", {}), character_id: response},
            "message_history": [*state.get("message_history", []), new_message],
            "active_characters": remaining,
        }
        
        logger.debug(f"character_node:{character_id} returning updates: {str(updates)[:100]}...")
        return updates
    
    def collate_node(state: ChatState) -> Dict[str, Any]:
        """Collate responses from all active characters."""
        logger.debug(f"collate_node entered with character_responses: {list(state['character_responses'].keys())}")
        logger.debug(f"collate_node selected_characters: {state.get('selected_characters')}")
        
        # Get all character responses
        responses = state["character_responses"]
        selected_chars = state.get("selected_characters", set())
        
        # Handle '/intimate' commands
        user_message = state["user_message"].strip()
        if user_message.lower().startswith("/intimate"):
            parts = user_message.split()
            if len(parts) == 2 and parts[1] in {"on", "off"}:
                enabled = parts[1] == "on"
                return {"intimacy_mode": enabled, "final_response": f"[Intimacy mode {'ON' if enabled else 'OFF'}]"}
            if len(parts) == 3 and parts[1] == "model":
                model_name = parts[2]
                return {"intimate_model": model_name, "final_response": f"[Intimacy model set to {model_name}]"}

        # Format the final response
        response_parts = []
        for char_id in selected_chars:
            if char_id in responses:
                response_parts.append(f"**{characters[char_id].name}**: {responses[char_id]}")
        
        final_response = "\n\n".join(response_parts)
        logger.debug(f"collate_node final response: '{final_response[:50]}...'")
        
        # Memory management: process conversation and reflect
        if memory_manager is not None:
            for char_id in state.get("selected_characters", set()):
                if char_id not in responses:
                    continue  # Skip if no response from this character
                    
                # Get character's LLM if available for better memory processing
                char_llm = None
                if char_id in characters and hasattr(characters[char_id], 'llm'):
                    char_llm = characters[char_id].llm
                
                # 1. Create new memories from messages (if significant)
                user_message = state["user_message"]
                char_response = responses[char_id]
                
                # skip processing '/intimate' commands
                if user_message.startswith('/intimate'):
                    continue
                created_memories = memory_manager.process_conversation_update(
                    character_id=char_id,
                    user_message=user_message,
                    character_response=char_response,
                    llm=char_llm
                )
                
                if created_memories:
                    logger.info(f"Created {len(created_memories)} new memories for {char_id}")
                
                # 2. Run reflection on existing memories
                context = user_message
                if len(state.get("message_history", [])) > 0:
                    # Add some history for better context if available
                    history_context = "\n".join([msg["content"] for msg in state.get("message_history", [])[-3:]])
                    context = f"{history_context}\n{context}"
                
                memory_manager.reflect(char_id, context=context, llm=char_llm)
        return {"final_response": final_response}
    
    def cross_talk_node(state: ChatState) -> Dict[str, Any]:
        """Allow characters to respond to each other's initial responses."""
        logger.debug(f"cross_talk_node entered with character_responses: {list(state['character_responses'].keys())}")
        
        responses = state["character_responses"]
        selected_chars = state.get("selected_characters", set())
        
        # Only do cross-talk if multiple characters responded
        if len(responses) < 2:
            logger.debug(f"cross_talk_node: only {len(responses)} character(s) responded, skipping cross-talk")
            return {}
        
        # Let each character see the other's response and optionally react
        cross_talk_responses = {}
        for char_id in selected_chars:
            if char_id not in responses:
                continue
                
            # Build context showing other characters' responses
            other_responses = []
            for other_id, other_response in responses.items():
                if other_id != char_id:
                    other_responses.append(f"{characters[other_id].name}: {other_response}")
            
            if not other_responses:
                continue
            
            # Ask character if they want to add to their response
            cross_talk_prompt = f"""The user asked: "{state['user_message']}"

Other characters responded:
{chr(10).join(other_responses)}

After seeing what {' and '.join([characters[oid].name for oid in responses if oid != char_id])} said:
- Would you like to add a complementary perspective?
- Do you have a different viewpoint on any specific point?
- Is there something you'd like to highlight or clarify?

Be natural in your response - you may agree, partially agree, or have a different take. If you genuinely have nothing to add, just respond with "pass".
Keep it brief (1-2 sentences) and respond in the same language as the conversation."""

            # Inject character-to-character relationship context
            if memory_manager:
                try:
                    char_rel_ctx = memory_manager.char_relationship_context(char_id)
                    if char_rel_ctx:
                        cross_talk_prompt += "\n\n" + char_rel_ctx
                except Exception as e:
                    logger.warning(f"cross_talk_node:{char_id} failed to get relationship context: {e}")

            character = characters[char_id]
            logger.debug(f"cross_talk_node:{char_id} generating cross-talk response")
            
            # Get character's cross-talk response
            from langchain_core.messages import SystemMessage, HumanMessage
            messages = [
                SystemMessage(content=character._build_prompt_with_memories()),
                HumanMessage(content=cross_talk_prompt)
            ]
            
            try:
                cross_talk_response = character.llm.invoke(messages).content.strip()
                
                # Record cost
                model = character_models.get(char_id, "gpt-3.5-turbo")
                prompt_tokens = len(cross_talk_prompt) // 4
                completion_tokens = len(cross_talk_response) // 4
                cost_tracker.record(model, prompt_tokens, completion_tokens, category="intimacy" if state.get("intimacy_mode") else "general")
                
                # Only add if character has something to say
                if cross_talk_response.lower() != "pass" and len(cross_talk_response) > 5:
                    cross_talk_responses[char_id] = cross_talk_response
                    logger.debug(f"cross_talk_node:{char_id} added cross-talk: '{cross_talk_response[:30]}...'")

                    # Store cross-talk interaction in both characters' memories
                    if memory_manager:
                        for other_id in responses:
                            if other_id != char_id:
                                try:
                                    memory_manager.process_cross_talk(
                                        from_char=char_id,
                                        to_char=other_id,
                                        interaction_text=responses[other_id],  # what the other said
                                        response_text=cross_talk_response,      # how this char reacted
                                    )
                                except Exception as e:
                                    logger.warning(f"cross_talk_node: failed to process cross-talk memory for {char_id}->{other_id}: {e}")
                else:
                    logger.debug(f"cross_talk_node:{char_id} character passed on cross-talk")
                    
            except Exception as e:
                logger.error(f"cross_talk_node:{char_id} error during cross-talk: {e}")
                continue
        
        # Merge cross-talk responses with original responses
        if cross_talk_responses:
            merged_responses = {}
            for char_id in selected_chars:
                if char_id in responses:
                    merged_responses[char_id] = responses[char_id]
                    if char_id in cross_talk_responses:
                        merged_responses[char_id] += f"\n\n*({cross_talk_responses[char_id]})*"
            
            logger.debug(f"cross_talk_node: added {len(cross_talk_responses)} cross-talk responses")
            return {"character_responses": merged_responses}
        
        logger.debug(f"cross_talk_node: no cross-talk responses generated")
        return {}
        
    # Define router branch - sequential processing
    def router_branch(state: ChatState) -> str:
        """Return next node to handle one character at a time."""
        logger.debug(f"router_branch entered with active_characters: {state['active_characters']}")
        if not state["active_characters"]:
            logger.debug(f"router_branch: no active characters left, going to cross_talk")
            return "cross_talk"
        # Peek at the first character without mutating state
        next_char = next(iter(state["active_characters"]))
        logger.debug(f"router_branch: next character: {next_char}, active: {state['active_characters']}")
        return f"character_{next_char}"
    
    # Build the graph - simplified for latest LangGraph API
    builder = StateGraph(ChatState)
    
    # Add nodes
    builder.add_node("router", route_message)
    builder.add_node("cross_talk", cross_talk_node)
    builder.add_node("collator", collate_node)
    
    # Add character nodes
    for char_id in characters:
        builder.add_node(f"character_{char_id}", 
                         lambda state, char_id=char_id: character_node(state, char_id))
    
    # Add conditional routing
    builder.add_conditional_edges("router", router_branch)
    
    # For each character node add conditional edge: back to router if more chars else cross_talk
    for char_id in characters:
        def _after_char(state: ChatState, *, _char_id=char_id):
            # If there are still characters left, process next, else go to cross_talk
            if state["active_characters"]:
                return "router"
            return "cross_talk"
        builder.add_conditional_edges(f"character_{char_id}", _after_char)
    
    # Cross-talk always goes to collator
    builder.add_edge("cross_talk", "collator")
    
    # Connect collator to END
    builder.add_edge("collator", END)
    
    # Set entry point
    builder.set_entry_point("router")
    
    # Compile the graph
    return builder.compile()

def format_cost_summary(cost_tracker) -> str:
    """Format cost summary for display."""
    if not cost_tracker or not hasattr(cost_tracker, 'get_total_usd'):
        return "Cost tracking disabled"

    total_usd = cost_tracker.get_total_usd()
    model_breakdown = cost_tracker.get_model_breakdown()
    cat_breakdown = cost_tracker.get_category_breakdown() if hasattr(cost_tracker, 'get_category_breakdown') else {}

    summary_lines = [f"Cost: ${total_usd:.6f}"]
    for model, usd in model_breakdown.items():
        summary_lines.append(f"  {model}: ${usd:.6f}")
    if cat_breakdown:
        cats = ", ".join(f"{c}:{v:.4f}$" for c,v in cat_breakdown.items())
        summary_lines.append(f"  by category → {cats}")
    return "\n".join(summary_lines)
