import sys
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


def test_hypothesis_2():
    """
    This function implements the fix proposed in Hypothesis #2.
    It's expected to run without error and prove the validation logic.
    """
    print("--- Testing Hypothesis #2: Use __post_init__ for validation ---")
    try:
        # Base class remains a dataclass
        @dataclass
        class Action:
            params: Dict[str, Any] = field(default_factory=dict)

        # The fix: Give `command` a default of `None` to satisfy the
        # __init__ signature, then check for it in __post_init__.
        @dataclass
        class ExecuteAction(Action):
            command: Optional[str] = None

            def __post_init__(self):
                if self.command is None:
                    raise ValueError(
                        "The 'command' argument is required for ExecuteAction"
                    )

        print("[SUCCESS] Class hierarchy defined without TypeError.")

        # Test case 1: The validation should fail when command is missing
        try:
            ExecuteAction()
            print("[FAIL] Instantiation succeeded when it should have failed.")
            return False
        except ValueError as e:
            print(
                f"[SUCCESS] Correctly raised ValueError when 'command' was missing: {e}"
            )

        # Test case 2: The instantiation should succeed when command is provided
        try:
            instance = ExecuteAction(command="ls -l")
            print(
                f"[SUCCESS] Correctly instantiated when 'command' was provided: {instance}"
            )
        except ValueError:
            print("[FAIL] Instantiation failed when it should have succeeded.")
            return False

        print("[SUCCESS] Hypothesis #2 is confirmed. The validation works as expected.")
        return True

    except Exception as e:
        print(f"[FAIL] Hypothesis #2 is refuted. An unexpected error occurred: {e}")
        return False


if __name__ == "__main__":
    if not test_hypothesis_2():
        sys.exit(1)

    print("\nConclusion: Hypothesis #2 is a valid, alternative solution.")
    sys.exit(0)
