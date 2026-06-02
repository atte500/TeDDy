import sys
import os
import argparse
import time
import shutil
from pathlib import Path
from dataclasses import dataclass, field, replace
from typing import List, Optional, Dict

# --- Constants ---
SANDBOX_ROOT = Path("spikes/tmp/02-03-sandbox")

# --- Simulation Domain Models (Mirroring src/ logic) ---

@dataclass(frozen=True)
class ContextItem:
    path: str
    scope: str = "Turn"
    selected: bool = True
    auto_prune_reason: Optional[str] = None
    token_count: int = 100
    git_status: str = ""

@dataclass(frozen=True)
class ProjectContext:
    items: List[ContextItem]
    system_prompt_tokens: int = 0

# --- Prototype Logic ---

class SafetyLimitPrototype:
    def __init__(self, max_turns: int = 5, max_cost: float = 5.0):
        # Guardrail State (Process Relative)
        self.max_turns = max_turns
        self.max_cost = max_cost
        self.current_turns = 0
        self.current_cost = 0.0

    def should_continue(self, interactive: bool) -> bool:
        if interactive:
            return True # No limits in interactive mode
        
        if self.current_turns >= self.max_turns:
            print(f"DEBUG: Terminating - Turn limit reached ({self.current_turns}/{self.max_turns})")
            return False
        
        if self.current_cost >= self.max_cost:
            print(f"DEBUG: Terminating - Cost limit reached (${self.current_cost:.2f}/${self.max_cost:.2f})")
            return False
            
        return True

    def perform_turn(self, cost: float = 0.10):
        self.current_turns += 1
        self.current_cost += cost

class MigrationPrototype:
    def migrate(self, session_name: str, last_turn_id: int) -> str:
        """Actually creates folders and migrates files."""
        session_path = SANDBOX_ROOT / session_name
        
        if last_turn_id < 99:
            next_turn_path = session_path / f"{last_turn_id + 1:02d}"
            next_turn_path.mkdir(parents=True, exist_ok=True)
            return str(next_turn_path.relative_to(SANDBOX_ROOT))
        
        # Migration logic
        print(f"DEBUG: Turn limit 99 reached. Migrating session '{session_name}'")
        
        # Determine suffix
        import re
        suffix_match = re.search(r"-(\d+)$", session_name)
        if suffix_match:
            current_count = int(suffix_match.group(1))
            base_name = session_name[:suffix_match.start()]
            new_session_name = f"{base_name}-{current_count + 1}"
        else:
            new_session_name = f"{session_name}-2"
            
        new_session_path = SANDBOX_ROOT / new_session_name
        new_turn_path = new_session_path / "01"
        
        print(f"DEBUG: Creating new session directory: {new_session_path}")
        new_turn_path.mkdir(parents=True, exist_ok=True)
        
        # Clone Core Artifacts
        print(f"DEBUG: Cloning session.context and system_prompt.xml to {new_session_name}")
        shutil.copy(session_path / "session.context", new_session_path / "session.context")
        shutil.copy(session_path / "system_prompt.xml", new_session_path / "system_prompt.xml")
        
        # Transition Turn Context
        print(f"DEBUG: Transitioning Turn 99/turn.context to {new_session_name}/01/turn.context")
        shutil.copy(session_path / "99" / "turn.context", new_turn_path / "turn.context")
        
        return str(new_turn_path.relative_to(SANDBOX_ROOT))

    def initialize_session(self, name: str):
        """Prepares a session for simulation."""
        path = SANDBOX_ROOT / name
        path.mkdir(parents=True, exist_ok=True)
        (path / "session.context").write_text("README.md\nsrc/main.py")
        (path / "system_prompt.xml").write_text("<prompt>Be helpful</prompt>")
        
        turn_path = path / "99"
        turn_path.mkdir(parents=True, exist_ok=True)
        (turn_path / "turn.context").write_text("plan.md\nreport.md")
        print(f"DEBUG: Session '{name}' initialized at Turn 99.")

class PruningPrototype:
    def prune(self, context: ProjectContext, retention_limit: int = 2) -> ProjectContext:
        """
        Simulates the improved pruning logic:
        - Spares successful Message turns (Both Plan & Report).
        - Prunes validation failures.
        """
        new_items = []
        
        # Group by Turn ID to handle plan/report pairs
        turns = {}
        for item in context.items:
            # Simple path parsing for prototype: "01/plan.md"
            turn_id = item.path.split('/')[0]
            if turn_id not in turns:
                turns[turn_id] = []
            turns[turn_id].append(item)

        max_turn_id = max([int(tid) for tid in turns.keys()] if turns else [0])
        
        for tid_str, items in turns.items():
            tid = int(tid_str)
            
            # Identify Turn Status (Simulated)
            is_message_only = any("message" in it.path.lower() for it in items)
            is_success = not any("fail" in it.path.lower() for it in items)
            is_validation_failure = any("validation" in it.path.lower() for it in items)
            
            should_spare = is_message_only and is_success and not is_validation_failure
            
            in_retention = (max_turn_id - tid) < retention_limit
            
            for item in items:
                reason = None
                selected = item.selected
                
                if not in_retention:
                    if should_spare:
                        print(f"DEBUG: Sparing {item.path} (Successful Message Turn)")
                        selected = True
                    else:
                        selected = False
                        reason = "Turn exceeds retention limit"
                
                if is_validation_failure:
                    print(f"DEBUG: Pruning {item.path} (Validation Failure)")
                    selected = False
                    reason = "Plan failed validation"
                
                new_items.append(replace(item, selected=selected, auto_prune_reason=reason))
                
        return replace(context, items=new_items)

