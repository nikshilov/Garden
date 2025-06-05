"""
Command-line interface to test the Garden world chat graph.
"""
import os
import sys
import json
from typing import Dict, List, Set
import asyncio
from datetime import datetime

from garden_graph.graph import create_world_chat_graph, format_cost_summary
from garden_graph.cost_tracker import CostTracker
from garden_graph.memory.manager import MemoryManager

# Global cost tracker - we'll pass this to the graph
cost_tracker = CostTracker()

# Initialize memory manager with existing memories
print("Initializing memory manager...")
# Пробуем загрузить существующую память, если файл не найден - создаем новый экземпляр
try:
    memory_manager = MemoryManager()
    default_path = memory_manager.get_default_filepath()
    print(f"Loading memories from {default_path}")
    if os.path.exists(default_path):
        memory_manager.load_from_file(default_path)
        print(f"Loaded {len(memory_manager._records)} memory records")
    else:
        print("No existing memories found, starting fresh")
        
    # Check for scheduled events
    event_count = len(memory_manager.scheduler._events)
    print(f"Loaded {event_count} scheduled events")
    
except Exception as e:
    print(f"Failed to initialize memory manager: {e}")
    memory_manager = MemoryManager()
    print("Created new memory manager")

# Enable memory debug mode
DEBUG_MEMORY = True

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    """Print CLI header."""
    print("=" * 50)
    print("     GARDEN WORLD CHAT - LangGraph Prototype")
    print("=" * 50)
    print("Characters: Eve, Atlas")
    print(f"Current session cost: ${cost_tracker.get_total_usd():.6f}")
    print("-" * 50)

