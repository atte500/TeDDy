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

  # ── Secrets ──
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']

  # ── Language-specific: fast auto-fixers through the project runner ──
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

**Local vs CI scope:** keep only fast auto-fixers (`ruff --fix`, `ruff format`, `trailing-whitespace`, `end-of-file-fixer`), `detect-secrets`, and `check-merge-conflict` locally. Noisy, false-positive-prone static analysis (`mypy`, `bandit`, `pip-audit`, and repository-wide structural checkers) belongs in CI, where it runs non-blocking — the real friction is hook false positives forcing inline suppressions, not blocking. See the Quality-Gate Bypass Policy for the config-level-vs-inline bypass rule.

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

1. **Guards against automated git operations.** During `git pull --rebase`, Git fires the `post-commit` hook once per replayed commit; because the hook reverts on failure (`git reset --soft HEAD~1`), a failing replay would silently drop that commit while the rebase still reports success. The hook MUST exit immediately (skipping the suite) when `rebase-merge`, `rebase-apply`, `MERGE_HEAD`, or `CHERRY_PICK_HEAD` exists under the git dir. This is what makes `make push`'s `git pull --rebase` safe.
2. Verifies the runner and test framework are available, printing a clear, actionable error if not.
3. Runs the full test suite via the project's test command (e.g. `make test` / `uv run pytest`).
4. On failure, reverts the commit with `git reset --soft HEAD~1`, keeping the changes staged for investigation.

```python
# .githooks/post-commit.py (sketch)
import subprocess
import sys
from pathlib import Path


def _in_progress_git_operation() -> bool:
    """True during rebase/merge/cherry-pick, when the suite must NOT run."""
    git_dir = Path(
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    markers = ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD")
    return any((git_dir / marker).exists() for marker in markers)


def main() -> None:
    # Guard: skip during automated git operations (rebase/merge/cherry-pick).
    if _in_progress_git_operation():
        return
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
