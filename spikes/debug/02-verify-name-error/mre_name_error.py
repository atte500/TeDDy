from types import SimpleNamespace
from unittest.mock import MagicMock


# Minimal representation of the Action and ActionResult object concepts
class Action:
    pass


class ActionResult:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        return f"ActionResult({self.__dict__})"


# Minimal representation of the FileSystemManager
class FileSystemManager:
    def create_file(self, path: str, content: str):
        pass


# Simplified version of the PlanService._handle_create_file method
def _handle_create_file(
    action: Action, file_system_manager: FileSystemManager
) -> ActionResult:
    """
    This function mimics the real _handle_create_file method in PlanService.
    It contains the bug where it references the local variable `file_path`
    in the return statement instead of `action.file_path`.
    """
    try:
        print("Attempting to call file_system_manager.create_file...")
        file_system_manager.create_file(path=action.file_path, content=action.content)
        print("Call successful. Now attempting to create the ActionResult...")

        # This line contains the bug. It should be `action.file_path`.
        return ActionResult(
            action=action,
            status="COMPLETED",
            output=f"Created file: {file_path}",  # noqa: F821
        )
    except FileExistsError as e:
        error_message = f"{e.strerror}: '{e.filename}'"
        return ActionResult(action=action, status="FAILURE", error=error_message)


def main():
    """
    This function sets up the test case that causes the failure.
    """
    print("--- Replicating the bug from plan_service.py ---")

    # 1. This is a correctly structured action object, as the refactored
    #    code would expect.
    correctly_structured_action = SimpleNamespace(
        action_type="create_file", file_path="foo/bar.txt", content="Hello World"
    )

    mock_file_system_manager = MagicMock(spec=FileSystemManager)

    # 2. This call is expected to fail with a NameError.
    try:
        _handle_create_file(correctly_structured_action, mock_file_system_manager)
    except NameError as e:
        print("\nSUCCESS: Successfully replicated the failure.")
        print(f"Error caught: {e}")
        # Exit with a special code to signal successful replication of the error
        exit(222)

    print("\nFAILURE: Did not replicate the error. The code ran without a NameError.")
    exit(1)


if __name__ == "__main__":
    main()
