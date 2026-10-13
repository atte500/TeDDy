# CI/CD Template

> **⚠️ This is an example template.** Adapt the runner, test commands, and tool-specific details (e.g., `uv run pytest`, pre-commit hook list) to match your project's actual setup. The concrete examples shown may not work verbatim in all environments.

This template documents how to set up Continuous Integration and the Debug Workflow for Remote Probing.

## CI Pipeline

The CI pipeline consists of two parallel jobs:

### Job 1: Blocking OS Matrix Test Suite
- Runs on each push and pull request.
- Executes across multiple OS targets (e.g., ubuntu-latest, windows-latest, macos-latest).
- Runs the full test suite: `{runner} pytest`.
- **Blocking:** If this job fails, the CI pipeline is marked as failed.

### Job 2: Non-Blocking Quality Checks
- Runs the pre-commit hooks in two explicit passes: the fast hooks (formatters, `detect-secrets`, merge-conflict check) at the default `pre-commit` stage, then the heavy hooks (type checkers, security/dependency scanners, and the repository-wide structural checkers) at the non-default `manual` stage.
- The heavy hooks are scoped to the `manual` stage so they never slow down the local pre-commit loop; CI invokes both stages explicitly.
- Excludes sandboxes (`spikes/`) and third-party dependencies.
- **Non-Blocking:** Configured with `continue-on-error: true` so quality failures do not block the pipeline.

```shell
# Fast hooks (default stage)
{runner} pre-commit run --all-files
# Heavy hooks (CI-only manual stage)
{runner} pre-commit run --all-files --hook-stage manual
```

See [Pre-Commit Template](./pre-commit.md) for the local-vs-CI hook split.

### How to create it

Create `.github/workflows/ci.yml` in your project with the following structure:

```yaml
name: CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]
  workflow_dispatch: {}

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: false

jobs:
  # Job 1: Blocking OS matrix test suite.
  test-suite:
    name: Test Suite (${{ matrix.os }})
    runs-on: ${{ matrix.os }}
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

  # Job 2: Non-blocking quality checks (continue-on-error).
  quality-checks:
    name: Quality Checks
    runs-on: ubuntu-latest
    continue-on-error: true
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

      # Quote any step name that contains a colon. An unquoted YAML plain
      # scalar cannot contain ": " (colon+space) — it would be parsed as a
      # nested mapping and fail the entire workflow.
      - name: "Run Pre-commit Hooks (fast: formatters, secrets)"
        run: |
          {runner} pre-commit run --all-files

      - name: "Run Pre-commit Hooks (heavy: types, security, structural)"
        run: |
          {runner} pre-commit run --all-files --hook-stage manual
```

## Debug Workflow (Remote Probing Protocol)

The Debugger uses a remote probing workflow to investigate platform-specific or CI-only bugs that cannot be reproduced locally.

### What it does
1. Accepts a `reason` string via `workflow_dispatch`.
2. Checks out the repository on a CI runner.
3. Executes `spikes/debug/remote_probe.sh` (the probe script containing diagnostic logic).
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
          chmod +x spikes/debug/remote_probe.sh
          ./spikes/debug/remote_probe.sh
```

### How to use it
1. Create a probe script at `spikes/debug/remote_probe.sh` containing diagnostic logic.
2. Commit and push via: `make probe 'reason for probing'`
3. The Makefile will: push the probe → trigger the workflow → wait for completion → retrieve logs.

### Prerequisites
- `gh` (GitHub CLI) must be authenticated.
- A `.github/workflows/debug.yml` workflow must exist.
- A probe script must exist at `spikes/debug/remote_probe.sh`.

## Reference
- [Makefile Template](./makefile.md) for `make probe` command.
- [Debugger RPP Rule](../prompts/debugger.xml) for protocol details.
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
