"""
Streamlit UI for testing the Garden World Chat LangGraph prototype.
Run with: streamlit run streamlit_app.py
"""
import streamlit as st
import asyncio
import os
import sys, pathlib

# Ensure project root (prototype directory) is on PYTHONPATH so that internal
# package imports like `garden_graph.router` work when running this script
# directly via `streamlit run`.
ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from datetime import datetime
import json

from graph import create_world_chat_graph, format_cost_summary
from cost_tracker import CostTracker
from character import Character

# Page config
st.set_page_config(
    page_title="Garden World Chat",
    page_icon="🌱",
    layout="wide"
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
    
if "graph_state" not in st.session_state:
    st.session_state.graph_state = {
        "user_message": "",
        "message_history": [],
        "active_characters": set(),
        "character_responses": {},
        "final_response": None,
        "costs": {}
    }
    
if "cost_tracker" not in st.session_state:
    st.session_state.cost_tracker = CostTracker()
    
if "graph" not in st.session_state:
    # Initialize the graph
    st.session_state.graph = create_world_chat_graph(
        router_model="gpt-4o",
        character_models={
            "eve": "gpt-4o",
            "atlas": "gpt-4o"
        }
    )

# Sidebar - Configuration
st.sidebar.title("🌱 Garden Chat")

# Model selection
st.sidebar.subheader("Character Models")
router_model = st.sidebar.selectbox(
    "Router Model",
    ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o"],
    index=3
)

# Eve model
eve_model = st.sidebar.selectbox(
    "Eve's Model",
    ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o", "claude-3-sonnet"],
    index=3
)

# Atlas model
atlas_model = st.sidebar.selectbox(
    "Atlas's Model",
    ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o", "claude-3-sonnet"],
    index=3
)

# Budget settings
st.sidebar.subheader("Budget")
budget = st.sidebar.number_input("Budget limit (USD)", min_value=0.0, value=1.0, step=0.1)
st.session_state.cost_tracker.set_budget_limit(budget)

# Display current cost
total_cost = st.session_state.cost_tracker.get_total_usd()
st.sidebar.metric("Current Cost", f"${total_cost:.6f}", delta=f"{(total_cost/budget)*100:.1f}%" if budget > 0 else None)

# API Key input
st.sidebar.subheader("API Keys")
openai_key = st.sidebar.text_input("OpenAI API Key", type="password")
anthropic_key = st.sidebar.text_input("Anthropic API Key", type="password")

if openai_key:
    os.environ["OPENAI_API_KEY"] = openai_key
if anthropic_key:
    os.environ["ANTHROPIC_API_KEY"] = anthropic_key

# Reset chat button
if st.sidebar.button("Reset Chat"):
    st.session_state.messages = []
    st.session_state.graph_state = {
        "user_message": "",
        "message_history": [],
        "active_characters": set(),
        "character_responses": {},
        "final_response": None,
        "costs": {}
    }
    st.session_state.cost_tracker.reset()
    st.rerun()

# Main chat interface
st.title("Garden World Chat")
st.caption("Chat with Eve and Atlas in a shared world. Try addressing them directly with @eve or @atlas.")

# Display message history
for message in st.session_state.messages:
    with st.chat_message(message["role"].lower()):
        st.markdown(message["content"])
        
        # Show metadata for AI messages
        if message["role"] != "user" and "metadata" in message:
            with st.expander("Message Metadata"):
                st.json(message["metadata"])

# Chat input
if prompt := st.chat_input("Your message here..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
        
    # Update graph state
    st.session_state.graph_state["user_message"] = prompt
    st.session_state.graph_state["message_history"].append({
        "role": "user",
        "content": prompt,
        "timestamp": str(datetime.now().isoformat())
    })
    st.session_state.graph_state["character_responses"] = {}
    
    # Show thinking spinner while processing
    with st.spinner("Characters are thinking..."):
        # Invoke the graph asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            st.session_state.graph.ainvoke(st.session_state.graph_state)
        )
        loop.close()
        
        # Update state
        st.session_state.graph_state = result
        
        # Display which characters were selected
        active_chars = ", ".join(st.session_state.graph_state["active_characters"])
        
        # Extract responses
        if st.session_state.graph_state["final_response"]:
            response_text = st.session_state.graph_state["final_response"]
            
            # Split the responses by character
            for char_id in st.session_state.graph_state["active_characters"]:
                if char_id in st.session_state.graph_state["character_responses"]:
                    char_name = {"eve": "Eve", "atlas": "Atlas"}.get(char_id, char_id.capitalize())
                    char_response = st.session_state.graph_state["character_responses"][char_id]
                    
                    # Add to streamlit chat history
                    st.session_state.messages.append({
                        "role": char_name,
                        "content": char_response,
                        "metadata": {
                            "character_id": char_id,
                            "selected_by": "router",
                            "timestamp": str(datetime.now().isoformat())
                        }
                    })
                    
                    # Display character response
                    with st.chat_message(char_name.lower()):
                        st.markdown(char_response)
                        with st.expander("Message Info"):
                            st.write(f"Character: {char_name}")
                            st.write(f"Selected by: Router")
                            # Show top memories if we had a MemoryManager
                            
    # Show cost update
    st.sidebar.metric("Current Cost", f"${st.session_state.cost_tracker.get_total_usd():.6f}",
                      delta=f"+ ${0.00:.6f}")  # Would track delta per message
    
# Footer
st.caption("Garden LangGraph Prototype — P1 MVP")