async def main():
    """Run the CLI demo."""
    # Initialize the chat graph
    graph = create_world_chat_graph(
        router_model="gpt-3.5-turbo",
        character_models={
            "eve": "gpt-3.5-turbo",
            "atlas": "gpt-3.5-turbo"
        },
        cost_tracker=cost_tracker,  # Pass the same cost tracker instance to the graph
        memory_manager=memory_manager
    )
    
    # Set up initial state
    state = {
        "user_message": "",
        "message_history": [],
        "active_characters": set(),
        "selected_characters": set(), # For display - won't get emptied during processing
        "character_responses": {},
        "final_response": None,
        "costs": {}
    }
    
    # Welcome message
    clear_screen()
    print_header()
    print("\nWelcome to the Garden world chat!")
    print("Type '@eve' or '@atlas' to address characters directly.")
    print("Type 'exit' or 'quit' to end the session.\n")
    
    # Event checking - track last check time
    last_event_check = datetime.now()
    event_check_interval = 60  # seconds
    idle_threshold = 300  # seconds (5 minutes)
    last_activity = datetime.now()
    
    # Main chat loop
    while True:
        # Check for scheduled events and reminders
        now = datetime.now()
        time_since_check = (now - last_event_check).total_seconds()
        time_since_activity = (now - last_activity).total_seconds()
        
        # Only check for events if enough time has passed since last check
        if time_since_check >= event_check_interval:
            # Check for both characters when idle
            if time_since_activity >= idle_threshold:
                # User has been idle, check for events from any character
                for char_id in ["eve", "atlas"]:
                    pending_events = memory_manager.check_pending_events(char_id, now)
                    pending_reminders = memory_manager.check_pending_reminders(char_id, now)
                    
                    # If we have events due, notify the user
                    if pending_events or pending_reminders:
                        print(f"\n{'='*50}")
                        print(f"SCHEDULED EVENT NOTIFICATION FROM {char_id.upper()}:")
                        
                        if pending_events:
                            print(f"\nDue events:")
                            for event in pending_events:
                                print(f"• {event['time'].strftime('%H:%M')} - {event['description']}")
                                # Don't mark as completed since user isn't actively responding
                        
                        if pending_reminders:
                            print(f"\nUpcoming events (reminders):")
                            for reminder in pending_reminders:
                                print(f"• {reminder['time'].strftime('%H:%M')} - {reminder['description']}")
                        
                        print(f"{'='*50}\n")
            
            last_event_check = now
        
        # Non-blocking input with timeout to check for events periodically
        try:
            # Set timeout for input to enable periodic event checking
            # This is tricky in a standard CLI - we'll use a simple approach
            print("\nYou: ", end="", flush=True)
            user_message = input()
            last_activity = datetime.now()  # Update last activity time
        except Exception:  # Handle any input issues
            continue
        
        # Check for exit command
        if user_message.lower() in ["exit", "quit", "q"]:
            # Save memories before exiting
            memory_manager.save_to_file(memory_manager.get_default_filepath())
            print("Saved memories to disk. Goodbye!")
            break
            
        # Update state with user message
        state["user_message"] = user_message
        state["message_history"].append({
            "role": "user",
            "content": user_message,
            "timestamp": str(datetime.now().isoformat())
        })
        state["character_responses"] = {}
        
        # Run the graph
        print("\nThinking...", end="", flush=True)
        result = await graph.ainvoke(state)
        print("\r          \r", end="", flush=True)  # Clear "Thinking..."
        
        # Extract response and update state
        state = result
        
        # Print characters that were selected by the router
        # Use selected_characters (original selection) instead of active_characters (gets emptied during processing)
        selected_chars_list = list(state["selected_characters"]) if state["selected_characters"] else []
        selected_chars = ", ".join(selected_chars_list)
        print(f"\n[Router selected: {selected_chars}]")
        
        # Print cost summary for this interaction
        cost_summary = format_cost_summary(cost_tracker)
        if cost_summary:
            print(cost_summary)
        
        # Debug memory creation if enabled
        if DEBUG_MEMORY and "final_response" in state and memory_manager:
            # Check for new memories in the last interaction
            all_memories = memory_manager.all_active("eve")
            if all_memories:
                print(f"\n[DEBUG] Active memories for Eve: {len(all_memories)}")
                for mem in all_memories[-3:]:  # Show last 3 memories
                    emos = ", ".join(f"{k}:{v:.1f}" for k, v in list(mem.emotions.items())[:3]) if mem.emotions else "-"
                    print(f"[MEM] {mem.id[:8]}: '{mem.event_text[:50]}...' (w={mem.weight:.2f}, val={mem.emotions.get('valence',0):.1f}) emos=[{emos}]")
            else:
                print("\n[DEBUG] No active memories for Eve")
                
            # Show relationship snapshot diff (top 3 axes by abs value)
            rel = memory_manager.relationships.get("eve", {})
            if rel:
                top = sorted(rel.items(), key=lambda kv: -abs(kv[1]))[:3]
                axes_str = ", ".join(f"{ax}:{val:+.2f}" for ax, val in top)
                print(f"[DEBUG] Eve relationships top: {axes_str}")
            
            # Save memories after each interaction
            default_path = memory_manager.get_default_filepath()
            memory_manager.save_to_file(default_path)
            print(f"[DEBUG] Memories saved to file: {default_path}")
        
        # Print character responses
        if state["final_response"]:
            print(state["final_response"])
        elif len(state["character_responses"]) > 0:
            # Fallback in case final_response wasn't set properly
            for char_id, response in state["character_responses"].items():
                char_name = char_id.capitalize()
                print(f"\n**{char_name}**: {response}")
            
        # Show cost info
        total_usd = cost_tracker.get_total_usd()
        print(f"\n[Session cost: ${total_usd:.6f}]")
        
    # Print session summary
    print("\n" + "=" * 50)
    print("Session Summary")
    print("-" * 50)
    print(f"Total messages: {len([m for m in state['message_history'] if m['role'] == 'user'])}")
    print(f"Total cost: ${cost_tracker.get_total_usd():.6f}")
    model_breakdown = cost_tracker.get_model_breakdown()
    for model, cost in model_breakdown.items():
        print(f"  {model}: ${cost:.6f}")
    print("=" * 50)
    print("Thanks for using Garden World Chat!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
