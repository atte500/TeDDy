import sys
from dataclasses import dataclass, field
from typing import Dict, Any


def replicate_error():
    """
    This function attempts to define the problematic class structure.
    It's expected to raise a TypeError at class definition time.
    """
    print("--- Attempting to replicate the error ---")
    try:

        @dataclass
        class Action:
            params: Dict[str, Any] = field(default_factory=dict)

        @dataclass
        class ExecuteAction(Action):
            command: str

        # The error occurs at definition, but we'll try to instantiate to be sure.
        _ = ExecuteAction(command="echo 'fail'")
        print("[FAIL] The TypeError was NOT replicated.")
        return False
    except TypeError as e:
        print(f"[SUCCESS] Replicated expected error: {e}")
        return True


def test_hypothesis_1():
    """
    This function implements the fix proposed in Hypothesis #1.
    It's expected to run without error.
    """
    print("\n--- Testing Hypothesis #1: Make base class a non-dataclass ---")
    try:
        # The fix: Action is just a plain object, not a dataclass.
        class Action:
            pass

        @dataclass
        class ExecuteAction(Action):
            command: str
            params: Dict[str, Any] = field(default_factory=dict)
            action: str = "execute"

        # For completeness, define the other action class as well
        @dataclass
        class CreateFileAction(Action):
            path: str
            content: str = ""
            params: Dict[str, Any] = field(default_factory=dict)
            action: str = "create_file"

        # Now, try to instantiate them
        exec_action = ExecuteAction(command="ls -l")
        create_action = CreateFileAction(path="/tmp/file.txt", content="hello")

        print(f"ExecuteAction instance: {exec_action}")
        print(f"CreateFileAction instance: {create_action}")
        print(
            "[SUCCESS] Hypothesis #1 is confirmed. The classes can be defined and instantiated."
        )
        return True
    except Exception as e:
        print(f"[FAIL] Hypothesis #1 is refuted. An unexpected error occurred: {e}")
        return False


if __name__ == "__main__":
    if not replicate_error():
        sys.exit(1)

    if not test_hypothesis_1():
        sys.exit(1)

    print("\nConclusion: Hypothesis #1 is a valid solution.")
    sys.exit(0)
