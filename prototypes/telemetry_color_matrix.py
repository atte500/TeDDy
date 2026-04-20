from rich.console import Console

console = Console()

def render_sample(label_style: str, value_style: str, header_style: str, title: str):
    console.print(f"\n[bold magenta]--- Option: {title} ---[/bold magenta]")
    
    # Simulate Turn Header
    turn_id = "01"
    session_name = "fix-login-bug"
    agent = "pathfinder"
    console.print(f"[{header_style}][{turn_id}] {session_name} | Waiting for {agent} to respond...[/{header_style}]")
    
    # Simulate Telemetry
    # label_style: The color for the bullet and key
    # value_style: The color for the actual data
    console.print(f"[{label_style}]• Model:[/{label_style}] [{value_style}]gpt-4o[/{value_style}]")
    console.print(f"[{label_style}]• Context:[/{label_style}] [{value_style}]12.4k tokens[/{value_style}]")
    console.print(f"[{label_style}]• Session Cost:[/{label_style}] [{value_style}]$0.0341[/{value_style}]")

# Current implementation (per session_planner.py)
render_sample(label_style="dim", value_style="dim", header_style="cyan", title="Current (Dim)")

# Proposed in Slice 00-05
render_sample(label_style="bright_black", value_style="bright_black", header_style="cyan", title="Proposed (Bright Black)")

# Option: High Contrast Keys
render_sample(label_style="cyan", value_style="white", header_style="bold cyan", title="High Contrast (Cyan Keys)")

# Option: Subtle Labels, Clear Values
render_sample(label_style="bright_black", value_style="white", header_style="cyan", title="Subtle Labels / White Values")

# Option: Deep Blue (True Secondary)
render_sample(label_style="blue", value_style="blue", header_style="cyan", title="Deep Blue")

# User Proposed: Blue Keys + Magenta Values
render_sample(label_style="blue", value_style="magenta", header_style="cyan", title="User Proposed (Blue/Magenta)")

console.print("\n" + "="*50 + "\n")