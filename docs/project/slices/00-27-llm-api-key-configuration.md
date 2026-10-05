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
- [x] **Logic** - Add `${VAR}` interpolation to `YamlConfigAdapter`: `_build_interpolation_env()` (start from `dotenv_values(self._env_file_path())` dropping `None`s, then `.update(os.environ)` so the real shell env wins; read `.env` FRESH every call), `_interpolate()` (regex `\$\{([_A-Za-z][_A-Za-z0-9]*)(?::-([^}]*))?\}`, unresolved → `""`, `$$` → literal `$`; return unchanged when no `${`), and `_maybe_interpolate()` (only when `isinstance(value, str) and "${" in value`). Apply in BOTH the exact-match and `_resolve_nested` paths of `get_setting`. Unit tests: the interpolation rule matrix + a cross-instance liveness test (a SECOND real adapter resolves a key written by `set_env_variable`).
- [x] **Migration** - Point the bundled `config.yaml` `llm.api_key` at `"${TEDDY_LLM_API_KEY}"` and refresh the adjacent comment (interpolated from `.teddy/.env`/shell; a literal value still wins). MUST follow the interpolation Logic deliverable. Verify no suite asserts the bundled `api_key` literal.
- [x] **Migration** - Scaffold `.teddy/.env`: CREATE `src/teddy_executor/resources/config/.env` (commented placeholder, obviously-fake to avoid a `detect-secrets` false positive) and add `".env"` to `InitService._init_config_dir`'s `config_files`; update the literal `3`→`4` count assertions in `tests/suites/unit/core/services/test_init_service.py`. Unit test for `teddy init config` scaffolding the file.
- [x] **Migration** - Append a `.teddy/.env` / `TEDDY_LLM_API_KEY` hint to the empty-key message in `LiteLLMAdapter.validate_config` (the emptiness CHECK is unchanged). Reconcile any message-asserting test (the `match="'llm.api_key' is empty"` substring in `test_litellm_adapter_retries.py` stays green).
- [x] **Seam** - Additive seam in `_run_cli_preflight_check`: add `setup_api_key: Optional[bool] = None`; resolve `config_service = container.resolve(IConfigService)` at the top and run `if setup_api_key and _is_llm_api_key_missing(config_service): _prompt_for_api_key(config_service)`; MOVE `llm_client = container.resolve(ILlmClient)` to AFTER the gate. Add module-level `_is_llm_api_key_missing(config_service)` (`not (isinstance(k, str) and k.strip())`) and `_prompt_for_api_key(config_service)` (yellow stderr warning; `typer.prompt("LLM API key", hide_input=True)`; persist via `set_env_variable` + `set_setting("llm.api_key", "${TEDDY_LLM_API_KEY}")`; green confirmation; EOF/empty → return). Inert by default (`None` → skip). Unit tests: gate skip/run + prompt persist/EOF.
- [x] **Wiring** - Thread the signal end-to-end (Tracer Bullet): add `setup_api_key: Optional[bool] = None` to `handle_new_session`/`handle_resume_session` (appended LAST, so no positional caller shifts) and forward `setup_api_key=setup_api_key` into `_run_cli_preflight_check(...)`; `handle_plan_generation` passes `setup_api_key=False`. In `__main__.py` add `_resolve_setup_api_key(system_env, pipeline) -> bool` returning `system_env.isatty() and not pipeline` (NO `interactive`/`-m` clause), compute it in `start`/`resume`, and pass it. Bundle behavioral tests: one Acceptance test (`start -y -m` on a TTY with a missing key → prompt fires → key persisted) + Unit skips (falsy `setup_api_key`).
- [x] **Logic** - Cover the gate unit's edge-case table: `_is_llm_api_key_missing` (`None`/`""`/whitespace → missing; a real key → present) and `_prompt_for_api_key` (non-empty → both persists + confirmation; empty and EOF → no persist). Pin every permutation independently of the higher-layer behavioral tests.
- [x] **Cleanup** - Update the component docs: `docs/architecture/adapters/outbound/yaml_config_adapter.md` (record `${VAR}` / `${VAR:-default}` / `$$` interpolation, fresh-read `.env` layering with shell-env precedence, `set_env_variable`, and the "`os.environ` is never mutated" guarantee) and `docs/architecture/core/ports/outbound/config_service.md` (record the new `set_env_variable` member). Set/refresh their status.

