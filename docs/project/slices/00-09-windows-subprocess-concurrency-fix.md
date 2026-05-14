# Slice: Windows Subprocess Concurrency Fix
- **Status:** Planned
- **Milestone:** N/A
- **Specs:** N/A
- **Prototype:** N/A
- **MRE:** [spikes/debug/remote_probe.sh](/spikes/debug/remote_probe.sh) and [spikes/debug/mre_runner.py](/spikes/debug/mre_runner.py)
- **Showcase:** N/A
- **Component Docs:** N/A

## Business Goal
Eliminate intermittent CI worker crashes on Windows environments. This ensures stable and reliable testing, restoring developer velocity and preventing false-positive pipeline failures caused by concurrent standard input handle inheritance.

## Scenarios
> As a Contributor, I want the test suite to run consistently on Windows with xdist so that my PR checks are reliable and do not require random restarts.

```gherkin
Given a Windows environment running pytest with xdist (-n 4)
When multiple tests execute shell actions concurrently via `ShellAdapter` or `SystemEnvironmentAdapter`
Then the subprocesses should isolate their standard input (DEVNULL)
And the xdist workers should not fatally crash with "Not properly terminated"
```

## Deliverables
- [ ] **Logic** - Refactor `ShellAdapter._prepare_subprocess_kwargs` to explicitly set `stdin=subprocess.DEVNULL` for all platforms, including Windows, removing the POSIX-only condition.
- [ ] **Logic** - Refactor `ShellAdapter._run_subprocess` to ensure background subprocesses also use `stdin=subprocess.DEVNULL`.
- [ ] **Logic** - Refactor `SystemEnvironmentAdapter.run_command` to explicitly pass `stdin=subprocess.DEVNULL` to both `subprocess.run` and `subprocess.Popen`.
- [ ] **Logic** - Refactor `SystemEnvironmentInspector.get_env_snapshot` to explicitly pass `stdin=subprocess.DEVNULL` to `subprocess.run`.
- [ ] **Logic** - Refactor `TextualPlanReviewerEditor` methods launching subprocesses to explicitly pass `stdin=subprocess.DEVNULL` to prevent potential async loop blocking on Windows.

## Implementation Notes
*Pending Developer Implementation.*

## Delta Analysis
This is a non-breaking internal stabilization fix. It modifies the outbound adapters to safely invoke native OS tools without bleeding test harness state (mocked stdin) into the spawned process handles on Windows.

## Guidelines for Implementation
- Ensure that the addition of `stdin=subprocess.DEVNULL` does not interfere with explicitly interactive tooling (e.g., if a tool legitimately requires interactive input, though the architecture assumes automated execution in these layers).
- Review `subprocess` module documentation for `DEVNULL` usage to ensure backwards compatibility and proper pipe closure.
