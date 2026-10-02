# Bug: Ctrl+C (SIGINT) Not Firing During TeDDy Execution on the Host Terminal

- **Status:** Unresolved
- **Milestone:** N/A (ad-hoc slice)
- **Vertical Slice:** [00-21-session-interrupt-resume-message.md](/docs/project/slices/00-21-session-interrupt-resume-message.md)
- **Specs:** N/A

## Symptoms

Verification steps 6 and 7 of the `session-interrupt-resume-message` slice are non-functional on the user's machine:

- **Step 6 (Ctrl+C during execution, two-phase drain):** `uv run teddy start`, approve a plan with a long `EXECUTE` (e.g. `echo one`, `sleep 5`, `echo two`), press Ctrl+C during the sleep. Expected: the in-flight command completes, the remaining actions are logged INTERRUPTED, `report.md` is created, and the process exits. Observed: nothing happens (per the user).
- **Step 7 (Ctrl+C while waiting, immediate exit):** press Ctrl+C during the planning LLM call ("Waiting for assistant to respond...") or during an `ask_question` prompt. Expected: immediate exit with no partial artifacts. Observed: nothing happens (per the user).

The user reports the behaviour "not working on my machine at all" and suspects a terminal keybinding configuration conflict, and explicitly requested this be tracked as a SEPARATE case file to be tackled with the Debugger independently.

## Context & Scope

### Regressing Delta
N/A — the interrupt wiring is the delivered feature under verification (`InterruptGuard` Seam → Migration → Wiring). No regression is presumed; the failure is at the real-terminal interaction layer, outside `typer.testing.CliRunner`'s reach.

### Environmental Triggers
- Host: macOS (Darwin 25.5.0), shell `/bin/zsh`.
- Exact terminal emulator + keybindings UNKNOWN — the user suspects a keybinding conflict preventing SIGINT delivery on Ctrl+C.

### Ruled Out
- The in-process `InterruptGuard` phase logic (WAITING raises; EXECUTING sets the flag; a second signal within the grace window escalates) — `tests/suites/unit/core/utils/test_interrupt_guard.py` passes.
- SIGINT handler installation/restoration at the session-loop boundary — `tests/suites/unit/adapters/inbound/test_session_loop_interrupt_wiring.py` passes.
- Shell child process-group shielding (`preexec_fn` setsid/setpgrp on POSIX) — characterized by `tests/suites/unit/adapters/outbound/test_shell_adapter_kwargs.py`.

## Diagnostic Analysis

### Causal Model
Because the in-process tests prove both the guard's phase semantics and the boundary's handler installation, a total absence of interrupt behaviour on a real terminal most plausibly indicates that the terminal is NOT delivering SIGINT to the TeDDy process on Ctrl+C (keybinding remap / terminal configuration), so the installed handler never fires. An alternative hypothesis (unverified) is that the new process-group shielding of the in-flight child (`setsid`/`setpgrp`) interacts with the terminal's foreground process-group handling such that Ctrl+C is swallowed.

### Discrepancies
- The user's own diagnostic ("I suspect this has to do with my keybindings") conflicts with the possibility of a TeDDy-side defect. Cannot be resolved without observing actual signal delivery on the host.

### Investigation History
1. Hypothesis: the guard/boundary logic is broken. Observation: the relevant unit suites pass in isolated runs. Conclusion: unlikely; the failure appears environmental.
2. Hypothesis: the terminal does not deliver SIGINT on Ctrl+C. Observation: the user's suspicion only. Conclusion: UNCONFIRMED — needs a minimal remote probe on the host.

## Solution
_(To be completed by the Debugger.)_

Recommended first probe: run a minimal Python script on the host that installs a SIGINT handler and prints on receipt (e.g. `python -c "import signal,time; signal.signal(signal.SIGINT, lambda *a: print('SIGINT')); time.sleep(30)"`), then press Ctrl+C — this isolates whether SIGINT is delivered to a foreground process at all, independent of TeDDy. If SIGINT is not delivered → terminal/keybinding configuration (not a TeDDy defect). If SIGINT IS delivered but TeDDy does not react in a real terminal → the process-group shielding is the prime suspect. Preventative: a documented manual-verification procedure and/or a `teddy doctor`-style SIGINT self-test.