## Implementation Notes

### D1 — Contract: `set_env_variable` on `IConfigService` + `YamlConfigAdapter`

- Added `set_env_variable(self, name: str, value: str) -> None` as an `@abstractmethod` on `IConfigService` (mirrors the existing `set_setting` contract shape and documents the `os.environ` non-mutation guarantee in its docstring).
- Implemented it on `YamlConfigAdapter` via a new `_env_file_path()` helper (`os.path.join(os.path.dirname(self._config_path), ".env")`), a parent-dir guard (`if parent_dir: os.makedirs(parent_dir, exist_ok=True)` — the same idiom `set_setting` already uses, avoiding `os.makedirs("")` on a bare `config_path`), and `dotenv.set_key(env_path, name, value, quote_mode="always")`.
- `quote_mode="always"` was chosen deliberately: secrets are always quoted in the `.env` file, keeping it robust against values containing spaces or shell-metacharacters.
- The write uses `dotenv.set_key` (never `load_dotenv`), so `os.environ` is never mutated. This is the mechanism that keeps the key out of the child shells that `EXECUTE` actions spawn inside the user's repo — TeDDy is a guest in that repo.
- **Green-to-Green**: Orientation (Turn 3) proved `YamlConfigAdapter` is the SOLE concrete `IConfigService` subclass, so adding the abstract member AND its implementation in the SAME change kept the ABC instantiable with no consumer migration. The auto-specced harness doubles (`POSIXPathMock(spec=IConfigService)` via `register_mock`) inherit the new member automatically, so brief Step 7 required no harness edit.
- New Unit test: `tests/suites/unit/adapters/outbound/test_yaml_config_adapter_env_persistence.py` drives a REAL adapter over `tmp_path` and asserts both persistence to `.teddy/.env` and non-mutation of `os.environ`.
- Integration gate: the FULL suite ran green (`1587 passed, 5 skipped`) — the breaking port addition regressed no existing consumer or harness double.

### D2 — Logic: `${VAR}` interpolation in `YamlConfigAdapter`

- Added a module-level compiled pattern `_INTERPOLATION_PATTERN = re.compile(r"\$\$|\$\{([_A-Za-z][_A-Za-z0-9]*)(?::-([^}]*))?\}")`. The single alternation covers BOTH the `$$` escape and the `${VAR}` / `${VAR:-default}` token, so one `sub()` pass resolves escaping and substitution without a second scan.
- Added `_build_interpolation_env()`: starts from `dotenv_values(self._env_file_path())` (dropping `None` values), then `.update(os.environ)` so a real shell environment variable wins over the file. `.env` is read FRESH on every call (never cached) — this is the mechanism that keeps a key written mid-run live across the transient `IConfigService` instances (registered `punq.Scope.transient`) with no explicit refresh call.
- Added `_interpolate()`: fast-path returns the text unchanged when it contains no `${`; otherwise each token resolves to `$$` → a literal `$`, a resolved name → its value, and an unresolved name → its `${VAR:-default}` default or `""`.
- Added `_maybe_interpolate()`: only interpolates `str` values that actually contain `${`, so plain strings, numbers, and dicts are never mangled.
- Applied `_maybe_interpolate` in BOTH `get_setting` paths — the exact-match branch AND the `_resolve_nested` branch.
- New Unit test: `tests/suites/unit/adapters/outbound/test_yaml_config_adapter_interpolation.py` — 8 tests pinning the rule matrix (`.env` resolution; shell-env precedence; `${VAR:-default}` fallback; unresolved → `""`; `$$` escape; plain string untouched; the exact-match path; and cross-instance liveness via a SECOND adapter constructed BEFORE a `set_env_variable` write).
- The interpolation is **value-only** and applied lazily at `get_setting` time; a literal `config.yaml` value with no `${` is returned verbatim, so the change is fully backwards-compatible with the existing literal-key fixtures.
- Integration gate: the FULL suite ran green (`1595 passed, 5 skipped`) — the `get_setting` interpolation change regressed no existing consumer or harness double.
- **Ordering honored**: this Logic deliverable landed (implemented and integrated) BEFORE the `config.yaml` Migration (D3), so the literal `"${TEDDY_LLM_API_KEY}"` string can no longer masquerade as a present key once the default config is migrated.

