# RCA: Mypy Pre-commit Hook - Library Stub Not Installed

## 1. Summary
The Developer agent entered a `🔴 Red` state due to a persistent pre-commit failure. The `mypy` hook repeatedly failed with the error `error: Library stubs not installed for "yaml"`, even after `types-PyYAML` was correctly added to the project's development dependencies in `pyproject.toml`.

## 2. Investigation
The investigation focused on the configuration of the pre-commit framework itself.

*   **Hypothesis 1 (Confirmed):** The `mypy` hook in `.pre-commit-config.yaml` was missing `types-PyYAML` in its `additional_dependencies` list.
    *   **Verification:** A spike was created (`spikes/debug/01-verify-mypy-fix/`) with a corrected `.pre-commit-config.yaml`. Running the hook against this isolated configuration resulted in a `Passed` status, confirming the hypothesis.

## 3. Root Cause
The root cause was a misunderstanding of how the `pre-commit` framework operates. By default, `pre-commit` creates a separate, isolated virtual environment for each hook to ensure reliability. It does **not** use the project's main Poetry environment. Therefore, any dependencies required by a hook (especially type stubs for `mypy`) must be explicitly declared within the hook's configuration in `.pre-commit-config.yaml` using the `additional_dependencies` key. The project's `pyproject.toml` dependencies are not visible to the hook's environment.

## 4. Recommended Action
The `.pre-commit-config.yaml` file must be modified to include `additional_dependencies: ["types-PyYAML"]` under the `mypy` hook definition.
