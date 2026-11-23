# Slice: Configurable Update Source
- **Status:** In Progress
- **Milestone:** N/A (ad-hoc)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [IConfigService](/docs/architecture/core/ports/outbound/config_service.md), [UpdateChecker](/docs/architecture/core/services/update_checker.md), [CLI Adapter](/docs/architecture/adapters/inbound/cli.md)
- **Scope Slug:** `update-source`

## Goal
Let a user point TeDDy's update check at their own fork's package source instead of the official PyPI endpoint, so a self-hosted distribution reports its own releases. Installing and upgrading from a fork already works through `uv`; this slice fixes the check, which today compares the installed version against upstream no matter where the code came from.

## Context
- `update_checker.py`: `PYPI_URL = "https://pypi.org/pypi/teddy-cli/json"` is the only home of the source literal. `fetch_latest_version(index_url=PYPI_URL, stable_only=True)` reads the PyPI JSON shape (`data["releases"]`, with an `info.version` fallback) and returns `None` on any failure (`fail_silent`). `background_check(cache_path, index_url=PYPI_URL)` fetches and writes the cache; `read_update_cache`/`write_update_cache` handle a `{latest_version, checked_at}` mapping with a 24-hour TTL and an atomic rename.
- `teddy update` (`__main__.py`) is notification-only: it passes `PYPI_URL` literally to `fetch_latest_version` and prints an upgrade hint. It performs no install.
- Session startup calls `_start_background_update_check()`, which spawns a daemon thread passing no source, and `_display_update_notification(container, cache_path)` already resolves `IConfigService` and gates only the printed notice on `checks.update`. The notice reads the cache the previous run's thread wrote.
- `config_schema._SCHEMA_FIELDS` is the canonical default table. Declared keys resolve through the typed view with exact-flat-first-then-nested precedence, and `construct_app_config` treats `None` and `""` as "use the schema default".
- `YamlConfigAdapter` deep-merges the bundled baseline in `resources/config/config.yaml` under `.teddy/config.yaml`, so an existing config inherits a new key without migration.
- `tests/suites/unit/core/domain/models/test_config_schema.py::test_documentation_and_schema_declare_the_same_keys` parses `config_service.md`, so the schema row and the documentation row ship in one change.
- The three `checks.*` keys are booleans that double as fired-check identifiers (`["checks.update"]` in the disable footer), so the source cannot live under `checks:`.
- `get_current_version()` reads the installed `teddy-cli` distribution metadata, so the installed distribution must keep that name. Distribution names are unique per index, not globally, so a git install, a local wheel, and a private index all keep `teddy-cli`; only a public PyPI upload under a different name would need a second knob, which is out of scope.
- The source only needs to be PyPI-JSON-shaped: `fetch_latest_version` falls back to `info.version` when `releases` is empty, so a static `version.json` served from a fork's repository is a valid source. That fallback ignores `stable_only`, so `--experimental` and the default agree for such a source.
- `uv` persists install-time options in `uv-receipt.toml` under `[tool.options]` — confirmed locally, where `prerelease = "allow"` survives, and in astral-sh/uv#11929, where a private index is recorded as an `index` list — and the documented rule is that "tool upgrades will retain the settings provided when installing the tool". A fork installed from a git URL or a private index therefore upgrades from that source with no change to TeDDy.
- `tests/conftest.py` guards the daemon thread (`_bound_background_update_thread`) and blocks live network calls (`disable_live_network_calls`), so a test-injected config stays offline.

## Scenarios

> As a developer running a fork, I want the update check to read my own package source so that I learn about my fork's releases instead of upstream's.

```gherkin
Given a project whose .teddy/config.yaml sets update.index_url to a fork's PyPI JSON endpoint
When the user runs `teddy update`
Then the command fetches the latest version from that endpoint
And it reports the version it found
```

> As a fork maintainer, I want the startup notice to reflect my configured source so that a routine session tells me about my own release.

```gherkin
Given a project whose .teddy/config.yaml sets update.index_url
And a cache entry reporting a newer version
When the user starts or resumes a session
Then the startup notice reports that newer version
And the next background check refreshes the cache from the configured source
```