### D3 — Migration: bundled `config.yaml` `llm.api_key` → `"${TEDDY_LLM_API_KEY}"`

- Migrated the bundled default `src/teddy_executor/resources/config/config.yaml` line 55 from the literal `api_key: ""` to `api_key: "${TEDDY_LLM_API_KEY}"`, and added an adjacent comment explaining that the value is interpolated from `.teddy/.env` / the shell environment and that a literal key still overrides.
- Added a migration-guard Unit test `test_baseline_llm_api_key_is_an_env_var_reference` to `tests/suites/unit/adapters/outbound/test_yaml_config_adapter_layering.py`, driving a REAL `YamlConfigAdapter` over `tmp_path` with `monkeypatch.setenv("TEDDY_LLM_API_KEY", ...)` (no mocks; a low-entropy fake value to avoid a detect-secrets false positive).
- This migration was only safe AFTER the D2 interpolation Logic landed (`7eb275cf`): without interpolation the literal `${...}` string would itself be truthy and mask the missing-key path.
- Green-to-Green: the bundled empty-literal `api_key` had NO test asserting it (every `llm.api_key` reader in the suite drives a mocked config — see the Turn 26 grep), so the value swap regressed no consumer.
- Integration gate: the FULL suite ran green (`1596 passed, 5 skipped`) — the baseline migration regressed no existing consumer or harness double.

### D4 — Migration: scaffold `.teddy/.env` in `init`

- Delivered the `.teddy/.env` scaffold as an EMBEDDED string constant (`_ENV_PLACEHOLDER` + `_EMBEDDED_DEFAULTS`) in `init_service.py` rather than a tracked `resources/config/.env` dotfile. This is an AS-BUILT DEVIATION from the task brief's Step 4, justified by the empirically-confirmed packaging hazard and authorized by the brief's own Verification #7 fallback.
- Root cause for the deviation: the bundled `resources/config/.gitignore` template (content `*`) makes git IGNORE any new dotfile dropped into that directory; the repo-root re-inclusion (`!/src/teddy_executor/resources/config/**`) is overridden by the deeper file per git precedence — `git check-ignore -v src/teddy_executor/resources/config/.env` matched `.gitignore:2:*`. A tracked dotfile would require a fragile `git add -f`.
- The embedded-constant approach is ALSO strictly more testable: a REAL `mock_fs` intercepts the resource read, so a dotfile-backed placeholder could not be asserted through the harness; the embedded map short-circuits `_get_default_content` BEFORE the filesystem is consulted.
- `_get_default_content` now checks `_EMBEDDED_DEFAULTS` first (falling through to the bundled config directory otherwise); `_init_config_dir`'s `config_files` grew to `["config.yaml", ".gitignore", "init.context", ".env"]`.
- Updated `test_init_service.py`'s literal count assertions `3` → `4` in lockstep (three summary strings plus two `write_file.call_count` assertions), keeping the pre-existing tests green-to-green.
- New Unit test `test_ensure_config_initialized_scaffolds_env_placeholder` asserts `.teddy/.env` is written and its content references `TEDDY_LLM_API_KEY`.
- The placeholder is fully commented; the `# TEDDY_LLM_API_KEY=` line carries a trailing `# pragma: allowlist secret` (OUTSIDE the string) so `Detect secrets` passes without polluting the written `.env` content. Verified via `pre-commit run --files src/teddy_executor/core/services/init_service.py` (all applicable hooks green).
- Integration gate: the FULL suite ran green (`1599 passed, 5 skipped`) — the scaffold change regressed no existing consumer.

### D5 — Migration: append the `.teddy/.env` / `TEDDY_LLM_API_KEY` hint to the empty-key message

