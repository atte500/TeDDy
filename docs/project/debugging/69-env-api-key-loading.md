# Bug: TEDDY_LLM_API_KEY from .teddy/.env Causes AuthenticationError
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** [00-27-llm-api-key-configuration](/docs/project/slices/00-27-llm-api-key-configuration.md)
- **Specs:** N/A

## Symptoms
**Expected:** When `TEDDY_LLM_API_KEY="sk-or-v1-..."` is set in `.teddy/.env`, the LLM client authenticates successfully.
**Actual:** LLM completion fails with `litellm.AuthenticationError: AuthenticationError: OpenrouterException - {"error":{"message":"Missing Authentication header","code":401}}`.
This occurs both with and without quotes around the API key value.

**Reproduction Steps:**
1. Create `.teddy/.env` with `TEDDY_LLM_API_KEY=sk-placeholder-xxxxxxxx`
2. Run `teddy start -a developer -m "test"`
3. Observe AuthenticationError in the LLM call.

## Context & Scope
### Regressing Delta
The bug was introduced by Slice 00-27 (LLM API key configuration), specifically the changes to `YamlConfigAdapter._maybe_interpolate` that added `${VAR}` interpolation. The method was designed to interpolate string values returned by `get_setting()`, but only handles top-level string results — it does NOT recursively process nested dicts or lists. This means `get_setting('llm', {})` (used by `LiteLLMAdapter._prepare_completion_params`) returns the `llm` section dict with `api_key` still as the literal `${TEDDY_LLM_API_KEY}` token.

### Environmental Triggers
- `.teddy/.env` file exists with `TEDDY_LLM_API_KEY` set.
- The error occurs on all platforms (macOS confirmed; Windows/Linux similarly affected).
- Any path that calls `get_setting()` with a parent key (e.g., `get_setting("llm", {})`, `get_setting("execution", {})`) on a config section with `${VAR}` tokens in child strings will exhibit the same bug.

### Ruled Out
- **dotenv loading**: `_build_interpolation_env()` correctly reads `.teddy/.env` and merges with `os.environ`. Verified by successful interpolation via the nested-key path `get_setting("llm.api_key")`.
- **`set_env_variable()` quoting**: The `quote_mode="always"` parameter was confirmed to write correctly quoted values. The user's manual edits (with or without quotes) also resolve correctly via the nested-key path.
- **LiteLLMAdapter config resolution**: `_prepare_completion_params` correctly calls `get_setting("llm", {})` — the issue is in the config service, not the LLM client.

## Diagnostic Analysis
### Causal Model
The `YamlConfigAdapter.get_setting()` method uses `_maybe_interpolate()` to resolve `${VAR}` tokens in config values. The current implementation of `_maybe_interpolate` only handles direct string values:

```python
def _maybe_interpolate(self, value: Any) -> Any:
    """Interpolate only string values that actually carry a token."""
    if isinstance(value, str) and "${" in value:
        return self._interpolate(value)
    return value
```

When `get_setting("llm.api_key")` is called, the internal `_resolve_nested` traverses the dict tree and returns the leaf string `"${TEDDY_LLM_API_KEY}"`, which is then passed to `_maybe_interpolate` and correctly resolved.

However, when `get_setting("llm", {})` is called, the top-level match (`key in self._config` — see [yaml_config_adapter.py:71](/src/teddy_executor/adapters/outbound/yaml_config_adapter.py#L71)) returns the entire `llm` dict **without** traversing its children. The dict itself is not a string, so `_maybe_interpolate` returns it unchanged — leaving all child strings containing `${VAR}` tokens unresolved.

`LiteLLMAdapter._prepare_completion_params` uses `get_setting("llm", {})` to merge the entire `llm` config section into the completion parameters. The unresolved `${TEDDY_LLM_API_KEY}` string is passed as `api_key` to `litellm.completion()`, which sends it as the HTTP `Authorization` header — causing OpenRouter to reject it with "Missing Authentication header" (since the literal token is not a valid API key).

### Discrepancies
- `_maybe_interpolate` treats dicts as opaque, returning them without recursive processing. (Resolved: confirmed by MRE in Turn 2 — `get_setting("llm", {})` returns `api_key: '${TEDDY_LLM_API_KEY}'`.)
- `_maybe_interpolate` has no handling for lists containing interpolatable strings. (Resolved: included in the fix with recursive list processing.)
- The `_maybe_interpolate` call in `get_setting` does not use `deepcopy()` on the config value before mutating it via interpolation. (Resolved: verified that `get_setting("llm.api_key")` returns the resolved value correctly — the existing code does NOT mutate the cache because `_interpolate` returns a new string. However, the shadow fix adds `deepcopy` as a defensive measure for dict/list recursion since `_maybe_interpolate` now mutates the intermediate structure.)
- The fix (recursive dict/list processing) resolves all test scenarios. (Resolved: MRE against shadow file passes — all four tests show correct interpolation.)

### Investigation History
1. **Hypothesis**: `_maybe_interpolate` does not recursively process dicts — `get_setting("llm", {})` returns literal `${TEDDY_LLM_API_KEY}`.
   **Observation**: MRE confirmed — `get_setting("llm.api_key")` resolves correctly, but `get_setting("llm", {})` returns the dict with `api_key` as literal `${TEDDY_LLM_API_KEY}`.
   **Conclusion**: Hypothesis confirmed. Root cause identified.

2. **Hypothesis**: Making `_maybe_interpolate` recursive (handling dicts and lists) fixes the issue.
   **Observation**: Shadow file with recursive `_maybe_interpolate` passes the MRE — all four tests show correct interpolation.
   **Conclusion**: The fix is proven via Zero-Touch Verification. Exact fix: replace `_maybe_interpolate` in the real `yaml_config_adapter.py` with the recursive version (including `deepcopy` for safety).

## Solution
Root cause: `YamlConfigAdapter._maybe_interpolate` returns non-string values (dicts, lists) unchanged, so `${VAR}` tokens inside child strings of a retrieved dict section are never resolved.

Fix: Replace `_maybe_interpolate` with a recursive version that:
1. Interpolates string values containing `${VAR}` tokens.
2. Recursively processes all values in dicts (returning a new dict with interpolated children).
3. Recursively processes all items in lists.
4. Returns non-string, non-dict, non-list values unchanged.
5. Uses `deepcopy` on the input value (the caller in `get_setting` already passes a copy, but recursion internalizes the pattern for safety).

Preventative measures:
- **Add unit tests** for `_maybe_interpolate` covering: plain strings (with/without tokens), nested dicts, lists, mixed structures, and edge cases (unresolved tokens, `$$` escaping, empty strings).
- **Audit all `get_setting()` call sites** that retrieve parent sections (like `get_setting("llm", {})`) to ensure they are covered by the fix. The existing call sites in `litellm_adapter.py` (`_prepare_completion_params`), `console_tooling.py`, and `planning_service.py` all benefit from the recursive fix automatically.
- **Add an integration-level check** that verifies the config service resolves `${VAR}` tokens at all nesting depths — this prevents regression if `_maybe_interpolate` becomes non-recursive again.
