"""
This script demonstrates the correct way to handle dependencies
in a Typer application, as confirmed by the library's author.

The pattern uses a main app callback to create and attach dependencies
to the context object (`ctx.obj`), which is then available to all
subcommands.
"""
import typer
from typing import cast


# --- 1. Define your dependency (e.g., a service or use case) ---
class MyService:
    def __init__(self, name: str):
        self.name = name

    def execute(self, message: str):
        print(f"Service '{self.name}' executing with message: '{message}'")
        return f"Processed: {message}"


# --- 2. Create an instance of the service ---
# In a real app, this would be your instantiated use case.
my_plan_service = MyService(name="PlanService")

# --- 3. Create the Typer App ---
app = typer.Typer()


# --- 4. Create a Callback to manage the context ---
# This function runs before any command.
# It's the designated place to set up shared state/dependencies.
@app.callback()
def main_callback(ctx: typer.Context):
    """
    Main callback to manage application state.
    This is where we "inject" the dependency.
    """
    # Attach the service instance to the context object.
    # This makes it available to all commands.
    ctx.obj = my_plan_service
    print("Callback: Service has been attached to context.")


# --- 5. Define a command that uses the dependency ---
@app.command()
def run(
    ctx: typer.Context,
    message: str = typer.Argument("default message", help="The message to process."),
):
    """
    A command that uses the dependency from the context.
    """
    print(f"Command 'run': Received message '{message}'.")
    # Retrieve the service from the context object.
    # It's good practice to cast the type for static analysis.
    service = cast(MyService, ctx.obj)

    # Use the service
    result = service.execute(message)
    print(f"Command 'run': Got result from service: '{result}'")
    typer.echo("Command executed successfully!")


if __name__ == "__main__":
    print("--- Running Solution Verifier ---")
    # To test, run: python spikes/debug/solution_verifier.py run "Hello Typer"
    app()

# Expected output for `python solution_verifier.py run "test"`:
# --- Running Solution Verifier ---
# Callback: Service has been attached to context.
# Command 'run': Received message 'test'.
# Service 'PlanService' executing with message: 'test'
# Command 'run': Got result from service: 'Processed: test'
# Command executed successfully!
