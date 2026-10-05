# Slice: LLM API Key via `.teddy/.env` + Interactive Preflight Setup

- **Status:** In Progress
- **Milestone:** N/A (ad-hoc task; source: [00-27-llm-api-key-configuration.md](/docs/project/tasks/00-27-llm-api-key-configuration.md))
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:** [yaml_config_adapter.md](/docs/architecture/adapters/outbound/yaml_config_adapter.md), [config_service.md](/docs/architecture/core/ports/outbound/config_service.md)
- **Scope Slug:** `llm-api-key-configuration`

## Business Goal

Let users configure the required LLM API key through a gitignored `.teddy/.env`
file (referenced from `config.yaml` via `${VAR}` interpolation) and be guided
through an editor-style interactive prompt on first run, so a fresh project
"just works" without hand-editing YAML — while a pipeline/non-TTY run keeps a
hard error whose message points at the env file. The key must become live within
the SAME run that sets it, and must never leak into `EXECUTE` child shells.

## Scenarios

> As a developer with a fresh TeDDy project and no LLM API key configured, I want to be prompted for the key on first run so that I can start a session without hand-editing YAML.

```gherkin
Given a fresh project whose .teddy/config.yaml references llm.api_key: "${TEDDY_LLM_API_KEY}"
And no key is present in .teddy/.env or the shell environment
And the command runs on an interactive terminal (stdin is a TTY, not --pipeline)
When I run teddy start
Then the preflight prompts for the LLM API key (all output on stderr)
And my entered key is persisted to .teddy/.env as TEDDY_LLM_API_KEY
And the session proceeds with a valid configuration
```

> As a CI/pipeline operator, I want a clear hard error that points at the env file so that I know how to configure the key non-interactively.

```gherkin
Given a fresh project with no LLM API key and no .teddy/.env
And the run is non-interactive (--pipeline or non-TTY stdin)
When I run teddy start --pipeline -m "do the thing"
Then the preflight hard-errors on the empty key
And the error message points at .teddy/.env / TEDDY_LLM_API_KEY
```

> As a user who keeps secrets out of YAML, I want config.yaml to reference the env var so that my key lives only in the gitignored env file.

```gherkin
Given .teddy/.env contains TEDDY_LLM_API_KEY=sk-abc123
And .teddy/config.yaml has llm.api_key: "${TEDDY_LLM_API_KEY}"
When TeDDy resolves llm.api_key
Then it uses "sk-abc123" from .teddy/.env
And a literal llm.api_key value in config.yaml still wins over interpolation
```

## Edge Cases

- **Shell env precedence**: If `TEDDY_LLM_API_KEY` is set in the shell env, then the shell value wins over the `.env` file value, because the shell is the more specific override.
- **`${VAR:-default}` fallback**: If a token carries a `:-default`, then the default is substituted when the var is unresolved, because token authors need a fallback.
- **Unresolved var**: If a `${VAR}` token resolves to nothing, then it becomes an empty string, because the key must be treated as missing and trigger the prompt/error path.
- **`$$` escape**: If a value contains `$$`, then it renders as a literal `$`, because literal dollar signs must remain expressible.
- **Plain string untouched**: If a config value has no `${`, then it is returned verbatim, because interpolation must never mangle non-interpolated values.
- **`os.environ` non-mutation**: If `set_env_variable` persists a key, then `os.environ` is unchanged, because a leaked key would propagate into every `EXECUTE` child shell.
- **Same-run liveness**: If the prompt persists a key, then the same run's validation sees it, because `IConfigService` is transient and a stale per-instance cache must not block the session.
- **Empty/EOF input**: If the user supplies empty input or presses Ctrl-D at the prompt, then no key is persisted and the downstream validation error surfaces, because we must never persist an empty secret.
- **Explicit-but-empty config value**: If `config.yaml` carries an explicit empty `llm.api_key`, then persisting the key also writes `llm.api_key: "${TEDDY_LLM_API_KEY}"`, because the explicit empty value would otherwise override the interpolation.
- **Init scaffolding**: If `teddy init` runs with `.env` missing, then a commented `.env` placeholder is scaffolded, because the user needs a file to paste the key into.
- **One-shot execute**: If `handle_plan_generation` runs, then the interactive prompt is skipped (`setup_api_key=False`), because a one-shot plan generation is not an interactive session.

## Key Unknowns

