# Task: LLM API Key via `.teddy/.env` + Interactive Preflight Setup

## Business Goal
Let users configure the LLM API key through a gitignored `.teddy/.env` file (referenced from `config.yaml` via `${VAR}` interpolation) and be guided through an editor-style interactive prompt on first run, so a fresh project "just works" without hand-editing YAML.

## Context

Today the LLM API key lives only in `.teddy/config.yaml` (`llm.api_key`), which ships as `api_key: ""`. Validation in `LiteLLMAdapter.validate_config()` hard-fails with `'llm.api_key' is empty.` whenever the resolved value is empty (`src/teddy_executor/adapters/outbound/litellm_adapter.py`, ~line 356). There is no `.env` support, and no interactive way to set the key.

The editor flow (Slice 03-01) is the UX template: a TTY-gated, interactive prompt inside the CLI preflight (`_run_cli_preflight_check` in `session_cli_handlers.py`) that validates, persists, and prints a green confirmation, with all output on stderr.

### Approved design (locked)
1. `.teddy/.env` holds `TEDDY_LLM_API_KEY` (gitignored via `.teddy/.gitignore` = `*`; scaffolded as a commented placeholder by `teddy init`).
2. `config.yaml` ships `api_key: "${TEDDY_LLM_API_KEY}"` — explicit `${VAR}` interpolation (Docker-Compose syntax), value-only. A literal value still wins.
3. Interactive preflight prompt, **TTY-gated by `isatty() and not pipeline`** → persist → green confirmation on stderr.
4. `--pipeline` / non-TTY → keep the current hard error, but point the message at `.teddy/.env` / `TEDDY_LLM_API_KEY`.
5. `validate_config()` is left **UNCHANGED** — interpolation yields a non-empty value at `get_setting("llm.api_key")` time.

Note the API-key gate is deliberately **wider** than the editor gate: the editor is optional, so its gate also excludes `-y -m`; the API key is **required**, so `-y -m` on a TTY still prompts. `--pipeline` remains the clean automation path (it hard-errors by design).

### The wrinkle (must be handled)
`YamlConfigAdapter.__init__` eagerly loads and **caches** the merged config. After the prompt persists the key to `.env`, the key must be live **for the same run**. Compounding this, `IConfigService` is registered **transient** (`registries/infrastructure.py:125`), so `ILlmClient` holds a *different* `YamlConfigAdapter` instance than the preflight — each with its own `_config` cache.

