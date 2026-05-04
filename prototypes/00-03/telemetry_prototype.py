import litellm
import sys

def get_context_window(model: str) -> int:
    """Simulates the logic intended for LiteLLMAdapter."""
    try:
        cost_info = litellm.model_cost.get(model, {})
        # Use max_input_tokens for context window, fall back to max_tokens (output) or 0
        return cost_info.get("max_input_tokens") or cost_info.get("max_tokens") or 0
    except Exception:
        return 0

def display_telemetry(model: str, used_tokens: int, cumulative_cost: float):
    """Simulates the formatting logic intended for PlanningService."""
    total_tokens = get_context_window(model)
    
    # Simulate the "Waiting for" message
    print(f"[02] MySession | Waiting for pathfinder to respond...")
    
    # Telemetry block (using rich-style tags for simulation)
    print(f"• Model: {model}")
    
    # Format tokens: e.g., 1.2k / 128.0k
    used_fmt = f"{used_tokens / 1000:.1f}k"
    total_fmt = f"{total_tokens / 1000:.1f}k"
    print(f"• Context: {used_fmt} / {total_fmt} tokens")
    
    print(f"• Session Cost: ${cumulative_cost:.4f}")

if __name__ == "__main__":
    # Test cases
    print("--- Scenario: GPT-4o ---")
    display_telemetry("gpt-4o", 1200, 0.0500)
    
    print("\n--- Scenario: Unknown Model ---")
    display_telemetry("unknown-model", 500, 0.0100)