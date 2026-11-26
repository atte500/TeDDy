# CI/CD Template

> **⚠️ This is an example template.** Adapt the runner, test commands, and tool-specific details (e.g., `uv run pytest`, pre-commit hook list) to match your project's actual setup. The concrete examples shown may not work verbatim in all environments.

This template documents how to set up Continuous Integration and the Debug Workflow for Remote Probing.

## CI Pipeline

The CI pipeline consists of three parallel jobs. Two are merge gates; one is advisory.

A check earns a merge veto only when it is deterministic (the verdict is reproducible locally) and diff-actionable (the author can fix it within the commit that triggered it). Deterministic static analysis meets that bar for a project that starts at zero debt. Aggregate, repository-wide metrics do not: no single commit can satisfy a file-length cap or a duplication threshold without unrelated refactoring.

### Job 1: Blocking OS Matrix Test Suite
- Runs on each push and pull request.
- Executes across multiple OS targets (e.g., ubuntu-latest, windows-latest, macos-latest).
- Runs the full test suite: `{runner} pytest`.
- Discovers tests via `testpaths` in `pyproject.toml`; the CI step passes no path so the config stays the single source of truth.
- Carries a wall-clock cap (`timeout-minutes`) so a hung test cannot occupy a runner indefinitely.
- **Blocking:** If this job fails, the CI pipeline is marked as failed.

### Job 2: Blocking Static Analysis
- Executes across the same OS matrix as the test suite, because static verdicts are not OS-neutral: a type checker surfaces platform-conditional attribute errors (a `msvcrt` member that exists only on Windows), and the structural checkers guard POSIX-only patches that only the Windows leg exercises.
- Runs deterministic, diff-actionable checks, each in its own step with `if: success() || failure()` so every check reports even when an earlier one fails: formatters, linters, secret scanners, security audits, type checkers, and structural checkers.
- Scopes the heavy checks (type checkers, security/dependency scanners, structural checkers) to the non-default `manual` stage so they never slow down the local pre-commit loop.
- Excludes sandboxes (`spikes/`) and third-party dependencies.
- Sets `fail-fast: false` so each OS leg reports its own verdict instead of cancelling its siblings, and `defaults.run.shell: bash` so the checks run identically on Windows.
- **Blocking:** Configured with `continue-on-error: false`. A failure on any OS leg fails the pipeline.

### Job 3: Advisory Quality Metrics
- Runs aggregate, repository-wide checks that no single commit can satisfy without unrelated refactoring: file-length caps and duplication thresholds.
- Executes across the same OS matrix so a platform-specific path or line-ending difference cannot hide behind a single-runner verdict. These checks carry no merge veto, so a matrix here costs runner minutes without risking a blocked merge.
- Sets `fail-fast: false` and `defaults.run.shell: bash` for the same reasons as Job 2.
- **Advisory:** Configured with `continue-on-error: true`. Findings surface as triage items, not merge blockers, and the job never vetoes a merge.

```shell
# Fast hooks (default stage)
{runner} pre-commit run --all-files
# Heavy hooks (CI-only manual stage, run by the blocking static-analysis job)
{runner} pre-commit run --all-files --hook-stage manual
```

See [Pre-Commit Template](./pre-commit.md) for the local-vs-CI hook split.

### How to create it

Create `.github/workflows/ci.yml` in your project with the following structure:

