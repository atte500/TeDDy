# Outbound Adapter: Console Interactor

**Status:** Implemented

## 1. Purpose

The `ConsoleInteractorAdapter` is a concrete implementation of the `IUserInteractor` outbound port. Its responsibility is to handle direct interaction with the user via the standard input/output of the console. It translates the port's abstract request for user input into a specific terminal-based interaction.

## 2. Implemented Ports

*   **Implements:** [`UserInteractor`](../../core/ports/outbound/user_interactor.md)

## 3. Implementation Notes

The core of this adapter is the logic to read multi-line input from `sys.stdin`. A technical spike was performed to verify the most robust and idiomatic Python pattern for this task.

*   **Spike:** `spikes/technical/10-multiline-input/` (now deleted)
*   **Finding:** The proven approach is to read from `sys.stdin` in a `while` loop, appending lines to a buffer until a blank line (`\n`) or end-of-stream (empty string `''`) is detected.

### Implementation Details

The `ask_question` method logic is as follows:
1.  **Print Prompt to Stderr:** The prompt is printed to `sys.stderr` to avoid polluting `stdout`, which is reserved for the final machine-readable report.
2.  **Read Input Loop:** The adapter reads lines from standard input using `input()` until an `EOFError` is caught or the user enters an empty line. This robustly handles both interactive sessions and piped input.
3.  **Return Value:** The collected lines are joined into a single string.

```python
# Conceptual Implementation
import sys
from teddy.core.ports.outbound.user_interactor import UserInteractor

class ConsoleInteractorAdapter(UserInteractor):
    def ask_question(self, prompt: str) -> str:
        print(prompt, file=sys.stderr, flush=True)
        lines = []
        while True:
            try:
                line = input()
                if line == "":
                    break
                lines.append(line)
            except EOFError:
                break
        return "\n".join(lines)
```

## 4. External Documentation

*   [Python `sys.stdin` documentation](https://docs.python.org/3/library/sys.html#sys.stdin)