> As an upstream user, I want the default behaviour unchanged so that nothing about my update check moves.

```gherkin
Given the default configuration with no update.index_url
When the user runs `teddy update`
Then the official PyPI JSON endpoint is queried
And the existing upgrade hint naming `teddy-cli` is printed
```

## Edge Cases
- **Unreachable or invalid endpoint**: If the configured URL fails to resolve or returns non-JSON, then `fetch_latest_version` returns `None` and the command prints its existing network-error line, because the `fail_silent` invariant is unchanged.
- **Surrounding whitespace**: If the configured value has leading or trailing spaces, then `resolve_index_url` strips them, because a stray space would otherwise make `urllib` fail with no visible cause.
- **Empty value**: If `update.index_url` is absent, empty, or `null`, then the official `PYPI_URL` is used, because the schema default is `""` and construction treats an empty value as the default.
- **Non-string value**: If `update.index_url` is a number or a list, then construction raises `ConfigurationError` naming the key, because the schema declares `str` and coerces nothing else.
- **Shared cache across sources**: If a project switches `update.index_url`, then the existing `.teddy/.update_cache.json` keeps supplying the notice until the next background check and the 24-hour TTL expire, because the cache records only `latest_version` and `checked_at`. The window is accepted: switching sources is a rare manual edit, and the worst case is one notice naming the previous source's version.
- **Custom source with `--experimental`**: If a custom source is configured and `--experimental` is passed, then the pre-release filter applies to whatever `releases` map that source returns, because `stable_only` passes through unchanged.
- **Upgrade hint unchanged**: If a custom source is configured, then the printed hint still names `uv tool upgrade teddy-cli`, because `uv` re-resolves the upgrade from the index recorded in its receipt. A fork installed from a git URL upgrades by reinstalling from that URL instead, which the README states.
- **Notice disabled**: If `checks.update` is `false`, then the startup notice is suppressed even with a custom source, because the toggle still gates only the printed notice while the background fetch runs.
- **Malformed configuration**: If `.teddy/config.yaml` cannot be read or a declared key is invalid, then `teddy update` fails through the same `ConfigurationError` path as other commands, because it now resolves configuration instead of bypassing it.
- **No project root**: If `teddy update` runs where neither the CWD nor an ancestor holds a `.teddy` directory, then no user config is merged and the official source is used.

## Key Unknowns
- [x] [Technical] Git-install upgrade semantics: resolved as README wording only. The official uv tools documentation states that tool upgrades "will retain the settings provided when installing the tool" and "will respect the version constraints provided when installing the tool", and the `uv tool upgrade` CLI reference repeats it for install-time settings. Neither page names a git URL, so the git case is covered by the general rule but not spelled out. The README therefore instructs a reinstall from the git URL instead of asserting `uv tool upgrade` advances a git install. No code, contract, or test impact.

## Impact
1. `[EXTEND]` `config_schema.UpdateConfig` / `AppConfig.update` / `_SCHEMA_FIELDS` — a new declared key `update.index_url` defaulting to `""`; existing keys and consumers untouched.
2. `[EXTEND]` `resources/config/config.yaml` — a commented `update:` group beside the existing `checks` block.
3. `[EXTEND]` `update_checker.resolve_index_url` — new pure resolver owning the `PYPI_URL` fallback, so no call site repeats `or PYPI_URL`.
4. `[MIGRATE]` `__main__.update` and `session_cli_handlers._start_background_update_check` — resolve `update.index_url` through `IConfigService` and pass the resolved URL into `fetch_latest_version` / `background_check`; the background helper gains a `container` parameter so it resolves before the daemon thread spawns.
5. `[PRUNE]` The literal `PYPI_URL` argument in the `teddy update` call and the argument-less `background_check(cache_path)` call — removed once both entry points resolve the source.

