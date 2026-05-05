import sys
import os

# Mock litellm for testing in case it's not installed in the current environment
# In production, we'll use the actual library via LiteLLMAdapter.
class MockLiteLLM:
    @staticmethod
    def token_counter(model, text):
        # Rough heuristic: ~4 chars per token
        return len(text) // 4

def get_text_token_count(text: str, model: str = "gpt-4o") -> int:
    try:
        import litellm
        return litellm.token_counter(model=model, text=text)
    except (ImportError, Exception):
        return MockLiteLLM.token_counter(model, text)

if __name__ == "__main__":
    sample_text = "This is a sample text for token counting." * 10
    count = get_text_token_count(sample_text)
    print(f"Token count for {len(sample_text)} chars: {count}")