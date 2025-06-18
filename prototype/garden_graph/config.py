"""
Configuration and model provider setup for Garden World Chat.
Loads settings from .env file and provides model initialization.
"""
import os
from typing import Dict, Any, Optional, Union
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# App Settings
DISABLE_COST_TRACKING = os.getenv("DISABLE_COST_TRACKING", "false").lower() == "true"
BUDGET_LIMIT = float(os.getenv("BUDGET_LIMIT", "1.0"))
ROUTER_MODEL = os.getenv("ROUTER_MODEL", "gpt-3.5-turbo")

# --- Memory / Emotion thresholds (configurable) ---
# Minimum absolute significance score required to persist a message as a memory.
# Default 0.25 (range 0‒1).  Lower = store more memories; higher = store fewer.
MEM_SIGNIFICANCE_THRESHOLD = float(os.getenv("MEM_SIGNIFICANCE_THRESHOLD", "0.25"))

# Threshold for applying forgiveness/amplification logic for existing memories.
EMOTIONAL_IMPACT_THRESHOLD = float(os.getenv("EMOTIONAL_IMPACT_THRESHOLD", "0.5"))

# --- Persistence backend ---
# 'json' (default) | 'supabase'
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "json").lower()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# --- Supervisor / Producer thresholds ---
# Accumulated emotional 'energy' triggering prompt refresh suggestion
PROMPT_REFRESH_ENERGY_THRESHOLD = float(os.getenv("PROMPT_REFRESH_ENERGY_THRESHOLD", "8.0"))
# Significance at which evaluate_message suggests 'highlight'
HIGHLIGHT_IMPACT_THRESHOLD = float(os.getenv("HIGHLIGHT_IMPACT_THRESHOLD", "1.0"))

# Model Provider Mappings
MODEL_PROVIDERS = {
    # OpenAI models
    "gpt-": "openai",
    # Anthropic models
    "claude-": "anthropic",
    # Google models
    "gemini-": "google",
    "gemini": "google",
    "gemma-": "google",
    # Groq models
    "llama2-": "groq",
    "mixtral-": "groq",
    "llama3-": "groq",
    "mixtral": "groq",
    # OpenRouter models (various providers)
    "openrouter/": "openrouter"
}

def get_model_provider(model_name: str) -> str:
    """Determine the provider for a given model name."""
    if not model_name:
        return "openai"  # Default provider
        
    model_lower = model_name.lower()
    for prefix, provider in MODEL_PROVIDERS.items():
        if model_lower.startswith(prefix):
            return provider
    return "openai"  # Fallback to OpenAI

def get_llm(model_name: str, temperature: float = 0.7, **kwargs):
    """Get an LLM instance based on model name."""
    provider = get_model_provider(model_name)
    
    try:
        if provider == "openai" and OPENAI_API_KEY:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_name,
                temperature=temperature,
                openai_api_key=OPENAI_API_KEY,
                **kwargs
            )
            
        elif provider == "anthropic" and ANTHROPIC_API_KEY:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=model_name,
                temperature=temperature,
                anthropic_api_key=ANTHROPIC_API_KEY,
                **kwargs
            )
            
        elif provider == "google" and GOOGLE_API_KEY:
            from langchain_google_genai import ChatGoogleGenerativeAI
            # Google's API expects model names without the 'gemini-' prefix
            google_model = model_name.replace('gemini-', '') if 'gemini' in model_name else model_name
            return ChatGoogleGenerativeAI(
                model=google_model,
                temperature=temperature,
                google_api_key=GOOGLE_API_KEY,
                **kwargs
            )
            
        elif provider == "groq" and GROQ_API_KEY:
            from langchain_groq import ChatGroq
            return ChatGroq(
                model_name=model_name,
                temperature=temperature,
                groq_api_key=GROQ_API_KEY,
                **kwargs
            )
            
        elif provider == "openrouter" and OPENROUTER_API_KEY:
            from langchain_openai import ChatOpenAI
            # For OpenRouter, we need to add the headers to model_kwargs instead
            model_kwargs = kwargs.get("model_kwargs", {})
            model_kwargs["headers"] = {"HTTP-Referer": "https://github.com/your-github-username/garden-chat"}
            
            return ChatOpenAI(
                model=model_name,
                temperature=temperature,
                openai_api_key=OPENROUTER_API_KEY,
                openai_api_base="https://openrouter.ai/api/v1",
                model_kwargs=model_kwargs,
                **{k: v for k, v in kwargs.items() if k != "model_kwargs"}
            )
            
    except ImportError as e:
        print(f"Error importing {provider} package: {e}. Please install required packages.")
        raise
    
    raise ValueError(f"No valid API key found for provider: {provider}")

def get_embedding_model():
    """Get default embedding model."""
    if OPENAI_API_KEY:
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
    elif GOOGLE_API_KEY:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(google_api_key=GOOGLE_API_KEY)
    else:
        raise ValueError("No valid API key found for embedding models")

def validate_environment() -> Dict[str, bool]:
    """Check if required API keys are set."""
    return {
        "openai": bool(OPENAI_API_KEY),
        "anthropic": bool(ANTHROPIC_API_KEY),
        "google": bool(GOOGLE_API_KEY),
        "groq": bool(GROQ_API_KEY),
        "openrouter": bool(OPENROUTER_API_KEY)
    }
