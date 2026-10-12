#!/usr/bin/env python3
"""Interactive driver for the TeDDy showcase GIF recording.

Uses pexpect to drive the session in a real PTY with full UTF-8 support,
ensuring emoji (🟢) are preserved without mojibake, typing out the initial command,
and synchronizing with Textual's TUI plan reviewer.
"""

import os
import sys
import time
import pexpect


def type_command(command: str) -> None:
    """Simulate a human typing the command at the terminal prompt."""
    prompt = "\033[1;32m$\033[0m "
    sys.stdout.write(prompt)
    sys.stdout.flush()
    time.sleep(0.8)
    for char in command:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(0.04)
    time.sleep(0.5)
    sys.stdout.write("\r\n")
    sys.stdout.flush()


def main() -> None:
    work_dir = os.environ.get("WORK_DIR")
    repo_root = os.environ.get("REPO_ROOT")

    if not work_dir or not repo_root:
        sys.stderr.write("WORK_DIR and REPO_ROOT must be set\n")
        sys.exit(1)

    initial_cmd = "teddy start -m 'Build a greeting helper'"
    type_command(initial_cmd)

    os.chdir(work_dir)

    spawn_cmd = (
        f"uv run --project '{repo_root}' teddy start -m 'Build a greeting helper'"
    )
    env = dict(os.environ)
    env["TERM"] = "xterm-256color"
    env["LANG"] = "en_US.UTF-8"
    env["LC_ALL"] = "en_US.UTF-8"
    env["PYTHONUTF8"] = "1"

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

    # Turn 1: Wait for Textual entering alternate screen buffer and rendering
    child.expect(r"\x1b\[\?1049h", timeout=40)
    sleep_and_drain(2.0)  # Viewer sees initial TUI layout with Context highlighted

    # Navigate down into Rationale root
    child.send("\x1b[B")
    sleep_and_drain(1.6)  # Viewer sees full Rationale rendered in right pane

    # Navigate through Rationale sections
    child.send("\x1b[B")  # Synthesis
    sleep_and_drain(1.1)

    child.send("\x1b[B")  # Justification
    sleep_and_drain(1.1)

    child.send("\x1b[B")  # Expectation
    sleep_and_drain(1.1)

    child.send("\x1b[B")  # State Dashboard
    sleep_and_drain(1.0)

    # Navigate down to Action Plan root
    child.send("\x1b[B")
    sleep_and_drain(0.8)

    # Navigate down to first action: [✓] CREATE: Create the greeting module.
    child.send("\x1b[B")
    sleep_and_drain(1.8)  # Viewer sees source code preview in right pane

    # Move to right panel with Tab
    child.send("\t")
    sleep_and_drain(1.4)  # Viewer sees focus transferred to right panel

    # Move back to left panel with Tab
    child.send("\t")
    sleep_and_drain(1.2)  # Viewer sees focus return to left tree

    # Navigate down to second action: [✓] CREATE: Create the test for the greeting helper.
    child.send("\x1b[B")
    sleep_and_drain(1.8)  # Viewer sees test code preview in right pane

    # Deselect the action with Space [ ]
    child.send(" ")
    sleep_and_drain(2.0)  # Viewer clearly sees action deselected [ ]

    # Submit plan
    child.send("s")

    # Turn 2: Wait for Textual entering alternate screen buffer for turn 2
    child.expect(r"\x1b\[\?1049h", timeout=40)
    sleep_and_drain(2.0)  # Viewer sees Turn 2 plan overview

    # Navigate down to Rationale node -> Right pane displays Turn 2 rationale
    child.send("\x1b[B")
    sleep_and_drain(1.6)

    # Collapse Rationale
    child.send("\x1b[D")
    sleep_and_drain(0.8)

    # Navigate to Action Plan root
    child.send("\x1b[B")
    sleep_and_drain(0.8)

    # Navigate down to EDIT action -> Right pane displays diff preview
    child.send("\x1b[B")
    sleep_and_drain(2.6)  # Viewer sees diff in right pane

    # Submit Turn 2
    child.send("s")

    # Turn 3: Conclusion message (no reviewer, summary message output)
    child.expect("--- MESSAGE from TeDDy ---", timeout=40)
    child.expect("The session is complete", timeout=10)
    sleep_and_drain(
        5.0
    )  # Hold the final summary on screen so viewers can read the accomplishment

    # Terminate child cleanly so the recording ends on the green summary message
    # without prompting for response or triggering cursor position requests (CPR)
    try:
        child.terminate(force=True)
    except Exception:
        pass


if __name__ == "__main__":
    main()
