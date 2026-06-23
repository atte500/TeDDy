# Task: Pre-Commit Installation & Health Checks Relocation to Application Layer

## Business Goal
Reduce agent prompt noise by moving pre-commit hook installation and project health checks from the agent's Version Control Protocol (VCP) to the application layer (`start`/`resume` commands), displaying yellow terminal notifications when pre-commit or git is not available.

## Context
Previously, every agent prompt included `pre-commit install -t pre-commit -t post-commit` as Step 0 of the VCP. This has been removed entirely from all 6 prompts (already committed). The application now needs two startup health checks in `handle_new_session()` and `handle_resume_session()`:

1. **Pre-commit hook installation:** Conditionally install hooks if `.pre-commit-config.yaml` exists and `pre-commit` CLI is available. If either condition is false, display a **yellow warning notification**.
2. **Git initialization check:** Verify the current directory is a git repository. If not, display a **yellow warning notification** with guidance.

Key constraints:
- **Covered commands:** Only `handle_new_session` and `handle_resume_session` in `session_cli_handlers.py`. The `execute` command is NOT covered.
- **Notifications:** Use `typer.secho(msg, fg=typer.colors.YELLOW, err=True)` for warnings (existing pattern in codebase at `cli_formatter.py`).
- **Non-blocking:** Health check failures must NOT prevent startup — they are advisory only.

## Implementation Steps

### Step 1: Add imports
- **File:** [src/teddy_executor/adapters/inbound/session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py)
- **Change:** Add `import subprocess`, `import shutil`, and `import logging` to the module imports.

### Step 2: Add `_run_health_checks` orchestrator and helpers
- **File:** [src/teddy_executor/adapters/inbound/session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py)
- **Change:** Add three new private functions at module level:

**`_run_health_checks()`** — Orchestrator that calls both helpers:
```python
def _run_health_checks() -> None:
    """Run all startup health checks and display notifications if needed."""
    _ensure_commit_hooks()
    _check_git_initialized()
```

**`_ensure_commit_hooks()`** — Install pre-commit hooks with green/yellow notifications:
1. Check if `(Path.cwd() / ".pre-commit-config.yaml").exists()`.
2. If missing, display: `typer.secho("⚠ No pre-commit hooks configured", fg=typer.colors.YELLOW, err=True)` and return.
3. Check if `shutil.which("pre-commit")` returns a path.
4. If missing, display: `typer.secho("⚠ pre-commit CLI not found", fg=typer.colors.YELLOW, err=True)` and return.
5. If both true, run `subprocess.run(["pre-commit", "install", "-t", "pre-commit", "-t", "post-commit"], check=True, capture_output=True)`.
6. On failure (`CalledProcessError`), log a debug message and return (do not show any notification).
7. On success, display: `typer.secho("✓ pre-commit hooks installed", fg=typer.colors.GREEN, err=True)`.

**`_check_git_initialized()`** — Verify git repository with green/yellow notifications:
1. Check if `shutil.which("git")` returns a path.
2. If missing, display: `typer.secho("⚠ Git CLI not found", fg=typer.colors.YELLOW, err=True)` and return.
3. Run `subprocess.run(["git", "rev-parse", "--git-dir"], capture_output=True)`.
4. If return code is zero (already a repo), display: `typer.secho("✓ Git repository detected", fg=typer.colors.GREEN, err=True)` and return.
5. If return code is non-zero (not a repo), run `subprocess.run(["git", "init"], check=True, capture_output=True)`.
6. On failure, log a debug message and return.
7. On success, display: `typer.secho("✓ Git repository initialized", fg=typer.colors.GREEN, err=True)`.

### Step 3: Wire `_run_health_checks` into command handlers
- **File:** [src/teddy_executor/adapters/inbound/session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py)
- **Change:** Add `_run_health_checks()` calls in two locations:
  1. `handle_new_session()` — insert after `container.resolve(IInitUseCase).ensure_initialized()` and before `_run_cli_preflight_check(container, agent=agent)`.
  2. `handle_resume_session()` — insert at the beginning of the try block, before `typer.echo("Checking configurations...", err=True)` and `_run_cli_preflight_check(container)`.
  3. **Not in execute** — do NOT wire into `execute` command.

## Verification
- [ ] `teddy start` displays green "✓ pre-commit hooks installed" when `.pre-commit-config.yaml` exists and `pre-commit` CLI is available.
- [ ] `teddy start` displays yellow "⚠ No pre-commit hooks configured" when `.pre-commit-config.yaml` does not exist.
- [ ] `teddy start` displays yellow "⚠ pre-commit CLI not found" when `pre-commit` CLI is not installed.
- [ ] `teddy start` displays green "✓ Git repository detected" when already in a git repo.
- [ ] `teddy start` displays green "✓ Git repository initialized" when not in a git repo (auto-initializes).
- [ ] `teddy start` displays yellow "⚠ Git CLI not found" when git CLI is not installed.
- [ ] `teddy resume` behaves identically to `start` for all health checks.
- [ ] `teddy execute --plan-content "..."` does NOT run health checks (no warnings or hook installation).
- [ ] A project without pre-commit or git CLI installed starts successfully (warnings are advisory, not blocking).
