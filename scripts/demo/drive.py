#!/usr/bin/env python3
"""Interactive driver for the TeDDy showcase GIF recording.

Uses pexpect to drive the session in a real PTY with full UTF-8 support,
ensuring emoji (🟢) are preserved without mojibake, typing out the initial command,
and synchronizing with Textual's TUI plan reviewer.
"""

import os
import random
import sys
import time
import pexpect


def type_human(stream, text: str, base_delay: float = 0.035) -> None:
    """Type characters with natural human cadence, variance, and micro-pauses."""
    for char in text:
        stream.write(char)
        stream.flush()
        # Occasional micro-pause on punctuation / spaces
        if char in " .,:;!?'\"":
            time.sleep(base_delay + random.uniform(0.04, 0.09))
        else:
            time.sleep(base_delay + random.uniform(-0.012, 0.022))


def type_command(command: str) -> None:
    """Simulate a human typing the command at the terminal prompt."""
    prompt = "\033[1;32m$\033[0m "
    sys.stdout.write(prompt)
    sys.stdout.flush()
    time.sleep(0.6)
    type_human(sys.stdout, command, base_delay=0.038)
    time.sleep(0.4)
    sys.stdout.write("\r\n")
    sys.stdout.flush()


def main() -> None:
    work_dir = os.environ.get("WORK_DIR")
    repo_root = os.environ.get("REPO_ROOT")

    if not work_dir or not repo_root:
        sys.stderr.write("WORK_DIR and REPO_ROOT must be set\n")
        sys.exit(1)

    initial_cmd = "teddy start -a developer -m 'Build a greeting helper'"
    type_command(initial_cmd)

    os.chdir(work_dir)

    spawn_cmd = f"uv run --project '{repo_root}' teddy start -a developer -m 'Build a greeting helper'"
    env = dict(os.environ)
    env["TERM"] = "xterm-256color"
    env["LANG"] = "en_US.UTF-8"
    env["LC_ALL"] = "en_US.UTF-8"
    env["PYTHONUTF8"] = "1"
    env["PROMPT_TOOLKIT_NO_CPR"] = "1"

    env.pop("VIRTUAL_ENV", None)

    def sleep_and_drain(seconds: float) -> None:
        """Sleep while continuously reading from child so terminal repaints stream live."""
        deadline = time.time() + seconds
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            try:
                child.read_nonblocking(size=2048, timeout=min(remaining, 0.05))
            except (pexpect.TIMEOUT, pexpect.EOF):
                pass

    child = pexpect.spawn(
        "/bin/bash",
        ["-c", spawn_cmd],
        dimensions=(26, 150),
        env=env,
        encoding="utf-8",
        codec_errors="replace",
        timeout=60,
    )
    child.logfile_read = sys.stdout

    def send_and_step(key: str, base_delay: float = 0.35) -> None:
        """Send a navigation key and pause with slight natural variance."""
        child.send(key)
        sleep_and_drain(base_delay + random.uniform(-0.04, 0.07))

    def type_in_child(text: str, base_delay: float = 0.038) -> None:
        """Type characters into child process with human-like randomized delays."""
        for char in text:
            child.send(char)
            if char in " .,:;!?'\"":
                sleep_and_drain(base_delay + random.uniform(0.03, 0.07))
            else:
                sleep_and_drain(base_delay + random.uniform(-0.01, 0.02))

    # Turn 1: Wait for Textual entering alternate screen buffer and rendering
    child.expect(r"\x1b\[\?1049h", timeout=40)
    sleep_and_drain(1.4)  # Viewer sees initial TUI layout with Context highlighted

    # Navigate down into Rationale root
    send_and_step("\x1b[B", 0.6)  # Viewer sees full Rationale rendered in right pane

    # Step through Rationale sections briskly
    send_and_step("\x1b[B", 0.35)  # Synthesis
    send_and_step("\x1b[B", 0.35)  # Justification
    send_and_step("\x1b[B", 0.35)  # Expectation
    send_and_step("\x1b[B", 0.4)  # State Dashboard

    # Navigate down to Action Plan root
    send_and_step("\x1b[B", 0.3)

    # Navigate down to first action: [✓] CREATE: Create the greeting module.
    child.send("\x1b[B")
    sleep_and_drain(1.0)  # Viewer sees source code preview in right pane

    # 1. Open first CREATE action in nvim editor ('e')
    child.send("e")
    sleep_and_drain(1.2)  # Wait for nvim to take over screen

    # In nvim: move to line 1, open line below with 'o'
    # Nvim auto-indents 4 spaces in Python files, so type docstring directly without extra spaces!
    child.send("o")
    sleep_and_drain(0.3)
    type_in_child('"""Return a personalized greeting message."""', 0.032)
    sleep_and_drain(0.7)
    child.send("\x1b")  # Return to normal mode
    sleep_and_drain(0.4)
    type_in_child(":wq\r", 0.04)  # Save and exit nvim

    # Wait for Textual to resume
    sleep_and_drain(1.2)  # Viewer sees updated action details (*modified) in TUI

    # Add message using 'm' about the edit done and why
    child.send("m")
    sleep_and_drain(1.2)  # Wait for nvim message buffer to open

    # Type the explanation above the instruction marker
    child.send("ggO")  # Open line above marker at top
    sleep_and_drain(0.3)
    type_in_child("Added docstring to greet function for clarity.", 0.032)
    sleep_and_drain(0.7)
    child.send("\x1b")  # Return to normal mode
    sleep_and_drain(0.4)
    type_in_child(":wq\r", 0.04)  # Save and exit nvim

    # Wait for Textual to resume
    sleep_and_drain(1.0)

    # Navigate down to second action: [✓] CREATE: Create the test for the greeting helper.
    send_and_step("\x1b[B", 0.6)  # Keeps test creation selected

    # Navigate down to third action: [✓] EXECUTE: Run test suite to verify initial setup.
    send_and_step("\x1b[B", 0.6)

    # Tab navigation to right panel to inspect parameters
    child.send("\t")
    sleep_and_drain(0.6)

    # Move down in right panel
    send_and_step("\x1b[B", 0.4)
    send_and_step("\x1b[B", 0.4)

    # Tab back to left tree
    child.send("\t")
    sleep_and_drain(0.5)

    # Deselect the third EXECUTE action with Space [ ]
    child.send(" ")
    sleep_and_drain(1.2)  # Viewer clearly sees third action deselected [ ]

    # Submit plan
    child.send("s")

    # Turn 2: Wait for Textual entering alternate screen buffer for turn 2
    child.expect(r"\x1b\[\?1049h", timeout=40)
    sleep_and_drain(1.2)  # Viewer sees Turn 2 plan overview

    # Use alt+down (\x1b[1;3B) to jump sections quickly to Action Plan
    send_and_step("\x1b[1;3B", 0.5)  # Jump to Rationale
    send_and_step("\x1b[1;3B", 0.5)  # Jump to Action Plan root

    # Step down to EDIT action -> Right pane displays diff preview
    child.send("\x1b[B")
    sleep_and_drain(2.0)  # Viewer sees diff in right pane

    # Submit Turn 2
    child.send("s")

    # Turn 3: Conclusion message (summary message output on console)
    child.expect("--- MESSAGE from TeDDy ---", timeout=40)
    child.expect(r"Response \(type 'e' for editor\)", timeout=30)
    sleep_and_drain(1.5)

    # Reply to message with "ok thanks!"
    type_in_child("ok thanks!", 0.045)
    sleep_and_drain(0.6)
    child.send("\r")
    sleep_and_drain(2.5)  # Hold on screen so viewers see the submitted reply

    # Clean termination right after reply confirmation so no turn 4 occurs
    try:
        child.terminate(force=True)
    except Exception:
        pass


if __name__ == "__main__":
    main()
