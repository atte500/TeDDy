import os
import sys
from unittest.mock import MagicMock, patch
import litellm

# Ensure the src directory is in the path
sys.path.append(os.path.abspath("src"))

from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter
from teddy_executor.adapters.outbound.openrouter_hydrator import OpenRouterMetadataHydrator

def showcase_openrouter_resilience():
    print("--- SHOWCASE: Resilient OpenRouter Metadata Hydration ---")
    
    # 1. Setup
    # Call with versioned name, catalog has generic name
    model_name = "openrouter/deepseek/deepseek-v4-flash-20260423"
    catalog_id = "deepseek/deepseek-v4-flash"
    
    # Mocking the OpenRouter API response for the hydrator
    mock_catalog = {
        "data": [
            {
                "id": catalog_id,
                "context_length": 1048576,
                "pricing": {"prompt": "0.000001", "completion": "0.000002"}
            }
        ]
    }
    
    hydrator = OpenRouterMetadataHydrator()
    mock_config = MagicMock()
    mock_config.get.return_value = None # No special config needed for mock run
    
    # 2. Programmatic Assertion of Logic
    print(f"\n[1] Testing Hydration Logic for {model_name}...")
    
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_catalog
        
        adapter = LiteLLMAdapter(config_service=mock_config, hydrator=hydrator)
        
        # Simulate LiteLLM NotFoundError on first call, success on second
        # We need to mock litellm.completion
        with patch("litellm.completion") as mock_completion:
            # First call raises NotFoundError, second succeeds
            mock_response = MagicMock()
            # Explicitly set the return value for the content attribute to avoid Mock ID printing
            type(mock_response).content = "Hello from DeepSeek V4"
            mock_response.choices = [MagicMock(message=MagicMock(content="Hello from DeepSeek V4"))]
            mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
            
            mock_completion.side_effect = [
                litellm.NotFoundError(
                    message="model not found", 
                    model=model_name, 
                    llm_provider="openrouter"
                ),
                mock_response
            ]
            
            print(f"Triggering completion for {model_name} (simulating initial LiteLLM miss)...")
            response = adapter.get_completion(
                model=model_name,
                messages=[{"role": "user", "content": "Hi"}],
                stream=False
            )
            
            # LiteLLM responses are usually accessed via choices, but some adapters add .content
            print(f"Success! Response: {getattr(response, 'content', 'No content')}")
            
            # Verify litellm.model_cost was updated
            assert model_name in litellm.model_cost, f"Metadata for {model_name} not found in litellm.model_cost"
            metadata = litellm.model_cost[model_name]
            print(f"Verified metadata injection for {model_name}:")
            print(f"  Context Window: {metadata['max_input_tokens']}")
            print(f"  Price/1k Prompt: ${metadata['input_cost_per_token'] * 1000}")
            
    # 3. Smoke Test UI Telemetry Display
    print("\n[2] Smoke Testing Telemetry Display...")
    # Mock context window as 0 (unknown) first
    print("Testing '???' display for unknown models:")
    from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import populate_context_detail
    
    # Simulate App and Pane
    mock_app = MagicMock()
    mock_app.project_context = MagicMock()
    mock_app.project_context.total_window = 0
    mock_app.project_context.items = []
    mock_app.project_context.system_prompt_tokens = 0
    
    mock_pane = MagicMock()
    
    # Patch DetailItem to inspect constructor arguments
    with patch("teddy_executor.adapters.inbound.textual_plan_reviewer_widgets.DetailItem") as mock_detail_item_cls:
        # Call with (app, pane, data=None) to trigger aggregate view
        populate_context_detail(mock_app, mock_pane, None)
        
        # Verify '???' was passed to the DetailItem constructor
        found_sentinel = False
        for call in mock_detail_item_cls.call_args_list:
            # DetailItem(label, value)
            if len(call.args) > 1 and "???" in str(call.args[1]):
                found_sentinel = True
                break
                
        assert found_sentinel, "Telemetry did not display ??? for unknown window"
    print("  Telemetery correctly shows '???' for unknown context window.")

    print("\n--- SHOWCASE COMPLETE ---")
    print("Continuous Trace: LiteLLM Error -> Hydrator Fetch -> Regex Match -> Registry Injection -> Retry Success")

if __name__ == "__main__":
    try:
        showcase_openrouter_resilience()
    except Exception as e:
        print(f"\nSHOWCASE FAILED: {e}")
        sys.exit(1)