"""
Test script to verify configuration and model loading.
"""
import os
import sys
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from garden_graph.config import validate_environment, get_llm

def test_environment():
    """Test if environment variables are loaded correctly."""
    print("\n=== Testing Environment ===")
    env_vars = validate_environment()
    
    print("\nAPI Key Status:")
    for provider, has_key in env_vars.items():
        status = "✅ Found" if has_key else "❌ Missing"
        print(f"{provider.upper()}: {status}")
    
    print("\nNote: At least one model provider API key is required.")
    return any(env_vars.values())

def test_model_loading():
    """Test loading different model providers."""
    print("\n=== Testing Model Loading and Provider Detection ===")
    
    # First, just test provider detection without API calls
    models_to_check = [
        ("gpt-3.5-turbo", "OpenAI"),
        ("gpt-4", "OpenAI"),
        ("claude-3-opus-20240229", "Anthropic"),
        ("claude-instant-1.2", "Anthropic"),
        ("gemini-pro", "Google"),
        ("gemma-7b", "Google"),
        ("llama2-70b-4096", "Groq"),
        ("mixtral-8x7b", "Groq"),
        ("openrouter/auto", "OpenRouter"),
    ]
    
    print("\nTesting provider detection:\n")
    for model_name, expected_provider in models_to_check:
        from garden_graph.config import get_model_provider
        detected = get_model_provider(model_name)
        result = "✅" if detected == expected_provider.lower() else "❌"
        print(f"{result} {model_name} -> {detected} (expected: {expected_provider.lower()})")
    
    # Then test actually loading models (one per provider to save API costs)
    # Enable API calls for testing
    test_api_calls = True
    
    if test_api_calls:
        models_to_test = [
            ("gpt-3.5-turbo", "OpenAI"),
            ("claude-3-haiku-20240307", "Anthropic"),
            ("gemini-pro", "Google"),
            ("llama2-70b-4096", "Groq"),
            ("openrouter/mistralai/mistral-small", "OpenRouter")
        ]
        
        print("\nTesting API Connections (limited to avoid excessive costs):\n")
        for model_name, provider_name in models_to_test:
            try:
                print(f"Testing {provider_name} model: {model_name}")
                llm = get_llm(model_name, temperature=0.5, max_tokens=10)
                print(f"✅ Successfully loaded {model_name} model class\n")
                
                # Optional: Test a simple completion 
                # Uncomment only when necessary to validate full end-to-end functionality
                # response = llm.invoke("Say Hi")
                # print(f"Response: {response.content}\n")
                
            except Exception as e:
                print(f"❌ Failed to load {model_name}: {str(e)}\n")
    else:
        print("\nSkipping API calls to save costs. Set test_api_calls = True to test actual API connections.")

if __name__ == "__main__":
    # Load environment variables from .env
    load_dotenv()
    
    if test_environment():
        test_model_loading()
    else:
        print("\n❌ No valid API keys found. Please set up at least one model provider in your .env file.")
        print("Refer to the README.md for instructions on setting up API keys.")
