import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Sequence
from teddy_executor.core.domain.models.plan import ActionType
from teddy_executor.prompts import find_prompt_content

def create_session_prefixed(service, name: str, agent_name: str) -> str:
    """Showcase version of create_session with date prefix."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefixed_name = f"{timestamp}-{name}"
    session_root = f".teddy/sessions/{prefixed_name}"
    turn_dir = f"{session_root}/01"

    service._file_system_manager.create_directory(turn_dir)

    # Re-use existing seeding logic from the service instance
    init_context = service._file_system_manager.read_file(".teddy/init.context")
    clean_context = "\n".join([l for l in init_context.splitlines() if l.strip() and not l.strip().startswith("#")])
    service._file_system_manager.write_file(f"{session_root}/session.context", clean_context)

    prompt_content = find_prompt_content(agent_name)
    service._file_system_manager.write_file(f"{turn_dir}/{agent_name}.xml", prompt_content)

    meta_data = {
        "turn_id": "01",
        "agent_name": agent_name,
        "cumulative_cost": 0.0,
        "turn_cost": 0.0,
        "creation_timestamp": datetime.now().isoformat(),
    }
    service._write_meta(f"{turn_dir}/meta.yaml", meta_data)

    return session_root

def generate_plan_sequenced(planning_service, interactor, message, turn_dir, context_files, agent_name):
    """Showcase version of plan display with prefix stripping and log sequencing."""
    import os
    turn_p = Path(turn_dir)
    session_folder = turn_p.parent.name
    
    # Strip prefix for display
    display_name = re.sub(r"^\d{8}_\d{6}-", "", session_folder)
    
    # Sequence: Resolve message first (this simulates the prompt)
    resolved_message = message
    if not resolved_message and interactor:
        resolved_message = interactor.ask_question("What would you like the AI to do?")

    # Display progress AFTER resolution
    # UX Update: Remove 'Session:' prefix, use natural language, brighter telemetry
    msg = f"[cyan][{turn_p.name}] {display_name} | Waiting for {agent_name} to respond...[/cyan]"
    interactor.display_message(msg)
    
    # Mock LLM if requested
    if os.getenv("TEDDY_SHOWCASE_MOCK_LLM") == "1":
        # Simulate small delay
        import time
        time.sleep(0.3)
        
        # Write valid protocol plan.md
        plan_content = """# Plan: Showcase Mock
- **Agent:** pathfinder
- **Status:** SUCCESS

## Rationale
~~~~~~
This is a mock plan for showcase purposes.
~~~~~~

## Action Plan
### `EXECUTE`
- **Description:** A safe mock action.
~~~~~~shell
echo "Showcase success"
~~~~~~
"""
        plan_path = turn_p / "plan.md"
        planning_service._file_system_manager.write_file(str(plan_path), plan_content)
        
        # Update meta.yaml with mock telemetry
        meta_path = turn_p / "meta.yaml"
        meta = {
            "turn_id": turn_p.name,
            "agent_name": agent_name,
            "model": "showcase-mock",
            "token_count": 1200,
            "turn_cost": 0.001
        }
        import yaml
        planning_service._file_system_manager.write_file(str(meta_path), yaml.dump(meta))
        
        return str(plan_path), 0.001

    return planning_service.generate_plan(
        user_message=resolved_message,
        turn_dir=turn_dir,
        context_files=context_files
    )

def simulate_isolation_logic(actions):
    """Showcase version of ExecutionOrchestrator isolation reporting."""
    is_multi = len(actions) > 1
    logs = []
    for action in actions:
        if is_multi and action["type"] in ["PROMPT", "INVOKE", "RETURN"]:
            logs.append({
                "type": action["type"],
                "status": "SKIPPED",
                "reason": "Automatically skipped: This action must be performed in isolation."
            })
        else:
            logs.append({
                "type": action["type"],
                "status": "SUCCESS",
                "reason": "Action executed successfully."
            })
    return logs

def simulate_empty_input_logic(user_input):
    """Showcase version of PlanningService empty input handling."""
    if not user_input or not user_input.strip():
        return "[yellow]Empty input detected. Proceeding with current context as instruction...[/yellow]"
    return f"Proceeding with instruction: {user_input}"