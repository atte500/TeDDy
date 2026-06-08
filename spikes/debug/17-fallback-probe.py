"""
Probe: What model actually serves requests when an invalid name is given?
Goal: Send a minimal "Hello" completion with an invalid model name and
inspect the response to see what model OpenRouter actually used.
"""
import sys
import json
from pathlib import Path

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from teddy_executor.container import get_container
from teddy_executor.core.ports.outbound.llm_client import ILlmClient


def probe_fallback():
    container = get_container()
    llm_client = container.resolve(ILlmClient)

    invalid_model = "openrouter/deepseek/deepseek-v4-proh:nitro"
    messages = [{"role": "user", "content": "Say exactly 'Hello from fallback probe'"}]

    print(f"=== Probing fallback model for: {invalid_model} ===")
    print(f"Context window (should be 0): {llm_client.get_context_window(model=invalid_model)}")
    print(f"Pricing supported (should be False): {llm_client.supports_pricing(model=invalid_model)}")

    try:
        response = llm_client.get_completion(messages=messages, model=invalid_model)
        print(f"\nResponse model (what actually served): {response.model}")
        print(f"Response ID: {response.id}")
        print(f"Response content: {response.choices[0].message.content}")
        
        # Check for hidden params (provider info)
        if hasattr(response, '_hidden_params'):
            print(f"Hidden params: {json.dumps(response._hidden_params, default=str, indent=2)}")
        
        # Check cost
        cost = llm_client.get_completion_cost(response, model_override=invalid_model)
        print(f"Computed cost: ${cost:.6f}" if cost else "Computed cost: $0.0 (unknown)")
        
    except Exception as e:
        print(f"\nError during completion: {e}")
        # If it fails, try with a fallback model to confirm difference
        print("\n--- Retrying with valid model for comparison ---")
        try:
            response_valid = llm_client.get_completion(
                messages=messages, model="openrouter/openai/gpt-4o"
            )
            print(f"Response model (valid): {response_valid.model}")
        except Exception as e2:
            print(f"Error with valid model too: {e2}")

if __name__ == "__main__":
    probe_fallback()