- Extended `LiteLLMAdapter.validate_config`'s empty-key error message so a fresh project is told WHERE the key belongs; it now reads `"'llm.api_key' is empty. Set TEDDY_LLM_API_KEY in .teddy/.env (or your shell environment)."`
- The emptiness CHECK is UNCHANGED (brief design #5): `is_placeholder = isinstance(api_key, str) and api_key == ""` still gates the error; only the message STRING was extended.
- Preserved the LEADING `'llm.api_key' is empty` substring so `test_litellm_adapter_retries.py`'s `pytest.raises(ConfigurationError, match="'llm.api_key' is empty")` stays green (`re.search` needs only the substring, not the whole string).
- New Unit test `test_validate_config_empty_api_key_message_hints_at_dotenv` (in `test_litellm_adapter_preflight.py`) drives the REAL adapter through the shared `mock_config` harness and asserts the message names BOTH `TEDDY_LLM_API_KEY` and `.teddy/.env`.
- Integration gate: the FULL suite ran green (`1600 passed, 5 skipped`) — the message change regressed no consumer.

### D6 — Seam: additive `setup_api_key` gate in `_run_cli_preflight_check`

- Added `setup_api_key: Optional[bool] = None` to `_run_cli_preflight_check` (mirroring `setup_editor`); the gate `if setup_api_key and _is_llm_api_key_missing(config_service): _prompt_for_api_key(config_service)` runs BEFORE the `ILlmClient` resolve.
- **Moved** `llm_client = container.resolve(ILlmClient)` to AFTER the gate so the client's transient `IConfigService` instance reads the post-persist on-disk state (the same-run / cross-instance liveness guarantee proven by the interpolation tests).
- Added module-level `_is_llm_api_key_missing(config_service)` (`not (isinstance(api_key, str) and api_key.strip())`) and `_prompt_for_api_key(config_service)` (yellow stderr warning; `typer.prompt("LLM API key", hide_input=True)`; persists via `set_env_variable("TEDDY_LLM_API_KEY", value)` AND `set_setting("llm.api_key", "${TEDDY_LLM_API_KEY}")`; green `LLM API key saved to .teddy/.env.` confirmation; EOF/empty input returns WITHOUT raising so the downstream validation error surfaces with its own hint).
- The gate is ADDITIVE and INERT by default (`None` → skip), so every existing caller is unaffected (brief design #5's append-only seam).
- New Unit test `test_preflight_check_gates_api_key_prompt_on_setup_api_key_flag` (parametrized `[True, False]`) drives the REAL gate through the shared `env`/`mock_config` harness and asserts the observable `set_env_variable` side-effect.
- Integration gate: the FULL suite ran green (`1602 passed, 5 skipped`).

### D7 — Wiring: thread `setup_api_key` end-to-end (Tracer Bullet)

- Added `setup_api_key: Optional[bool] = None` (appended LAST, so no positional caller shifts) to `handle_new_session` and `handle_resume_session`, and forwarded `setup_api_key=setup_api_key` into each `_run_cli_preflight_check(...)` call. `handle_plan_generation` (the `execute`/pipeline flow) passes `setup_api_key=False`.
- Added `_resolve_setup_api_key(system_env, pipeline) -> bool` in `__main__.py` returning `system_env.isatty() and not pipeline`, computed at BOTH the `start` and `resume` boundaries and passed into the handlers. It deliberately OMITS the editor resolver's `interactive`/`message` clause because the API key is REQUIRED (the editor is optional), so this gate is strictly WIDER.
- New Acceptance test `tests/suites/acceptance/test_api_key_setup_wiring.py::test_start_yolo_with_message_prompts_for_api_key_on_tty` drives `start -y -m "hi"` on a TTY with `llm.api_key` missing and asserts the observable persist `set_env_variable("TEDDY_LLM_API_KEY", "entered-value")`. `-y -m` is the sharp discriminator: it is fully specified, so the OPTIONAL editor gate is off, yet the REQUIRED key prompt still fires.
- **Integration-gate Local Recoveries** (existing test files only; no production code outside D7's scope changed, so both were classified LOCAL FLAW, not Systemic Regression):
  - The wider gate also fired in `test_editor_setup_decoupling.py`'s `-y` (no `-m`) TTY test, adding a second `set_setting` call and breaking its strict `assert_called_once_with("editor", "nvim")`. Fixed by supplying an already-configured `llm.api_key` so the API-key gate stays inert (the API-key prompt behaviour is owned by the new Acceptance test).
  - The two byte-identical `_run_cli_preflight_check` lambda stubs in `test_session_cli_handlers.py` pinned the OLD preflight signature; extended both (via a single `Match All` edit) with `setup_api_key=None`. The stub stays STRICT (an explicit parameter, not `**kwargs`) so future preflight signature drift fails fast in the test.
- Integration gate: the FULL suite ran green (`1603 passed, 5 skipped`).

### D8 — Logic: gate unit edge-case table

- Added `tests/suites/unit/adapters/inbound/test_session_cli_handlers_api_key_gate.py` — 12 unit tests pinning the preflight gate helpers' INDEPENDENT edge cases, deliberately distinct from `test_session_preflight_wiring.py` (which owns the higher-layer gate firing/skip behaviour keyed on `setup_api_key`).
- `_is_llm_api_key_missing` permutations: `None` / `""` / `"   "` / `"\t\n"` all count as missing; a genuine key (including a whitespace-padded one) counts as present.
- `_prompt_for_api_key` cases: a non-empty entry persists BOTH `set_env_variable("TEDDY_LLM_API_KEY", value)` and `set_setting("llm.api_key", "${TEDDY_LLM_API_KEY}")`, then prints the GREEN confirmation; a whitespace-padded entry is persisted stripped; blank input persists nothing; EOF (Ctrl-D) and `typer.Abort` both return WITHOUT raising and persist nothing.
- Characterization suite: the D6 Seam already implemented both helpers, so the table was Green on first run — the Red intent was to pin the boundaries, not to demand missing code.
- Uses a real in-memory `IConfigService` double (`_RecordingConfigService`, recording every persist call) plus `monkeypatch` for the `typer` I/O seams — no bare mocks.
- Integration gate: the FULL suite ran green (`1615 passed, 5 skipped`).

### D9 — Cleanup: as-built component-doc update

- Updated `docs/architecture/adapters/outbound/yaml_config_adapter.md` to as-built reality: §1 Purpose now names the lazy `${VAR}` interpolation and the `.teddy/.env` secret persistence; §3 gained the `${VAR}` / `${VAR:-default}` / `$$` interpolation rules (value-only, lazy at `get_setting` time), the fresh-read `.env` layering with shell-env precedence, a corrected comment-preserving `set_setting` description (replacing the stale `yaml.dump()` round-trip text), and a new `### Writing Secrets (set_env_variable)` subsection; §4 gained the `set_env_variable` method contract with the `os.environ` non-mutation invariant.
- Updated `docs/architecture/core/ports/outbound/config_service.md` §4 to record the additive `set_env_variable` member declared by the port (mirrors the `set_setting` persistence contract, for secrets written to the config-directory `.env`).
- Both component docs carry `**Status:** Implemented`, matching the as-built code.
- Doc-only deliverable: no production code changed, so the full suite was unchanged (`1615 passed, 5 skipped`).

## Verification

1. `uv run pytest tests/suites/unit/adapters/outbound/test_yaml_config_adapter_interpolation.py -q` → `${VAR}` resolves from `.env`; shell env wins; `${VAR:-default}` falls back; unresolved → `""`; `$$` → literal `$`; plain strings untouched.
2. `uv run pytest tests/suites/unit/adapters/outbound/test_yaml_config_adapter.py tests/suites/unit/adapters/outbound/test_yaml_config_adapter_layering.py tests/suites/unit/adapters/outbound/test_yaml_config_adapter_preserves_comments.py -q` → existing adapter suites still pass.
3. `set_env_variable` writes `.teddy/.env` AND `os.environ` is unchanged; a SECOND real adapter resolves `get_setting("llm.api_key")` from the freshly-written `.env`.
4. `uv run pytest tests/suites/unit/adapters/inbound/test_session_preflight_wiring.py -q` → the prompt fires when the key is missing and `setup_api_key=True`; skipped when `setup_api_key=False`; after a simulated prompt+persist, the SAME-run resolution yields a non-empty key.
5. Manual smoke: on a fresh project, `teddy start` (TTY) prompts → key lands in `.teddy/.env` (`cat .teddy/.env`); `teddy start -y -m "hi"` on a TTY also prompts; `teddy start --pipeline -m "hi"` (and any piped/non-TTY run) hard-errors with a message pointing at `.teddy/.env` / `TEDDY_LLM_API_KEY`.
6. Isolation regression: an `EXECUTE` child shell does NOT see `TEDDY_LLM_API_KEY` (assert the process env is unchanged after a persist).
7. `teddy init config` (and a clean `teddy init`) creates `.teddy/.env`; confirm the bundled `resources/config/.env` ships in the wheel (`uv build` and inspect the artifact); if the dotfile is excluded or gitignored by the repo, embed the placeholder as a string constant in `init_service` instead.
8. Full suite green: `uv run pytest`.
