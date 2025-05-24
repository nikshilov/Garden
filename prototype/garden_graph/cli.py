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

# Global cost tracker - we'll pass this to the graph
cost_tracker = CostTracker()

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    """Print CLI header."""
    print("=" * 50)
    print("     🌱 GARDEN WORLD CHAT - LangGraph Prototype")
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
        cost_tracker=cost_tracker  # Pass the same cost tracker instance to the graph
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
    
    # Main chat loop
    while True:
        # Get user input
        user_message = input("\nYou: ")
        
        # Check for exit command
        if user_message.lower() in ["exit", "quit", "q"]:
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