- [x] [Functional] Should the API-key gate be wider than the editor gate? – Resolution: YES. The key is REQUIRED (unlike the optional editor), so `-y -m` on a TTY must still prompt; the gate is `system_env.isatty() and not pipeline` (no `interactive`/`-m` clause).
- [x] [Technical] Interpolate at load time or `get_setting` time? – Resolution: LAZILY at `get_setting` time, reading `.env` FRESH on each interpolating call. This makes the value live across the transient `IConfigService` instances (registered `punq.Scope.transient`) with no explicit refresh call.
- [x] [Technical] Is `YamlConfigAdapter` the sole concrete `IConfigService`? – Resolution: YES (Turn 3 grep). Adding an abstract member is safe as long as it is implemented in the SAME commit; no consumer migration is needed.
- [x] [Technical] Must the harness `IConfigService` double implement `set_env_variable`? – Resolution: NO. `register_mock` builds `POSIXPathMock(spec=IConfigService)`, which auto-exposes new protocol members; `tests/harness/setup/mocks.py` holds no hand-rolled fake. Brief Step 7 is a no-op.
- [x] [Functional] Does `validate_config()` change? – Resolution: the emptiness CHECK is UNCHANGED; the empty-key MESSAGE gains an appended hint pointing at `.teddy/.env` / `TEDDY_LLM_API_KEY` (brief bullet #4 + Verification #5 require the user-visible message; bullet #5's "unchanged" is read as logic-only). `match=`/substring assertions stay green.
- [x] [Technical] Does adding `".env"` to `InitService._init_config_dir`'s `config_files` break the init tests? – Resolution: YES. `tests/suites/unit/core/services/test_init_service.py` asserts literal counts; they MUST be updated to `4` in the same scaffolding deliverable.
- [x] [Technical] Is `resources/config/.env` packaged in the wheel? – Resolution: LIKELY YES by inspection (hatch `include = ["src/teddy_executor"]` ships the whole tree, and the sibling `resources/config/.gitignore` dotfile already ships). Confirm empirically via `uv build` in Delivery.
- [x] [Technical] Does interpolation break existing adapter tests? – Resolution: NO. Interpolation only fires when a value contains `${`; the existing fixtures use literal keys and are untouched.
- [x] [Technical] Does the repo's root `.gitignore` exclude the new `resources/config/.env`? – Resolution: TO VERIFY at Implementation (the file must be tracked/allowlisted so the scaffold ships). Flagged as a build risk.
- [x] [Technical] Can a literal `${...}` string masquerade as a valid key? – Resolution: YES if `config.yaml` is migrated BEFORE interpolation exists. Ordering constraint: the interpolation Logic deliverable MUST land BEFORE the `config.yaml` Migration deliverable.

## Implementation Plan

The feature threads one value (the LLM API key) through five seams, each an
atomic, Green-to-Green transition:

1. **Resolution** (`YamlConfigAdapter`): `get_setting` lazily interpolates
   `${VAR}` tokens against a merged env (`dotenv_values('.teddy/.env')` layered
   UNDER `os.environ`). Reading `.env` fresh on every interpolating call makes the
   value live across transient instances with no refresh call — this resolves the
   eager-cache wrinkle called out in the brief.
2. **Persistence** (`IConfigService.set_env_variable` → `dotenv.set_key`): writes
   `.teddy/.env` WITHOUT mutating `os.environ`, so the key cannot leak into
   `EXECUTE` child shells.
3. **Scaffolding** (`InitService`): `teddy init` seeds a commented `.env`
   placeholder.
4. **Gate** (`_run_cli_preflight_check`): a TTY-gated prompt fires when the key
   is missing and `setup_api_key` is truthy; `ILlmClient` is resolved AFTER the
   prompt so its transient config instance reads the post-persist state.
5. **Threading** (`__main__.py`): `_resolve_setup_api_key(system_env, pipeline)`
   is computed at the CLI boundary and passed into the handlers.

**Ordering constraints (Green-to-Green):**

- The interpolation **Logic** deliverable MUST land BEFORE the `config.yaml`
  **Migration**, otherwise the literal `"${TEDDY_LLM_API_KEY}"` string would be
  read as a present key, masking the missing-key path.
- The persistence **Contract** deliverable MUST land before its consumer (the
  gate **Seam**).
- The gate **Seam** is additive and inert (`setup_api_key` defaults to `None` →
  skip), preserving the Shared-Seam evolution discipline established by Slice
  00-26 (`setup_editor`); the **Wiring** deliverable flips it end-to-end and
  carries the behavioral tests (Tracer Bullet).

**Test strategy:** adapter-level Unit tests drive the interpolation rule matrix
and `set_env_variable` non-mutation + cross-instance liveness with REAL adapters
over `tmp_path`; the preflight gate/prompt is driven in Unit via the harness
doubles; one Acceptance test proves the Tracer Bullet (TTY + missing key →
prompt fires → key persisted).

## Deliverables

- [x] **Contract** - Add `set_env_variable(self, name: str, value: str) -> None` to `IConfigService` (docstring: persist a secret to the `.env` file in the config directory, without touching `os.environ`) and implement it in `YamlConfigAdapter` via a new `_env_file_path()` helper (`os.path.join(os.path.dirname(self._config_path), ".env")`) + `os.makedirs(..., exist_ok=True)` + `dotenv.set_key(self._env_file_path(), name, value, quote_mode="always")`. Additive; `YamlConfigAdapter` is the sole concrete subclass, so the ABC stays instantiable. Unit test: the key lands in `.env` and `os.environ` is unchanged.
- [ ] **Logic** - Add `${VAR}` interpolation to `YamlConfigAdapter`: `_build_interpolation_env()` (start from `dotenv_values(self._env_file_path())` dropping `None`s, then `.update(os.environ)` so the real shell env wins; read `.env` FRESH every call), `_interpolate()` (regex `\$\{([_A-Za-z][_A-Za-z0-9]*)(?::-([^}]*))?\}`, unresolved → `""`, `$$` → literal `$`; return unchanged when no `${`), and `_maybe_interpolate()` (only when `isinstance(value, str) and "${" in value`). Apply in BOTH the exact-match and `_resolve_nested` paths of `get_setting`. Unit tests: the interpolation rule matrix + a cross-instance liveness test (a SECOND real adapter resolves a key written by `set_env_variable`).
- [ ] **Migration** - Point the bundled `config.yaml` `llm.api_key` at `"${TEDDY_LLM_API_KEY}"` and refresh the adjacent comment (interpolated from `.teddy/.env`/shell; a literal value still wins). MUST follow the interpolation Logic deliverable. Verify no suite asserts the bundled `api_key` literal.
- [ ] **Migration** - Scaffold `.teddy/.env`: CREATE `src/teddy_executor/resources/config/.env` (commented placeholder, obviously-fake to avoid a `detect-secrets` false positive) and add `".env"` to `InitService._init_config_dir`'s `config_files`; update the literal `3`→`4` count assertions in `tests/suites/unit/core/services/test_init_service.py`. Unit test for `teddy init config` scaffolding the file.
- [ ] **Migration** - Append a `.teddy/.env` / `TEDDY_LLM_API_KEY` hint to the empty-key message in `LiteLLMAdapter.validate_config` (the emptiness CHECK is unchanged). Reconcile any message-asserting test (the `match="'llm.api_key' is empty"` substring in `test_litellm_adapter_retries.py` stays green).
- [ ] **Seam** - Additive seam in `_run_cli_preflight_check`: add `setup_api_key: Optional[bool] = None`; resolve `config_service = container.resolve(IConfigService)` at the top and run `if setup_api_key and _is_llm_api_key_missing(config_service): _prompt_for_api_key(config_service)`; MOVE `llm_client = container.resolve(ILlmClient)` to AFTER the gate. Add module-level `_is_llm_api_key_missing(config_service)` (`not (isinstance(k, str) and k.strip())`) and `_prompt_for_api_key(config_service)` (yellow stderr warning; `typer.prompt("LLM API key", hide_input=True)`; persist via `set_env_variable` + `set_setting("llm.api_key", "${TEDDY_LLM_API_KEY}")`; green confirmation; EOF/empty → return). Inert by default (`None` → skip). Unit tests: gate skip/run + prompt persist/EOF.
- [ ] **Wiring** - Thread the signal end-to-end (Tracer Bullet): add `setup_api_key: Optional[bool] = None` to `handle_new_session`/`handle_resume_session` (appended LAST, so no positional caller shifts) and forward `setup_api_key=setup_api_key` into `_run_cli_preflight_check(...)`; `handle_plan_generation` passes `setup_api_key=False`. In `__main__.py` add `_resolve_setup_api_key(system_env, pipeline) -> bool` returning `system_env.isatty() and not pipeline` (NO `interactive`/`-m` clause), compute it in `start`/`resume`, and pass it. Bundle behavioral tests: one Acceptance test (`start -y -m` on a TTY with a missing key → prompt fires → key persisted) + Unit skips (falsy `setup_api_key`).
- [ ] **Logic** - Cover the gate unit's edge-case table: `_is_llm_api_key_missing` (`None`/`""`/whitespace → missing; a real key → present) and `_prompt_for_api_key` (non-empty → both persists + confirmation; empty and EOF → no persist). Pin every permutation independently of the higher-layer behavioral tests.
- [ ] **Cleanup** - Update the component docs: `docs/architecture/adapters/outbound/yaml_config_adapter.md` (record `${VAR}` / `${VAR:-default}` / `$$` interpolation, fresh-read `.env` layering with shell-env precedence, `set_env_variable`, and the "`os.environ` is never mutated" guarantee) and `docs/architecture/core/ports/outbound/config_service.md` (record the new `set_env_variable` member). Set/refresh their status.

## Implementation Notes

### D1 — Contract: `set_env_variable` on `IConfigService` + `YamlConfigAdapter`

- Added `set_env_variable(self, name: str, value: str) -> None` as an `@abstractmethod` on `IConfigService` (mirrors the existing `set_setting` contract shape and documents the `os.environ` non-mutation guarantee in its docstring).
- Implemented it on `YamlConfigAdapter` via a new `_env_file_path()` helper (`os.path.join(os.path.dirname(self._config_path), ".env")`), a parent-dir guard (`if parent_dir: os.makedirs(parent_dir, exist_ok=True)` — the same idiom `set_setting` already uses, avoiding `os.makedirs("")` on a bare `config_path`), and `dotenv.set_key(env_path, name, value, quote_mode="always")`.
- `quote_mode="always"` was chosen deliberately: secrets are always quoted in the `.env` file, keeping it robust against values containing spaces or shell-metacharacters.
- The write uses `dotenv.set_key` (never `load_dotenv`), so `os.environ` is never mutated. This is the mechanism that keeps the key out of the child shells that `EXECUTE` actions spawn inside the user's repo — TeDDy is a guest in that repo.
- **Green-to-Green**: Orientation (Turn 3) proved `YamlConfigAdapter` is the SOLE concrete `IConfigService` subclass, so adding the abstract member AND its implementation in the SAME change kept the ABC instantiable with no consumer migration. The auto-specced harness doubles (`POSIXPathMock(spec=IConfigService)` via `register_mock`) inherit the new member automatically, so brief Step 7 required no harness edit.
- New Unit test: `tests/suites/unit/adapters/outbound/test_yaml_config_adapter_env_persistence.py` drives a REAL adapter over `tmp_path` and asserts both persistence to `.teddy/.env` and non-mutation of `os.environ`.
- Integration gate: the FULL suite ran green (`1587 passed, 5 skipped`) — the breaking port addition regressed no existing consumer or harness double.

## Verification

1. `uv run pytest tests/suites/unit/adapters/outbound/test_yaml_config_adapter_interpolation.py -q` → `${VAR}` resolves from `.env`; shell env wins; `${VAR:-default}` falls back; unresolved → `""`; `$$` → literal `$`; plain strings untouched.
2. `uv run pytest tests/suites/unit/adapters/outbound/test_yaml_config_adapter.py tests/suites/unit/adapters/outbound/test_yaml_config_adapter_layering.py tests/suites/unit/adapters/outbound/test_yaml_config_adapter_preserves_comments.py -q` → existing adapter suites still pass.
3. `set_env_variable` writes `.teddy/.env` AND `os.environ` is unchanged; a SECOND real adapter resolves `get_setting("llm.api_key")` from the freshly-written `.env`.
4. `uv run pytest tests/suites/unit/adapters/inbound/test_session_preflight_wiring.py -q` → the prompt fires when the key is missing and `setup_api_key=True`; skipped when `setup_api_key=False`; after a simulated prompt+persist, the SAME-run resolution yields a non-empty key.
5. Manual smoke: on a fresh project, `teddy start` (TTY) prompts → key lands in `.teddy/.env` (`cat .teddy/.env`); `teddy start -y -m "hi"` on a TTY also prompts; `teddy start --pipeline -m "hi"` (and any piped/non-TTY run) hard-errors with a message pointing at `.teddy/.env` / `TEDDY_LLM_API_KEY`.
6. Isolation regression: an `EXECUTE` child shell does NOT see `TEDDY_LLM_API_KEY` (assert the process env is unchanged after a persist).
7. `teddy init config` (and a clean `teddy init`) creates `.teddy/.env`; confirm the bundled `resources/config/.env` ships in the wheel (`uv build` and inspect the artifact); if the dotfile is excluded or gitignored by the repo, embed the placeholder as a string constant in `init_service` instead.
8. Full suite green: `uv run pytest`.
