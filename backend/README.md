# 🌱 Garden World Chat - LangGraph Prototype

A prototype implementation of a multi-character chat system using LangGraph, supporting multiple model providers and configurations.

## 🌟 Features

- **Multi-Model Support**: Works with OpenAI, Anthropic, Google, Groq, and OpenRouter models
- **Router Node**: Directs messages to appropriate characters
- **Character Nodes**: Individual AI characters with memory
- **Memory Management**: Comprehensive memory system with persistence and reflection
- **Time-Aware**: Characters acknowledge time gaps between conversations
- **Semantic Emotional Memory**: 11-dimensional emotions and 10-axis relationship model (P2 Memory Core)
- **Cost Tracking**: Tracks token usage and costs across providers
- **Configuration**: Easy setup via environment variables
- **CLI Interface**: Test the system from the command line
- **Streamlit UI**: Web interface for testing

## 🚀 Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/garden-chat.git
   cd garden-chat/prototype
   ```

2. **Install dependencies**
   ```bash
   pip install -r garden_graph/requirements.txt
   ```

3. **Create .env**
   Copy the provided template and fill in your keys **at the project root (`prototype/.env`)**:
   ```bash
   cp .env.example .env
   # then edit .env with your favourite editor
   ```
   Copy the example environment file and update with your API keys:
   ```bash
   cp garden_graph/.env.example garden_graph/.env
   # Edit the .env file with your API keys
   ```

4. **Test the configuration**
   ```bash
   python test_config.py
   ```

5. **Run the Streamlit UI**
   ```bash
   streamlit run garden_graph/streamlit_app.py
   ```
   
   **Or** use the CLI:
   ```bash
   python -m garden_graph.cli
   ```

## 🔧 Configuration

### Environment Variables & Supabase

All configuration is loaded from `.env` located at *project root* (`prototype/.env`). The example template `.env.example` already lists every variable with sensible defaults. Common parameters:

```env
# Required: At least one model provider API key
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key
GROQ_API_KEY=your_groq_key
OPENROUTER_API_KEY=your_openrouter_key

# Optional settings (local JSON persistence)
STORAGE_BACKEND=json
DISABLE_COST_TRACKING=false
BUDGET_LIMIT=1.0  # USD
ROUTER_MODEL=gpt-3.5-turbo  # Model to use for routing
```

### Model Support

The system supports various models from different providers. The provider is automatically detected based on the model name:

- **OpenAI**: `gpt-*` models (e.g., `gpt-3.5-turbo`, `gpt-4`)
- **Anthropic**: `claude-*` models (e.g., `claude-3-opus-20240229`)
- **Google**: `gemini-*` models (e.g., `gemini-pro`)
- **Groq**: `llama2-*`, `mixtral-*` models
- **OpenRouter**: Any model via `openrouter/` prefix

## 🏗️ Project Structure

```
garden_graph/
├── __init__.py         # Package initialization
├── config.py           # Configuration and model loading
├── router.py           # Message routing logic
├── character.py        # Character implementation
├── cost_tracker.py     # Token and cost tracking
├── graph.py            # Main LangGraph implementation
├── memory/             # Memory management system
│   ├── __init__.py     # Memory package initialization
│   └── manager.py      # MemoryManager implementation
├── tests/              # Test suite
│   ├── test_router.py  # Router tests
│   ├── test_memory_*.py # Memory system tests
├── cli.py              # Command-line interface
├── streamlit_app.py    # Web interface
└── requirements.txt    # Python dependencies
```

## 🧑‍💻 Development Guidelines

### Keep the CLI in Sync
If you add or change features that should be accessible to users, **update `garden_graph/cli.py` and its `--help` output**. The rule of thumb is: _everything you can do via API should be invokable from the command line_. Make sure to add or adjust flags and extend the README accordingly.

---

## 🧪 Testing

Run the test suite:

```bash
pytest test_*.py -v
```

Test the configuration and model loading:

```bash
python test_config.py
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [LangChain](https://python.langchain.com/) for the LLM framework
- [LangGraph](https://langchain-ai.github.io/langgraph/) for the graph-based orchestration
- All model providers for their amazing APIs

## Architecture

The system uses LangGraph to orchestrate message flow:
```
User Message → Router → Character Node(s) → Collator → UI
```

Each character maintains:
- Base personality prompt
- Weighted memories with sentiment and relevance scoring
- Time-awareness and conversation history
- Model selection (can be changed in UI)

## 🧠 Memory System

The P2 Memory Core phase has been completed with the following features:

- **Memory Management**: Full CRUD operations for memory records with weight-based relevance
- **Reflection Engine**: LLM-powered analysis of memory relevance to current context
- **Automatic Memory Creation**: Creates memories from significant messages or explicit commands
- **Sentiment Analysis**: Analyzes emotional sentiment of messages (-2 to +2 scale)
- **Forgiveness & Amplification**: Adjusts weights of opposite/matching sentiment memories
- **Persistence**: Save/load memory to/from JSON files with automatic archiving
- **Time Awareness**: Characters acknowledge time gaps between conversations

Memory records include:
- Unique identifier
- Character association
- Event text content
- Creation timestamp
- Last accessed timestamp
- Sentiment score (-2 to +2)
- Weight/importance (0.0 to 1.0)
- Active/archived status

## Next Steps

After completing P2 Memory Core:
1. Implement P3 Cost Tracker with budget alerts
2. Complete P4 Persistence & Sync with Core Data
3. Package LangGraph MVP as v0.1.0
4. Begin P6 iOS UI prototype implementation

## Credits

Created as part of the Garden iOS project using LangGraph and LangChain.

---
*(Last updated: 2025-05-21)*
