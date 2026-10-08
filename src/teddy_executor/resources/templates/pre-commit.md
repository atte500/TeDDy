# Pre-Commit Template

> **⚠️ This is an example template.** Adapt the runner, hook set, and tool-specific details (e.g., `uv run`, the pre-commit hook list) to match your project's actual setup. The concrete examples shown may not work verbatim in all environments.

This template documents how to set up the [Pre-commit](https://pre-commit.com/) framework as the project's local quality gate. It runs fast checks before a commit is recorded and the full test suite after, keeping the repository green-to-green.

Pre-commit has two stages:

- **`pre-commit`** — fast checks (formatters, linters, type checkers, secret scanners), scoped strictly to the files being committed.
- **`post-commit`** — the full test suite, run after the commit is recorded. If it fails, the commit is reverted while keeping the changes staged. This stage is **not** affected by `--no-verify` and is the only truly unskippable gate.

## 1. Install the Pre-commit framework

```shell
uv tool install pre-commit   # or: pip install pre-commit   # or: brew install pre-commit
pre-commit --version
```

## 2. Create `.pre-commit-config.yaml`

Place this in the project root. Start with the universal hooks, then add security and project-local hooks that shell out to the project runner.

```yaml
# Exclude experimental sandboxes from every hook.
exclude: '^spikes/'
repos:
  # ── Universal (every project) ──
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-toml
      - id: check-added-large-files
        args: ['--maxkb=500']
      - id: check-case-conflict
      - id: check-merge-conflict

  # ── Secrets & security ──
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.9
    hooks:
      - id: bandit
        args: ["-c", "pyproject.toml"]
        exclude: ^(tests|spikes)/

  # ── Language-specific: run tools through the project runner ──
  - repo: local
    hooks:
      - id: ruff-lint
        name: Ruff Linter
        entry: uv run ruff check --fix --force-exclude
        language: system
        types: [python]
        require_serial: true
      - id: ruff-format
        name: Ruff Formatter
        entry: uv run ruff format --force-exclude
        language: system
        types: [python]
        require_serial: true
      - id: mypy
        name: Mypy
        entry: uv run mypy
        language: system
        types: [python]
        require_serial: true

  # ── Post-commit test gate (unskippable) ──
  - repo: local
    hooks:
      - id: post-commit-test-gate
        name: Post-commit test gate
        entry: uv run python .githooks/post-commit.py
        language: system
        stages: [post-commit]
        always_run: true
        pass_filenames: false
```

**Tip:** Pin exact `rev` tags so every teammate runs identical checks.

## 3. Install the hooks

```shell
pre-commit install                          # pre-commit stage
pre-commit install --hook-type post-commit  # post-commit test gate
```

`pre-commit install` writes the runner into `.git/hooks/`. The pre-commit stage runs only against the files you have staged; the post-commit stage runs the full suite after every commit.

## 4. Run hooks manually

```shell
pre-commit run --all-files             # run all pre-commit hooks against the repo (first setup)
pre-commit run ruff-lint --all-files   # run a single hook
```

`--all-files` is for the initial setup only; normal commits check just the staged files.

## 5. The post-commit test gate

The post-commit stage is the unskippable safety net. It invokes a project script (e.g. `.githooks/post-commit.py`) that:

1. Verifies the runner and test framework are available, printing a clear, actionable error if not.
2. Runs the full test suite via the project's test command (e.g. `make test` / `uv run pytest`).
3. On failure, reverts the commit with `git reset --soft HEAD~1`, keeping the changes staged for investigation.

```python
# .githooks/post-commit.py (sketch)
import subprocess
import sys


def main() -> None:
    # Pre-flight: verify the runner + test framework are available.
    # Run the full suite.
    result = subprocess.run(["uv", "run", "pytest", "--tb=short", "-q"])
    # On failure, revert the commit but keep the changes staged.
    if result.returncode != 0:
        print("TESTS FAILED \u2014 reverting commit")
        subprocess.run(["git", "reset", "--soft", "HEAD~1"], check=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

Because the hook is declared with `stages: [post-commit]`, `git commit --no-verify` cannot bypass it.

## 6. Bypass (emergency only)

```shell
git commit --no-verify      # skip the pre-commit stage for this commit
SKIP=ruff-lint git commit   # skip a single hook
```

The **post-commit test gate is never bypassable**. Treat a pre-commit bypass as a temporary measure followed by a cleanup commit that resolves the underlying issue.

## Reference
- [ARCHITECTURE.md Template](./ARCHITECTURE.md) — pre-commit + post-commit conventions.
- [Makefile Template](./makefile.md) — `make test` and the VCP commit workflow.
- [Pre-commit documentation](https://pre-commit.com/)
