#!/usr/bin/env bash
#
# Remote Probe: Terminal State inside Textual Suspend Context
#
# This probe is designed to run on CI (Ubuntu) inside the debug.yml workflow.
# It uses `script -q -c` to create a pseudo-TTY, then runs a Python script
# that simulates the Textual suspend -> subprocess.run -> resume flow.
#
# The probe captures termios flags at each stage and compares them to the
# initial cooked mode state. Output is written to stdout for CI log capture.
#
# Expected result: The terminal attributes should be identical before and after
# the subprocess.run call if cooked mode is properly restored.

set -e

echo "=== REMOTE PROBE: TUI Editor Suspend/Resume ==="
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Kernel: $(uname -a)"
echo "SHELL: $SHELL"
echo "TTY: $(tty 2>/dev/null || echo 'NOT_A_TTY')"
echo "STDIN_ISATTY: $(python3 -c 'import sys; print(sys.stdin.isatty())')"
echo ""

# Create a pseudo-TTY using `script` and run the Python probe inside it
# The -q flag suppresses script's own messages, -c runs the command
# Output is piped to a temp file so we can capture it from the parent shell
PROBE_PAYLOAD=$(cat << 'PYEOF'
import os, subprocess, sys, termios, tty, json

def dump_flags(label, fd):
    try:
        attrs = termios.tcgetattr(fd)
        iflags, oflags, cflags, lflags = attrs[:4]
        flags = []
        if lflags & termios.ICANON: flags.append("ICANON")
        if lflags & termios.ECHO: flags.append("ECHO")
        if lflags & termios.ISIG: flags.append("ISIG")
        if iflags & termios.ICRNL: flags.append("ICRNL")
        if iflags & termios.IGNBRK: flags.append("IGNBRK")
        if oflags & termios.OPOST: flags.append("OPOST")
        if not (lflags & termios.ICANON) and not (lflags & termios.ECHO) and not (lflags & termios.ISIG):
            flags.append("RAW_MODE")
        hex_flags = {
            "iflag": hex(attrs[0]), "oflag": hex(attrs[1]),
            "cflag": hex(attrs[2]), "lflag": hex(attrs[3])
        }
        return {"label": label, "flags": " | ".join(flags) if flags else "NONE", "hex": hex_flags}
    except Exception as e:
        return {"label": label, "flags": f"ERROR: {e}", "hex": {}}

fd = sys.stdin.fileno()
print(f"=== PROBE: PID={os.getpid()} FD={fd} ===")

# Phase 1: Capture initial cooked mode (as Textual would save at startup)
print(json.dumps(dump_flags("INITIAL", fd)))
try:
    saved_attrs = termios.tcgetattr(fd)
except Exception as e:
    print(f"FATAL: cannot save initial attrs: {e}")
    sys.exit(1)

# Phase 2: Simulate Textual setting raw mode (as it does when active)
try:
    tty.setraw(fd)
    print(json.dumps(dump_flags("RAW_SET", fd)))
except Exception as e:
    print(json.dumps({"label": "RAW_SET", "flags": f"ERROR: {e}", "hex": {}}))

# Phase 3: Restore cooked mode (as app.suspend() should do)
try:
    termios.tcsetattr(fd, termios.TCSAFLUSH, saved_attrs)
    print(json.dumps(dump_flags("COOKED_RESTORED", fd)))
except Exception as e:
    print(json.dumps({"label": "COOKED_RESTORED", "flags": f"ERROR: {e}", "hex": {}}))

# Phase 4: Run subprocess (simulating vim) to see what it inherits
try:
    print(">>> subprocess.run(['stty', '-a']) OUTPUT:")
    subprocess.run(["stty", "-a"], timeout=5)
    print("<<< END subprocess OUTPUT")
except Exception as e:
    print(f">>> subprocess.run ERROR: {e}")

# Phase 5: Capture terminal state AFTER subprocess exits (before any restore)
print(json.dumps(dump_flags("AFTER_SUBPROCESS", fd)))

# Phase 6: Compare with saved cooked mode
try:
    after_attrs = termios.tcgetattr(fd)
    if after_attrs == saved_attrs:
        print(json.dumps({"label": "COMPARISON", "flags": "SAME", "hex": {}}))
    else:
        diff = {}
        for i, k in enumerate(["iflag", "oflag", "cflag", "lflag"]):
            if after_attrs[i] != saved_attrs[i]:
                diff[k] = {"saved": hex(saved_attrs[i]), "after": hex(after_attrs[i])}
        print(json.dumps({"label": "COMPARISON", "flags": "DIFFERENT", "hex": diff}))
except Exception as e:
    print(json.dumps({"label": "COMPARISON", "flags": f"ERROR: {e}", "hex": {}}))

# Phase 7: Restore original
try:
    termios.tcsetattr(fd, termios.TCSAFLUSH, saved_attrs)
    print(json.dumps(dump_flags("FINAL_RESTORED", fd)))
except Exception as e:
    print(json.dumps({"label": "FINAL_RESTORED", "flags": f"ERROR: {e}", "hex": {}}))

print("=== PROBE COMPLETE ===")
PYEOF
)

# Run the probe inside a pseudo-TTY
echo ">>> Running probe inside script (pseudo-TTY) <<<"
script -q -c "python3 -c '$PROBE_PAYLOAD'" /dev/null 2>&1 || {
    echo "WARNING: script command failed. Falling back to direct execution."
    python3 -c "$PROBE_PAYLOAD"
}
echo ">>> End of probe output <<<"