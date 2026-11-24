# Project Tooling Template

> **⚠️ This is an example template.** Adapt the runner, commands, and tool-specific details to match your project's actual setup. Bind the exact invocations for your repository in `docs/project/PROJECT.md` (`## Tooling`) so agents see them on every turn without hardcoding runner syntax in agent prompts.

TeDDy separates **what** workflow operations exist (defined in `MRP.md` and agent prompts) from **how** a repository runs them (defined in `docs/project/PROJECT.md` under `## Tooling` and backed by a task runner + `scripts/`).

## Standard Command Interface

Every project should expose these standard commands through its chosen runner (`justfile`, `Taskfile.yml`, `Makefile`, `mise.toml`, or language-native runner) and document their exact invocations in `docs/project/PROJECT.md`:

| Command | Behavioral Contract |
| --- | --- |
| `test` | Runs the configured test runner unfiltered (e.g., `pytest` configured via `testpaths` in `pyproject.toml`). |
| `commit` | Local-only gate: stages all changes, runs fast pre-commit auto-fixers, re-stages fixes, and commits *without* `--no-verify` with a single-line Conventional Commit message (`"<type>(<scope>): <description>"`). The unskippable post-commit hook runs the full suite and reverts on failure. |
| `push` | Rebases on upstream and pushes (`git pull --rebase && git push`). Deferred to session Conclusion. |
| `ci-watch` | Resolves pushed `HEAD` (or explicit commit/base), waits through registration lag, watches all triggered workflows, and attributes blocking failures against the nearest run-bearing ancestor (failing safe on unknown conclusion or job-less base; non-blocking failures never block). |
| `logs` | Fetches logs for a run ID (`--log-failed`, or filtered by step substring), stripping timestamps, ANSI escapes, and `##[group]` noise. |
| `probe` | Remote Probing Protocol: commits `spikes/debug/probe.sh` (`--no-verify --allow-empty`), pushes, dispatches `.github/workflows/debug.yml` with a `reason` input, polls by pushed SHA, and downloads `spikes/debug/probe_output.txt`. |
| `help` | Lists available project commands (native in `just --list`, `task --list`, `mise tasks`). |

## Modular Recipes vs. `scripts/`

Split large recipe collections across `just/*.just` via `import` if needed for organization, while placing non-trivial multi-step logic (`ci-watch`, `logs`, `probe`, custom extractors) into standalone scripts under `scripts/` (subject to all quality gates):

- Avoids embedding escaped shell/`awk`/`sed` pipelines inside runner syntax.
- Eliminates platform shell discrepancies across Linux, macOS, and Windows (no Git Bash, `awk`, or `sed` dependencies when logic runs in the project runtime such as Python).
- Makes tooling logic lintable, type-checked, and directly unit-testable.

## Primary Example (`justfile` + `scripts/`)

Written in Rust, `just` requires no `.PHONY` declarations, accepts spaces or tabs, supports native positional arguments and defaults, loads `.env` files with one directive, and provides built-in `just --list` discovery.

```just
set dotenv-load

# Show available commands
default:
    @just --list

# Run the full test suite
test *args:
    uv run pytest {{args}}

# Stage all changes, run pre-commit auto-fix pass, and commit locally
commit msg:
    uv run python scripts/tooling/commit.py "{{msg}}"

# Rebase and push local commits to remote
push:
    git pull --rebase
    git push

# Watch CI workflows for HEAD (or explicit COMMIT/BASE) and attribute regressions
ci-watch *args:
    uv run python scripts/tooling/ci_watch.py {{args}}

# Extract sanitized CI logs for a run ID (and optional step substring)
logs run step="":
    uv run python scripts/tooling/ci_logs.py "{{run}}" "{{step}}"

# Push probe script, dispatch debug workflow, and print probe output
probe reason:
    uv run python scripts/tooling/probe.py "{{reason}}"
```

### Example `probe.sh` Contract

The Remote Probing Protocol expects `spikes/debug/probe.sh` to write diagnostics to `spikes/debug/probe_output.txt` so `.github/workflows/debug.yml` can upload it as the `probe-result` artifact:

```bash
#!/usr/bin/env bash
set -euo pipefail

mkdir -p spikes/debug
cat > spikes/debug/probe_output.txt <<EOF
=== Probe Result ===
OS: $(uname -s)
Python: $(python --version 2>&1)
Git: $(git --version 2>&1)
EOF
```

- The debug workflow must use a single job (no build matrix) so parallel jobs cannot overwrite `probe-result`.
- Keep the script minimal and self-contained using a single heredoc.

## Alternative Runners

Teams can use any runner that satisfies the Standard Command Interface and document its invocations in `docs/project/PROJECT.md` (`## Tooling`):

- **`Task` (`Taskfile.yml`):** Embeds its own POSIX shell (`mvdan/sh`) for out-of-the-box Windows parity without Git Bash. Pass arguments via `--` and `{{.CLI_ARGS}}` or explicit task variables (`task commit -- "feat: ..."`).
- **`mise` (`mise.toml`):** Useful when adopting a unified runtime manager + env manager + task runner (`mise run test`, `mise run commit "..."`), with longer scripts stored in `mise-tasks/`.
- **`Makefile`:** Ubiquitous on Unix without installing extra binaries, but requires `.PHONY` declarations, literal tab indentation, `VAR="value"` named inputs (to avoid positional goal execution), parse-time variable validation, and `SHELL := bash.exe` / Git Bash handling on Windows.

## Reference

- [PROJECT.md Template](./PROJECT.md) — `## Tooling` command-binding table.
- [CI Template](./ci.md) — `.github/workflows/debug.yml` for the Remote Probing Protocol.
- [Pre-Commit Template](./pre-commit.md) — local pre-commit auto-fixers and the post-commit test gate.