```yaml
name: CI

on:
  push:
    branches: [ "**" ]
  pull_request:
    branches: [ main ]
  workflow_dispatch: {}

# No `concurrency` block: GitHub runs workflow runs in parallel unless a block
# serializes them. Add one only when overlapping runs are unsafe (for example a
# deploy that must not race itself). A per-ref group instead queues every commit
# behind its predecessor for the full duration of the older run.

jobs:
  # Job 1: Blocking OS matrix test suite.
  test-suite:
    name: Test Suite (${{ matrix.os }})
    runs-on: ${{ matrix.os }}
    timeout-minutes: 10
    defaults:
      run:
        shell: bash
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    steps:
      - name: Check out repository
        uses: actions/checkout@v5

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: "3.14"

      - name: Install uv
        uses: astral-sh/setup-uv@v8.3.2

      - name: Install dependencies
        run: {runner} sync --frozen

      - name: Run Tests
        run: {runner} pytest

  # Jobs 2 and 3 share the test suite's OS matrix: a type checker surfaces
  # platform-conditional attribute errors, and the structural hooks guard
  # POSIX-only patches that only the Windows leg exercises.
  # Job 2: Blocking static analysis (deterministic checks, OS matrix).
  static-analysis:
    name: Static Analysis (${{ matrix.os }})
    runs-on: ${{ matrix.os }}
    timeout-minutes: 10
    continue-on-error: false
    defaults:
      run:
        shell: bash
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    steps:
      - name: Check out repository
        uses: actions/checkout@v5

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: "3.14"

      - name: Install uv
        uses: astral-sh/setup-uv@v8.3.2

      - name: Install dependencies
        run: {runner} sync --frozen

      # Each check runs with `if: success() || failure()` so all checks run
      # even if an earlier check fails. Every deterministic check blocks merge.
      - name: "Secrets Check (detect-secrets)"
        if: success() || failure()
        run: |
          {runner} pre-commit run detect-secrets --all-files

      - name: "Code Formatting (ruff format)"
        if: success() || failure()
        run: |
          {runner} pre-commit run ruff-format --all-files

      - name: "Linter (ruff check)"
        if: success() || failure()
        run: |
          {runner} pre-commit run ruff-lint --all-files

      - name: "Type Checker (mypy)"
        if: success() || failure()
        run: |
          {runner} pre-commit run mypy --all-files --hook-stage manual

      - name: "Structural Check (Architecture & Boundaries)"
        if: success() || failure()
        run: |
          {runner} pre-commit run check-architecture-boundaries --all-files --hook-stage manual

      # pre-commit accepts a single hook id per `run` invocation, so each hook
      # gets its own step to keep the granular, per-check reporting.
      - name: "Security Audit (bandit)"
        if: success() || failure()
        run: |
          {runner} pre-commit run bandit --all-files --hook-stage manual

      - name: "Security Audit (pip-audit)"
        if: success() || failure()
        run: |
          {runner} pre-commit run pip-audit --all-files --hook-stage manual

  # Job 3: Advisory quality metrics (aggregate checks, non-blocking, OS matrix).
  quality-metrics:
    name: Quality Metrics (${{ matrix.os }})
    runs-on: ${{ matrix.os }}
    timeout-minutes: 10
    continue-on-error: true
    defaults:
      run:
        shell: bash
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    steps:
      - name: Check out repository
        uses: actions/checkout@v5

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: "3.14"

      - name: Set up Node.js (for jscpd)
        uses: actions/setup-node@v5
        with:
          node-version: "24"

      - name: Install uv
        uses: astral-sh/setup-uv@v8.3.2

      - name: Install dependencies
        run: {runner} sync --frozen

      - name: "Check Python File Length (Max 500 Lines)"
        if: success() || failure()
        run: |
          find src tests -name "*.py" | xargs wc -l | awk '$1 > 500 && $2 != "total" {print "File " $2 " is too long (" $1 " lines)."; exit 1}'

      - name: "Detect Code Duplication (jscpd)"
        if: success() || failure()
        run: |
          npx jscpd --min-tokens 25 --threshold 0 --ignore "**/.venv/**,**/ports/**,**/prompts/**,**/spikes/**"
```

## Debug Workflow (Remote Probing Protocol)

The Debugger uses a remote probing workflow to investigate platform-specific or CI-only bugs that cannot be reproduced locally.

### What it does
1. Accepts a `reason` string via `workflow_dispatch`.
2. Checks out the repository on a CI runner.
3. Executes `spikes/debug/probe.sh` (the probe script containing diagnostic logic).
4. Captures output for retrieval via `gh run view --log`.

### How to create it
Create `.github/workflows/debug.yml` in your project with the following structure:

```yaml
name: Debug Probe
on:
  workflow_dispatch:
    inputs:
      reason:
        description: 'Reason for the probe'
        required: true
        default: 'investigate issue'

jobs:
  probe:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Probe
        run: |
          chmod +x spikes/debug/probe.sh
          ./spikes/debug/probe.sh
```

### How to use it
1. Create a probe script at `spikes/debug/probe.sh` containing diagnostic logic.
2. Commit, push, and dispatch via your project's remote probe command (e.g., `just probe "reason for probing"`).
3. The probe command will: push the probe → trigger the workflow → wait for completion → retrieve logs.

### Prerequisites
- `gh` (GitHub CLI) must be authenticated.
- A `.github/workflows/debug.yml` workflow must exist.
- A probe script must exist at `spikes/debug/probe.sh`.

## Reference
- [Tooling Template](./tooling.md) for the remote probe command.
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