# --- Execution ---

def run_assertions():
    if SANDBOX_ROOT.exists():
        shutil.rmtree(SANDBOX_ROOT)
    SANDBOX_ROOT.mkdir(parents=True)

    print("Running verification...")
    
    # 1. Guardrails
    guard = SafetyLimitPrototype(max_turns=3)
    assert guard.should_continue(interactive=False) == True
    guard.perform_turn()
    guard.perform_turn()
    guard.perform_turn()
    assert guard.should_continue(interactive=False) == False
    assert guard.should_continue(interactive=True) == True # Bypasses
    print("✓ Guardrails verified.")

    # 2. Migration
    migrator = MigrationPrototype()
    # Case A: Normal transition
    assert migrator.migrate("my-session", 10) == "my-session/11"
    
    # Case B: Centennial migration (99 -> 100/01)
    migrator.initialize_session("my-session")
    assert migrator.migrate("my-session", 99) == "my-session-2/01"
    
    # Case C: Incremental migration (session-2 -> session-3)
    migrator.initialize_session("my-session-2")
    assert migrator.migrate("my-session-2", 99) == "my-session-3/01"
    print("✓ Migration paths verified.")

    # 3. Pruning
    pruner = PruningPrototype()
    ctx = ProjectContext(items=[
        ContextItem("01/plan.md", selected=True),
        ContextItem("01/report.md", selected=True),
        ContextItem("02/message_plan.md", selected=True),
        ContextItem("02/message_report.md", selected=True),
        ContextItem("03/fail_validation_plan.md", selected=True),
        ContextItem("03/fail_validation_report.md", selected=True),
        ContextItem("04/plan.md", selected=True),
        ContextItem("04/report.md", selected=True),
    ])
    
    # Retention limit = 2. Max turn = 4. 
    # Turn 01 (id=1): 4-1=3 (out). Not message. -> Prune.
    # Turn 02 (id=2): 4-2=2 (out). Successful Message. -> Spare.
    # Turn 03 (id=3): 4-3=1 (in). Validation Fail. -> Prune.
    # Turn 04 (id=4): 4-4=0 (in). -> Keep.
    
    pruned = pruner.prune(ctx, retention_limit=2)
    
    results = {it.path: it.selected for it in pruned.items}
    assert results["01/plan.md"] == False
    assert results["02/message_plan.md"] == True  # SPARED
    assert results["02/message_report.md"] == True # BOTH PRESERVED
    assert results["03/fail_validation_plan.md"] == False # PRUNED (FAIL)
    assert results["04/plan.md"] == True
    
    print("✓ Pruning discrimination verified.")
    print("Verification SUCCESS.")

def run_interactive():
    if SANDBOX_ROOT.exists():
        shutil.rmtree(SANDBOX_ROOT)
    SANDBOX_ROOT.mkdir(parents=True)

    print("\n--- Safety Limits Prototype (Live Sandbox) ---")
    print(f"Sandbox Location: {SANDBOX_ROOT}")
    print("Commands: [t] Turn, [c] Add $1, [m] Migrate (T99), [l] List Files, [q] Quit")
    
    guard = SafetyLimitPrototype(max_turns=10, max_cost=5.0)
    migrator = MigrationPrototype()
    current_session = "interactive-session"
    
    # Init
    migrator.initialize_session(current_session)
    
    while True:
        cmd = input("> ").lower().strip()
        if cmd == 'q':
            break
        elif cmd == 't':
            guard.perform_turn()
            print(f"Turn {guard.current_turns}/10. Status: {'CONTINUE' if guard.should_continue(False) else 'STOP'}")
        elif cmd == 'c':
            guard.perform_turn(cost=1.0)
            print(f"Cost ${guard.current_cost:.2f}/$5.00. Status: {'CONTINUE' if guard.should_continue(False) else 'STOP'}")
        elif cmd == 'm':
            next_step = migrator.migrate(current_session, 99)
            print(f"Migration Target: {next_step}")
            # Update current session name for next potential migration
            current_session = Path(next_step).parent.name
        elif cmd == 'l':
            print("\nFilesystem State:")
            for root, dirs, files in os.walk(SANDBOX_ROOT):
                level = root.replace(str(SANDBOX_ROOT), '').count(os.sep)
                indent = ' ' * 4 * (level)
                print(f"{indent}{os.path.basename(root)}/")
                subindent = ' ' * 4 * (level + 1)
                for f in files:
                    print(f"{subindent}{f}")
        
        if not guard.should_continue(False):
            print("!!! GUARDRAIL BREACHED !!!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if args.verify:
        run_assertions()
        sys.exit(0)
    
    # 5-second smoke test check for CI/Boot
    if os.environ.get("SMOKE_TEST"):
        print("Smoke test boot successful.")
        time.sleep(1)
        sys.exit(0)

    run_interactive()