**Resolution:**
- Interpolate **lazily at `get_setting` time** (NOT at load time), reading `.env` **fresh** on each interpolation (only when a `${...}` token is present). This makes the value live across instances with no explicit refresh call, because every instance re-reads `.env` when it needs a value.
- In the preflight, resolve `ILlmClient` **after** the prompt/persist step, so its config-service instance reads the already-updated on-disk state.
- Use `dotenv_values()` (returns a dict) merged with `os.environ` and **never `load_dotenv()`** — so `os.environ` is never mutated and the key **cannot leak into `EXECUTE` child shells** (TeDDy is a guest in the user's repo and every `EXECUTE` spawns children that inherit the process environment). `set_env_variable` writes the file via `dotenv.set_key` (also non-mutating).

## Implementation Steps

### Step 1: Add `${VAR}` interpolation + env persistence to `YamlConfigAdapter`
- **File:** [src/teddy_executor/adapters/outbound/yaml_config_adapter.py](/src/teddy_executor/adapters/outbound/yaml_config_adapter.py)
- **Change:**
  - Add module import: `from dotenv import dotenv_values, set_key` (`python-dotenv` is already a direct dependency in `pyproject.toml`).
  - Add `_env_file_path(self) -> str`: `os.path.join(os.path.dirname(self._config_path), ".env")`.
  - Add `_build_interpolation_env(self) -> dict[str, str]`: start from `dotenv_values(self._env_file_path())` (drop `None` values), then `.update(os.environ)` so **real shell env wins** over the `.env` file. Read `.env` **fresh on every call** (no caching) — this is what resolves the wrinkle.
  - Add `_interpolate(self, text: str) -> str`: regex `\$\{([_A-Za-z][_A-Za-z0-9]*)(?::-([^}]*))?\}`; for each match substitute the env value, else the `${VAR:-default}` default, else `""` if unresolved. Support a `$$` → literal `$` escape. Return the text unchanged when no `${` is present.
  - Add `_maybe_interpolate(self, value) -> Any`: only interpolate when `isinstance(value, str) and "${" in value`; otherwise return `value` untouched (so plain strings, numbers, and dicts are never mangled).
  - Apply `_maybe_interpolate` to the value returned by `get_setting` in **both** the exact-match path and the `_resolve_nested` path.
  - Add `set_env_variable(self, name: str, value: str) -> None`: `os.makedirs(os.path.dirname(self._env_file_path()), exist_ok=True)` then `set_key(self._env_file_path(), name, value, quote_mode="always")`. Do **not** touch `os.environ`.

### Step 2: Extend the `IConfigService` port with `set_env_variable`
- **File:** [src/teddy_executor/core/ports/outbound/config_service.py](/src/teddy_executor/core/ports/outbound/config_service.py)
- **Change:** Add an abstract method `set_env_variable(self, name: str, value: str) -> None` documented as persisting a secret to the `.env` file inside the config directory (mirrors the existing `set_setting` contract). This is a **breaking addition to the protocol** — every implementation and `spec=IConfigService` test double must implement it (see Step 7).

### Step 3: Point the bundled default `config.yaml` at the env var
- **File:** [src/teddy_executor/resources/config/config.yaml](/src/teddy_executor/resources/config/config.yaml)
- **Change:** Replace `api_key: ""` with `api_key: "${TEDDY_LLM_API_KEY}"` and update the adjacent comment to explain that the value is interpolated from `.teddy/.env` / the shell environment, and that a literal key still works.

### Step 4: Scaffold `.teddy/.env` in `init`
- **File:** [src/teddy_executor/resources/config/.env](/src/teddy_executor/resources/config/.env) (new)
- **Change:** Create a commented placeholder; keep it obviously-fake/commented to avoid the known `detect-secrets` false positive. Suggested content:

  ```text
  # TeDDy secrets. This directory is gitignored (.teddy/.gitignore ignores *).
  # Referenced from config.yaml:  llm.api_key: "${TEDDY_LLM_API_KEY}"
  # Paste your OpenRouter (or other provider) key below, then save.
  # TEDDY_LLM_API_KEY=
  ```

- **File:** [src/teddy_executor/core/services/init_service.py](/src/teddy_executor/core/services/init_service.py)
- **Change:** Add `".env"` to the `config_files` list in `_init_config_dir` so `teddy init` and `teddy init config` scaffold/refresh `.teddy/.env`.

### Step 5: Interactive prompt + gate in the preflight
- **File:** [src/teddy_executor/adapters/inbound/session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py)
- **Change:**
  - Add a `setup_api_key: Optional[bool] = None` parameter to `_run_cli_preflight_check` (mirroring `setup_editor`).
  - At the top of the function, resolve `config_service = container.resolve(IConfigService)`; if `setup_api_key and _is_llm_api_key_missing(config_service)`, call `_prompt_for_api_key(config_service)`.
  - **Move** `llm_client = container.resolve(ILlmClient)` to **after** the gate, so its transient config-service instance reads the post-persist on-disk state.
  - Add module-level helpers:
    - `_is_llm_api_key_missing(config_service) -> bool`: `api_key = config_service.get_setting("llm.api_key"); return not (isinstance(api_key, str) and api_key.strip())`.
    - `_prompt_for_api_key(config_service) -> None`: yellow stderr warning; prompt with `typer.prompt("LLM API key", hide_input=True)` following the stderr conventions used by `_prompt_for_editor_selection`; on non-empty input call `config_service.set_env_variable("TEDDY_LLM_API_KEY", value)` **and** `config_service.set_setting("llm.api_key", "${TEDDY_LLM_API_KEY}")` (migrates an explicit-but-empty config value to the interpolation form), then print the green `LLM API key saved to .teddy/.env.` confirmation; on EOF/empty input return without raising (the downstream validation error surfaces, now pointing at `.env`).
  - Thread `setup_api_key` through `handle_new_session` and `handle_resume_session` (signature + the `_run_cli_preflight_check(...)` call). In `handle_plan_generation` (the `execute` flow), pass `setup_api_key=False`.

### Step 6: Thread the gate from the CLI boundary
- **File:** [src/teddy_executor/__main__.py](/src/teddy_executor/__main__.py)
- **Change:** Add `_resolve_setup_api_key(system_env, pipeline) -> bool` returning `system_env.isatty() and not pipeline`. Compute it in the `start` and `resume` commands (mirroring the `_resolve_setup_editor(...)` call sites) and pass `setup_api_key=` into the handlers. Do **not** add an `interactive`/`-m` clause — the API key is required, unlike the optional editor.

### Step 7: Update test doubles implementing `IConfigService`
- **File:** [tests/harness/setup/test_environment.py](/tests/harness/setup/test_environment.py) and any other `spec=IConfigService` double (search the harness).
- **Change:** Add `set_env_variable` so the fakes remain spec-compliant with the extended port.

### Step 8: Update the component docs
- **File:** [docs/architecture/adapters/outbound/yaml_config_adapter.md](/docs/architecture/adapters/outbound/yaml_config_adapter.md)
- **File:** [docs/architecture/core/ports/outbound/config_service.md](/docs/architecture/core/ports/outbound/config_service.md)
- **Change:** Document `${VAR}` interpolation (value-only, `${VAR}` / `${VAR:-default}` / `$$`), fresh-read `.env` layering with shell-env precedence, `set_env_variable`, and the guarantee that `os.environ` is never mutated.

## Verification

1. New unit test `tests/suites/unit/adapters/outbound/test_yaml_config_adapter_interpolation.py`: `${VAR}` resolves from `.env`; shell env wins over `.env` for the same name; `${VAR:-default}` falls back; an unresolved var yields `""`; `$$` yields a literal `$`; plain strings are untouched.
2. Existing adapter suites still pass: `uv run pytest tests/suites/unit/adapters/outbound/test_yaml_config_adapter.py tests/suites/unit/adapters/outbound/test_yaml_config_adapter_layering.py tests/suites/unit/adapters/outbound/test_yaml_config_adapter_preserves_comments.py -q`.
3. New unit test: `set_env_variable` writes `.teddy/.env` **and** `os.environ` is unchanged; a SECOND adapter instance resolves `get_setting("llm.api_key")` from the freshly-written `.env` (proves the same-run / cross-instance liveness that resolves the wrinkle).
4. Extend `tests/suites/unit/adapters/inbound/test_session_preflight_wiring.py`: the prompt fires when the key is missing and `setup_api_key=True`; it is skipped when `setup_api_key=False`; and after a simulated prompt+persist, `llm_client.validate_config(include_remote=False)` returns no errors in the SAME run.
5. Manual smoke on a fresh project: `teddy start` (TTY) prompts → key lands in `.teddy/.env` (`cat .teddy/.env`); `teddy start -y -m "hi"` on a TTY also prompts; `teddy start --pipeline -m "hi"` (and any piped/non-TTY run) hard-errors with a message pointing at `.teddy/.env` / `TEDDY_LLM_API_KEY`.
6. Isolation regression: an `EXECUTE` child shell does NOT see `TEDDY_LLM_API_KEY` (assert the env is unchanged).
7. `teddy init config` (and a clean `teddy init`) creates `.teddy/.env`. Confirm the bundled `resources/config/.env` is packaged in the wheel (`uv build` and inspect the artifact); if the dotfile is excluded, embed the placeholder as a string constant in `init_service` instead.
8. Full suite green: `uv run pytest` (the post-commit hook enforces this; never bypass it).
