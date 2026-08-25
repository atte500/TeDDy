# CI/CD Template

This template documents how to set up Continuous Integration and the Debug Workflow for Remote Probing.

## CI Pipeline

The CI pipeline consists of two parallel jobs:

### Job 1: Blocking OS Matrix Test Suite
- Runs on each push and pull request.
- Executes across multiple OS targets (e.g., ubuntu-latest, windows-latest, macos-latest).
- Runs the full test suite: `{runner} pytest`.
- **Blocking:** If this job fails, the CI pipeline is marked as failed.

### Job 2: Non-Blocking Quality Checks
- Runs quality tools: fast formatters, linters, security/secret scanners, type checkers, repository-wide structural checks.
- Excludes sandboxes (`spikes/`) and third-party dependencies.
- **Non-Blocking:** Configured with `continue-on-error: true` so quality failures do not block the pipeline.

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
