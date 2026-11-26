# Slice: Interactive-Prompt Sentinel Hardening
- **Status:** Planned
- **Milestone:** [Milestone 7: Runtime Reliability & Boundary Purity](/docs/project/milestones/07-runtime-reliability.md)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [ShellAdapter](/docs/architecture/adapters/outbound/shell_adapter.md), [IShellExecutor](/docs/architecture/core/ports/outbound/shell_executor.md)
- **Scope Slug:** `interactive-prompt-sentinel`

## Goal
Fire the interactive-prompt sentinel only when a child process is genuinely waiting for input, and never at the cost of hiding the real output it was inspecting, so a failing command that happens to print a prompt-like string reports its own failure.

## Context
- `ShellAdapter._detect_interactive_prompt(stderr, stdout)` (`shell_adapter.py:367`) is called from two sites (`:210` and `:353`) and fires on a non-zero exit whose combined output incidentally contains a prompt-like substring. A full `make test` run whose failure output quotes a Python prompt, a `>>>` snippet, a shell `$` line, or a heredoc echo can therefore have its entire stream replaced and its real result hidden — the one failure mode worse than a wrong verdict, because it hides the evidence.
- The discriminator the current check lacks is presence. A child process can only be interactively blocked when its stdin is a terminal, and this codebase already injects that fact: `ISystemEnvironment.isatty()` is resolved at the composition root, and the Terminal & Environmental Gates law forbids deriving it from ambient state inside a service or adapter. Requiring the injected capability is therefore both the correct rule and the house style.
- Presence alone is not sufficient. A command run from a terminal can also fail while merely printing something that looks like a prompt, so the second signal is temporal: a genuinely blocked child has stopped writing and stayed quiet. `InterruptGuard` already owns a grace-window notion for exactly this kind of judgement, and the sentinel's quiet-period threshold belongs in the configuration layer rather than as a module constant.
- When the sentinel does fire, the captured output must survive into the execution report. Today the stream is replaced, so the operator loses both the prompt text and the context around it — the fix includes preserving rather than substituting.
- Overlaps: [07-02](./07-02-test-suite-integrity.md) also exercises presence-gated behaviour, so both slices inject the same capability and a concurrent run needs a rebase.

## Scenarios

> As a user, I want a failing command's real output reported.

```gherkin
Given a non-interactive run whose failing output quotes a prompt-like string
When the command exits non-zero
Then the sentinel does not fire
And the report contains the command's actual stderr
```

> As a user, I want a genuinely blocked command surfaced with its context.

```gherkin
Given a command that inherits a terminal and blocks on input
When it stays quiet past the configured window
Then the sentinel fires naming the detected prompt
And the report preserves the output captured before it blocked
```

> As a maintainer, I want the sentinel's judgement testable without a real terminal.

```gherkin
Given an injected environment capability reporting no terminal
When the sentinel is evaluated against prompt-like output
Then it reports no prompt
And the same evaluation with the capability reporting a terminal reports one
```

## Edge Cases
- **Pipe-fed stdin**: If the child's stdin is a pipe rather than a terminal, then it can never be interactively blocked and the sentinel must not fire, regardless of output.
- **Interactive subcommand in a non-interactive run**: If stdin is not a terminal but the command explicitly opens `/dev/tty`, then it can still block; the sentinel does not attempt to cover that case and the timeout is the remedy, which the slice states rather than silently omits.
- **Quiet window versus long build**: If a child is silent because it is compiling, then a quiet-only rule false-positives; the prompt pattern must be the last thing written for the sentinel to fire, so silence alone is never sufficient.
- **Output preserved**: If the sentinel fires, then the report keeps the captured stderr and appends the diagnostic rather than replacing the stream, because the whole point is to leave evidence.
- **Windows**: If the platform reports no terminal on the child descriptor, then the presence check returns false and the sentinel stays quiet; the timeout remains the backstop on both platforms.
- **Configurable window**: If the quiet threshold is a module constant, then it violates the Centralized Configuration law; it belongs beside the existing interrupt grace window in the configuration layer.
- **Pattern source**: If the prompt patterns are inlined, then they drift from the message text they resemble; they live in one definition consumed by the sentinel and by its tests.
- **Process already exited**: If the process exited non-zero with output that ends in a prompt-like line, then no wait occurred and the sentinel must not fire, because nothing was blocked.
- **Both branches tested**: If only the terminal branch is exercised, then the false-positive fix is unobservable; both branches are driven through the injected capability.

## Key Unknowns
- [ ] [Technical] How the adapter observes "still running and quiet" without changing the process launch contract. Design Sensitivity: if the existing wait already polls with a timeout → the quiet window is a counter inside it and the change stays inside the adapter; if the wait is a single blocking call → the adapter needs the poll interval it already uses elsewhere or a modest restructure of the wait, which makes this a larger adapter change and moves the quiet-window logic into a small collaborator the adapter injects, keeping it unit-testable.

## Impact
1. `[MIGRATE]` `ShellAdapter._detect_interactive_prompt` — requires the injected presence capability and a quiet window, and inspects only the tail of the output.
2. `[MIGRATE]` Both call sites — pass the capture through unchanged so the report preserves it.
3. `[NEW]` The quiet-window threshold and the prompt pattern set in the configuration layer, beside the interrupt grace window.
4. `[MIGRATE]` The execution report path — keeps the captured stderr when the sentinel fires and appends the diagnostic.
5. `[NEW]` Unit tests driving both presence branches, the pipe-fed case, and the exited-with-prompt-like-output case.
6. `[MIGRATE]` The `ShellAdapter` and `IShellExecutor` pages — record the sentinel's contract, its two signals, and what it deliberately does not cover.

## Deliverables
- [ ] **Interface** — Record the sentinel's contract on the shell executor port: the two signals it requires, the diagnostic it emits, and the case it declines to cover.
- [ ] **Harness** — Add the two-branch presence tests plus the pipe-fed and already-exited cases, all through the injected capability.
- [ ] **Adapter** — Require presence, gate on tail output, apply the configured quiet window, and preserve the captured output on firing.
- [ ] **Cleanup** — Record the threshold and pattern set in the configuration layer and update both component pages.

## Implementation Notes

## Verification
1. **False positive gone:**
   Run a test command whose failure output quotes a prompt-like line from a non-terminal shell.
   Verify the report contains that output and no prompt diagnostic.
2. **True positive preserved:**
   Run a command that blocks on input from a terminal past the configured window.
   Verify the diagnostic names the prompt and the captured output survives.
3. **Both branches covered:**
   Run the new unit tests.
   Verify the injected capability drives both presence answers.
