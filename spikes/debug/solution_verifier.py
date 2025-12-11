"""
This script verifies the solutions for the two identified bugs:
1. The NameError in PlanService._handle_create_file.
2. The AttributeError caused by misconfigured mocks in test_plan_service.py.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock
import sys


# --- Common Mocks & Stubs ---
class Action:
    pass


class ActionResult:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.output = kwargs.get("output")

    def __repr__(self):
        return f"ActionResult({self.__dict__})"


class ShellExecutor:
    def run(self, command: str):
        pass


class FileSystemManager:
    def create_file(self, path: str, content: str):
        pass


class CommandResult:
    def __init__(self, stdout, stderr, return_code):
        self.stdout = stdout
        self.stderr = stderr
        self.return_code = return_code


# --- Verification for Bug #1: NameError in PlanService ---


def _handle_create_file_fixed(
    action: Action, file_system_manager: FileSystemManager
) -> ActionResult:
    """
    This is the corrected version of the PlanService method.
    The bug in `output=f"Created file: {file_path}"` is fixed.
    """
    file_system_manager.create_file(path=action.file_path, content=action.content)
    # CORRECT: Uses action.file_path
    return ActionResult(
        action=action,
        status="COMPLETED",
        output=f"Created file: {action.file_path}",
    )


def verify_plan_service_fix():
    print("--- Verifying Fix for NameError in _handle_create_file ---")
    action = SimpleNamespace(file_path="foo/bar.txt", content="test")
    mock_fsm = MagicMock(spec=FileSystemManager)

    try:
        result = _handle_create_file_fixed(action, mock_fsm)
        assert result.output == "Created file: foo/bar.txt"
        print(
            "✅ SUCCESS: Corrected method runs without NameError and produces the correct output."
        )
        return True
    except Exception as e:
        print(f"❌ FAILURE: Corrected method failed with an unexpected error: {e}")
        return False


# --- Verification for Bug #2: AttributeError in Unit Tests ---


def _handle_execute_original(
    action: Action, shell_executor: ShellExecutor
) -> ActionResult:
    """This is the original, correct method from PlanService."""
    command_result = shell_executor.run(action.command)
    status = "SUCCESS" if command_result.return_code == 0 else "FAILURE"
    return ActionResult(action=action, status=status, output=command_result.stdout)


def verify_test_mock_fix():
    print("\n--- Verifying Fix for Mock Configuration in Unit Tests ---")
    mock_shell_executor = MagicMock(spec=ShellExecutor)
    mock_shell_executor.run.return_value = CommandResult("ok", "", 0)

    # This is how the mock action SHOULD be created in the tests.
    # It has a direct '.command' attribute, not a '.params' dict.
    correctly_mocked_action = SimpleNamespace(
        action_type="execute", command='echo "hello"'
    )

    try:
        result = _handle_execute_original(correctly_mocked_action, mock_shell_executor)
        mock_shell_executor.run.assert_called_once_with('echo "hello"')
        assert result.status == "SUCCESS"
        print(
            "✅ SUCCESS: Service method works correctly with the properly structured mock action."
        )
        return True
    except Exception as e:
        print(f"❌ FAILURE: Interaction failed with an unexpected error: {e}")
        return False


# --- Main Execution ---
if __name__ == "__main__":
    print("Running solution verifier...")

    plan_service_ok = verify_plan_service_fix()
    test_mock_ok = verify_test_mock_fix()

    if plan_service_ok and test_mock_ok:
        print("\n🎉 Both solutions verified successfully.")
        sys.exit(0)
    else:
        print("\n🔥 One or more solutions could not be verified.")
        sys.exit(1)
