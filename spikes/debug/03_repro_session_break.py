import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add project root and spikes to path
root = Path(__file__).parent.parent.parent
sys.path.append(str(root))

from spikes.debug.shadow_session_planner import ShadowSessionPlanner as SessionPlanner
from teddy_executor.core.services.prompt_manager import PromptManager

def run_repro():
    fs = MagicMock()
    ui = MagicMock()
    ui.ask_question.return_value = "MANUAL_INPUT"
    
    # 1. Test SUCCESS turn (PROMPT case)
    print("--- Testing SUCCESS turn (Prompt Case) ---")
    report_success = """
# Execution Report: Turn 01
- **Overall Status:** SUCCESS

## Action Log
### `PROMPT`
#### User Response
```text
I am fine.
```
"""
    fs.path_exists.return_value = True
    fs.read_file.return_value = report_success
    
    planner = SessionPlanner(fs, MagicMock(), ui, MagicMock())
    # SessionPlanner logic: SUCCESS -> ""
    resolved_success = planner._resolve_message_from_previous_turn(".teddy/sessions/test/02")
    print(f"Planner resolved (SUCCESS): '{resolved_success}'")
    
    pm = PromptManager(file_system_manager=fs, user_interactor=ui)
    final_success = pm.resolve_message(resolved_success, Path(".teddy/sessions/test/02"))
    print(f"Final resolved message: '{final_success}'")
    if ui.ask_question.called:
        print("RESULT: User was prompted manually on SUCCESS (Prompt Lost)!")
    else:
        print("RESULT: Loop continued automatically (but message is empty).")

    # 2. Test FAILURE turn (Extraction Case)
    print("\n--- Testing FAILURE turn (Extraction Case) ---")
    ui.reset_mock()
    # Report with correct Level 2 header
    report_failure = """
# Execution Report: Turn 01
- **Overall Status:** FAILURE

## User Request
Please fix the bug.

## Action Log
...
"""
    fs.read_file.return_value = report_failure
    resolved_fail = planner._resolve_message_from_previous_turn(".teddy/sessions/test/02")
    print(f"Planner resolved (FAILURE): '{resolved_fail}'")
    
    final_fail = pm.resolve_message(resolved_fail, Path(".teddy/sessions/test/02"))
    print(f"Final resolved failure message: '{final_fail}'")
    if ui.ask_question.called:
        print("RESULT: FAILURE triggered manual prompt (Extraction Failed)!")
    else:
        print("RESULT: Loop continued automatically with extracted message.")

    # 3. Test RESUME case (Simulate Turn 01 Failure -> Turn 02 Planning)
    print("\n--- Testing RESUME turn (Turn 01 Failure -> Turn 02 Planning) ---")
    ui.reset_mock()
    # If we are in Turn 02, the planner should look at Turn 01's report.
    resolved_resume = planner._resolve_message_from_previous_turn(".teddy/sessions/test/02")
    print(f"Planner resolved (RESUME): '{resolved_resume}'")
    
    final_resume = pm.resolve_message(resolved_resume, Path(".teddy/sessions/test/02"))
    print(f"Final resolved resume message: '{final_resume}'")
    if ui.ask_question.called:
        print("RESULT: RESUME triggered manual prompt!")
    else:
        print("RESULT: RESUME correctly resolved message from previous report.")

if __name__ == "__main__":
    run_repro()