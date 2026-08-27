#!/usr/bin/env python3
"""PTY-based E2E reproduction: OSC escape sequence leak.

Spawns `python -m teddy_executor start` in a real pseudoterminal, injects
OSC sequences during editor runtime (simulating real terminal emulator
behavior), and checks if the session name contains leaked sequences.

This exercises the real ConsoleAskLoop with a real prompt_toolkit prompt
reading from a real TTY, bridging the gap between mock assertions and
real terminal behavior.

Uses only stdlib (pty, os, select, signal) — zero external dependencies.
"""

import os
import pty
import select
import signal
import sys
import time

OSC_SEQ = b"\x1b]11;rgb:1f1f/2323/3535\x1b\\"


def read_avail(fd, timeout=2.0):
    data = b""
    deadline = time.time() + timeout
    quiet = time.time() + 0.3
    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], 0.1)
        if r:
            try:
                chunk = os.read(fd, 4096)
                if not chunk:
                    break
                data += chunk
                quiet = time.time() + 0.3
            except OSError:
                break
        elif data and time.time() > quiet:
            break
    return data


def wait_for(fd, substring, timeout=15):
    data = b""
    deadline = time.time() + timeout
    while time.time() < deadline:
        data += read_avail(fd, timeout=0.5)
        if substring in data.decode("utf-8", errors="replace"):
            return data.decode("utf-8", errors="replace")
    return data.decode("utf-8", errors="replace")


def write(fd, data):
    os.write(fd, data)
    time.sleep(0.3)


def main():
    print("=" * 60)
    print("PTY E2E: OSC Leak Test")
    print("OSC:", OSC_SEQ)
    print("=" * 60)

    m, s = pty.openpty()
    pid = os.fork()

    if pid == 0:
        os.close(m)
        os.setsid()
        for fd in (0, 1, 2):
            os.dup2(s, fd)
        if s > 2:
            os.close(s)
        os.execvp("python", ["python", "-m", "teddy_executor", "start"])
        os._exit(1)

    os.close(s)

    try:
        print("\n[1] Waiting for prompt...")
        out = wait_for(m, "Response", timeout=15)
        print(f"[1] Prompt seen ({len(out)} chars)")

        print("\n[2] Sending 'e'...")
        write(m, b"e\n")
        time.sleep(0.5)
        out = read_avail(m, timeout=2).decode("utf-8", errors="replace")
        print(f"[2] Post-e: {out[-200:]}")

        print(f"\n[3] Injecting OSC: {OSC_SEQ!r}")
        write(m, OSC_SEQ)
        time.sleep(0.3)

        print("\n[4] Pressing Enter...")
        write(m, b"\n")
        out = read_avail(m, timeout=5).decode("utf-8", errors="replace")
        print(f"[4] Output:\n{out[-500:]}")

        print("\n" + "=" * 60)
        print("RESULT")
        print("=" * 60)
        has_leak = "rgb" in out and ("1f1f" in out or "2323" in out or "3535" in out)
        if has_leak:
            print("[FAIL] LEAK DETECTED!")
            for line in out.split("\n"):
                if "rgb" in line:
                    print(f"  -> {line.strip()}")
        else:
            print("[PASS] No leak detected")

        for line in out.split("\n"):
            if "[" in line and "|" in line and "Waiting" not in line:
                print(f"Session: {line.strip()}")

    finally:
        try:
            os.kill(pid, signal.SIGTERM)
            os.waitpid(pid, 0)
        except (OSError, ChildProcessError):
            pass
        os.close(m)

    return 1 if has_leak else 0


if __name__ == "__main__":
    sys.exit(main())