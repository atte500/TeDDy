from types import SimpleNamespace
from unittest.mock import MagicMock


# Minimal representation of the Action object concept
class Action:
    pass


# Minimal representation of the ShellExecutor
class ShellExecutor:
    def run(self, command: str):
        pass


# Simplified version of the PlanService._handle_execute method
def _handle_execute(action: Action, shell_executor: ShellExecutor) -> None:
    """
    This function mimics the real _handle_execute method in PlanService.
    It expects 'action' to have a direct 'command' attribute.
    """
    print("Attempting to access action.command...")
    command_result = shell_executor.run(action.command)  # noqa: F841
    print("Successfully accessed action.command.")


def main():
    """
    This function sets up the test case that causes the failure.
    """
    print("--- Replicating the bug from test_plan_service.py ---")

    # 1. This is how the mock action is currently created in the unit tests.
    #    It has a 'params' dictionary instead of a top-level 'command' attribute.
    incorrectly_mocked_action = SimpleNamespace(
        action_type="execute", params={"command": 'echo "hello world"'}
    )

    mock_shell_executor = MagicMock(spec=ShellExecutor)

    # 2. This call is expected to fail with an AttributeError.
    try:
        _handle_execute(incorrectly_mocked_action, mock_shell_executor)
    except AttributeError as e:
        print("\nSUCCESS: Successfully replicated the failure.")
        print(f"Error caught: {e}")
        # Exit with a special code to signal successful replication of the error
        exit(111)

    print(
        "\nFAILURE: Did not replicate the error. The code ran without an AttributeError."
    )
    exit(1)


if __name__ == "__main__":
    main()
