import time
import re
from rich.console import Console
from rich.panel import Panel

console = Console()

def strip_prefix(name):
    """Strips YYYYMMDD_HHMMSS- prefix if present."""
    match = re.match(r"^\d{8}_\d{6}-(.+)$", name)
    return match.group(1) if match else name

def simulate_start(session_name):
    timestamp = "20260417_120000"
    folder_name = f"{timestamp}-{session_name}"
    console.print(f"Session started: [bold white].teddy/sessions/{folder_name}[/bold white]")
    return folder_name

def simulate_planning_turn(folder_name, turn_id, agent):
    # 1. THE PROMPT (Sequence: Input first)
    # Refinement: Only show on Turn 1. Wording updated. Editor hint added.
    if turn_id == "01":
        console.print("\n[bold white]Initial instructions for the session (type 'e' for editor)[/bold white]")
        # PROD NOTE: Capturing user input occurs here; no simulation-only echo in production.
    
    # 2. THE PROGRESS (Natural language, cyan, no 'Session:' prefix)
    display_name = strip_prefix(folder_name)
    console.print(f"[cyan][{turn_id}] {display_name} | Waiting for {agent} to respond...[/cyan]")
    
    # Simulate thinking
    time.sleep(0.6)
    
    # 3. THE TELEMETRY (Brightened labels + Bullets)
    # Refinement: Removed leading whitespace before bullets
    console.print(f"[bright_black]• Model: gpt-4o[/bright_black]")
    console.print(f"[bright_black]• Context: 12.4k tokens[/bright_black]")
    console.print(f"[bright_black]• Session Cost: $0.0341[/bright_black]\n")

# Run the simulation
console.rule("[bold magenta]TeDDy Session UX Showcase")

# Step 1: Start
session_name = "my-new-feature"
folder = simulate_start(session_name)

# Step 2: Turn 1
simulate_planning_turn(folder, "01", "pathfinder")

# Step 3: Turn 2 (to show continuity)
simulate_planning_turn(folder, "02", "developer")

console.rule("[bold magenta]End of Showcase")