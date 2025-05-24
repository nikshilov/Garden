# 🌱 Garden World Chat - LangGraph Prototype

A prototype implementation of a multi-character chat system using LangGraph, supporting multiple model providers and configurations.

## 🌟 Features

- **Multi-Model Support**: Works with OpenAI, Anthropic, Google, Groq, and OpenRouter models
- **Router Node**: Directs messages to appropriate characters
- **Character Nodes**: Individual AI characters with memory
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

3. **Configure API keys**
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

### Environment Variables

Create a `.env` file in the `garden_graph` directory with your API keys:

```env
# Required: At least one model provider API key
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key
GROQ_API_KEY=your_groq_key
OPENROUTER_API_KEY=your_openrouter_key

# Optional settings
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
├── cli.py              # Command-line interface
├── streamlit_app.py    # Web interface
└── requirements.txt    # Python dependencies
```

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
- Weighted memories that decay over time
- Model selection (can be changed in UI)

## Next Steps

After validating the prototype:
1. Port to Swift LangGraph implementation
2. Implement detailed memory and reflection algorithms
3. Add Core Data persistence
4. Build SwiftUI layer

## Credits

Created as part of the Garden iOS project using LangGraph and LangChain.

---
*(Last updated: 2025-05-21)*