## Deliverables
- [x] **Interface** — Declare the key: a frozen `UpdateConfig(index_url: str = "")` dataclass, its `_FieldSpec` row, the `AppConfig.update` field, and the `construct_app_config` group argument; a commented `update:` group in the bundled `config.yaml`. Add `resolve_index_url(configured: Optional[str]) -> str` to `update_checker` (strip whitespace; `None` or empty → `PYPI_URL`).
- [ ] **Wiring** — Acceptance tracer bullet: with a config carrying `update.index_url`, `teddy update` queries that endpoint (assert the URL reaching `fetch_latest_version`), and `_start_background_update_check(container)` passes the same resolved URL into the daemon thread. The default configuration keeps reaching `PYPI_URL` at both sites.
- [ ] **Migration** — Update the tests whose assumptions shift: `test_experimental_wiring.py` gets an explicit empty `update.index_url` so its literal-URL assertion no longer depends on the developer's `.teddy/config.yaml`; `test_session_cli_handlers.py` adjusts its daemon-thread argument assertions to the new helper signature.
- [ ] **Cleanup** — Documentation lockstep: add the `update.index_url` row to `config_service.md`, document source resolution in `update_checker.md`, and add a README section covering the three install shapes (git URL, private index, static `version.json`), the `teddy-cli` distribution-name requirement, and the fact that `teddy update` compares against the configured source while `checks.update: false` silences only the startup notice.

## Implementation Notes

**Interface (delivered).**
- `update.index_url` is a declared key with default `""`: `UpdateConfig(index_url: str = "")`, `_FieldSpec("update.index_url", "update", "index_url", str)`, `AppConfig.update`, and the `construct_app_config` group argument. Because construction already treats `""` as "unset", an absent or empty value resolves the schema default and no second fallback appeared inside the schema.
- The `update.index_url` row in `config_service.md` shipped in this same commit: the parity test derives documented keys from the single `- **Configuration keys:**` bullet and drops tokens containing `*`, so a schema-only change would have left a documented-but-undeclared key unreachable and a docs-only change would have failed the same assertion in the opposite direction.
- `resolve_index_url(configured)` owns the `PYPI_URL` fallback exactly once: `None`, `""`, and whitespace-only all resolve the official endpoint, and any other value is stripped. The `None` branch keeps the helper total for a config service that returns no value at all.
- Non-string rejection needed no new code: `_coerce_str` raises `ConfigurationError` naming `update.index_url`, which the bundled `config.yaml` comment now documents alongside the key.
- The bundled `config.yaml` carries the group commented out. A live block would leave the resolved default identical, but the comment documents the knob without inviting an accidental edit, and the bundled-config toggle test only inspects the `checks` mapping so the block is inert either way.
- The resolver tests import inside each test body, matching `test_update_checker.py`'s existing style for every public function.
- Logger hoist: one module-level `logger` replaced three function-local `logging` imports, and `background_check` no longer shadows the module-level name.

**Red / Green evidence.**
- Red, schema: five failures — three `AttributeError: 'AppConfig' object has no attribute 'update'` and two `DID NOT RAISE ConfigurationError`, with all 38 pre-existing schema tests still passing.
- Red, resolver: four failures, each `ImportError: cannot import name 'resolve_index_url'`.
- Green: the three touched unit suites reported `75 passed`; the full unfiltered suite reported `2321 passed, 5 skipped`.

## Verification
1. **Custom source in `teddy update`:**
   Add `update:\n  index_url: "https://pypi.org/pypi/requests/json"` to `.teddy/config.yaml` and run `uv run teddy update`.
   Verify the reported version is a `requests` version (2.3x), not a TeDDy version. The `requests` endpoint is used deliberately: it is a reachable PyPI-JSON response whose version is far above the installed one, so the "newer version" branch is exercised.
2. **Default source unchanged:**
   Remove the `update` block and run `uv run teddy update`.
   Verify the output reports either `You are already running the latest version` or an upgrade hint naming `teddy-cli`.
3. **Startup path uses the configured source:**
   Set `update.index_url` to `https://pypi.org/pypi/requests/json`, delete `.teddy/.update_cache.json`, run `uv run teddy resume`, and quit with `q`.
   Inspect `.teddy/.update_cache.json` and verify `latest_version` is a `requests` version, proving the daemon thread fetched the configured endpoint instead of PyPI.
