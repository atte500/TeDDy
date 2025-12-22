# Outbound Adapter: `ConsoleInteractorAdapter`

**Status:** Planned

## 1. Purpose

The `ConsoleInteractorAdapter` is a concrete implementation of the `IUserInteractor` outbound port. Its responsibility is to handle direct interaction with the user via the standard input/output of the console. It translates the port's abstract request for user input into a specific terminal-based interaction.

## 2. Implemented Ports

*   **Implements:** [`IUserInteractor`](../../core/ports/outbound/user_interactor.md)

## 3. Implementation Notes

The core of this adapter is the logic to read multi-line input from `sys.stdin`. A technical spike was performed to verify the most robust and idiomatic Python pattern for this task.

*   **Spike:** `spikes/technical/10-multiline-input/` (now deleted)
*   **Finding:** The proven approach is to read from `sys.stdin` in a `while` loop, appending lines to a buffer until a blank line (`\n`) or end-of-stream (empty string `''`) is detected.

### Key Code Snippet (from Spike)

This code forms the basis of the `ask_question` method implementation.

```python
import sys

def ask_question(prompt: str) -> str:
    """
    Displays a prompt and reads multi-line input from stdin
    until the user enters a blank line.
    """
    print(prompt)
    lines = []
    while True:
        try:
            line = sys.stdin.readline()
            # An interactive newline is '\n', a piped end-of-file is ''
            if line == '\n' or line == '':
                break
            lines.append(line.rstrip('\n'))
        except KeyboardInterrupt:
            # Allow Ctrl+C to exit gracefully.
            break
    return "\n".join(lines)
```

## 4. External Documentation

*   [Python `sys.stdin` documentation](https://docs.python.org/3/library/sys.html#sys.stdin)
