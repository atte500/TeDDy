# Slice: Provider-Aware API Key Prompt and Local Endpoint Placeholder
- **Status:** Planned
- **Milestone:** Ad-hoc (no milestone)
- **Depends On:** [00-01](/docs/project/slices/00-01-defer-interactive-setup-to-session-start.md), [00-03](/docs/project/slices/00-03-remove-api-key-flag.md)
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** None
- **Component Docs:** [CLI Adapter](/docs/architecture/adapters/inbound/cli.md), [LiteLLMAdapter](/docs/architecture/adapters/outbound/litellm_adapter.md), [YamlConfigAdapter](/docs/architecture/adapters/outbound/yaml_config_adapter.md)
- **Scope Slug:** `api-key-prompt`

## Goal
Name the provider and the prefix-stripped model at the key prompt. Write a placeholder key with no prompt when the endpoint is local. Fail at preflight with a paste-ready fix when the model name carries no resolvable provider.

## Context
- `litellm.get_llm_provider(model, api_base=None)`: Returns `(model, provider, dynamic_api_key, api_base)`. It strips a recognised prefix, so `openai/qwen3-coder-30b` yields model `qwen3-coder-30b` and provider `openai`.
- A bare model name raises `BadRequestError: LLM Provider NOT provided`.
- `litellm.validate_environment(model)`: Returns `keys_in_environment: True` for a bare model name, so the current gate stays closed and the failure defers to the first completion.
- `litellm.validate_environment(model)`: Reports `lm_studio` and `hosted_vllm` as keyless and injects `fake-api-key` itself.
- An `openai/` model with a loopback `api_base` still reports `OPENAI_API_KEY` missing.
- `litellm`: Prints `Provider List: https://docs.litellm.ai/docs/providers` to stdout when resolution fails.
- `session_cli_handlers._prompt_for_api_key`: Prints a yellow warning that hardcodes OpenRouter as the default provider, regardless of the configured model.
- `session_cli_handlers._llm_model_requires_api_key`: Treats a `missing_keys` entry with an `_API_KEY` suffix as a key requirement.
- `session_cli_handlers._ensure_api_key_configured`: The single source of the key gate.
- `YamlConfigAdapter.set_env_variable`: Writes `.teddy/.env` only and never mutates `os.environ`. `set_setting("llm.api_key", "${TEDDY_LLM_API_KEY}")` switches the configuration to the interpolation form.
- `PlanningService._run_preflight_check`: Calls `LiteLLMAdapter.validate_config` before every generation.

### Copy contract
Warning body, no `api_base`:

```
⚠ No LLM API key configured.
  Provider: {provider}
  Model:    {model_without_provider_prefix}
```

Warning body, remote `api_base` set:

```
⚠ No LLM API key configured.
  Endpoint: {api_base}
  Model:    {model_without_provider_prefix}
```

Instruction lines, no `api_base`:

```
Paste your key below, or press Enter on an empty line to skip.
To use a different provider, change llm.model in .teddy/config.yaml.
```

Instruction line, remote `api_base` set:

```
Paste your key below, or press Enter on an empty line to skip.
```

Prompt label, save confirmation, and skip notice:

```
LLM API key
LLM API key saved to .teddy/.env.
ℹ No key saved.
```

Local endpoint, no prompt:

```
ℹ Local endpoint detected: {api_base}
  Saved placeholder API key "dummy-key-custom-endpoints" to .teddy/.env.
  Replace TEDDY_LLM_API_KEY there if the server checks the Authorization header.
```

Preflight provider error:

```
Cannot infer a provider for model '{model}'. Change llm.model in .teddy/config.yaml to prefix it with the provider, e.g. 'openai/{model}'.
```

## Scenarios

> As an OpenRouter user, I want the prompt to name the provider and the model, so I know which credential to paste.

```gherkin
Given `llm.model` is `openrouter/~deepseek/deepseek-flash-latest:nitro` and no key is configured
When I run `teddy start` on a terminal
Then the prompt shows `Provider: openrouter` and `Model: ~deepseek/deepseek-flash-latest:nitro`
```

> As a local-server user, I want no prompt at all, so setup never blocks.

```gherkin
Given `llm.model` is `openai/qwen3-coder-30b` and `llm.api_base` is `http://localhost:8080/v1`
When I run `teddy start` on a terminal
Then no prompt appears
And `.teddy/.env` holds `dummy-key-custom-endpoints`
```

> As a user with a typo in the model name, I want an early error, so I do not lose a turn.

```gherkin
Given `llm.model` is `qwen3-coder-30b` with no provider prefix
When the session starts
Then preflight fails with a message that names `llm.model` in `.teddy/config.yaml`
And the message shows a prefixed example
```

## Edge Cases
- **Loopback names**: If the `api_base` host is `localhost` or ends with `.localhost`, then it counts as local, because only the machine itself can answer.
- **Loopback literals**: If the host is an IPv4 loopback address, `::1`, or an IPv4-mapped loopback, then it counts as local, because every form addresses the same interface.
- **Private ranges**: If the host is an RFC1918 address, an IPv6 unique-local address, or a link-local address, then it counts as local, because it cannot be a public provider.
- **Container aliases**: If the host is `host.docker.internal` or ends with `.local`, then it counts as local, because those names resolve inside the developer machine.
- **Public host**: If the host is a public name or a public address, then the prompt appears, because a real credential can be required.
- **Scheme-less value**: If `api_base` is `localhost:11434` with no scheme, then the classifier must still read the host.
- **Malformed value**: If `api_base` has no parseable host, then the classifier reports not-local and the prompt appears, because a silent placeholder would hide a real requirement.
- **Vendor prefix on a local endpoint**: If `llm.model` is `deepseek/deepseek-chat` with a loopback `api_base`, then the placeholder is written, because the request goes to the local host.
- **Unresolvable model**: If `llm.model` has no provider prefix and no `api_base`, then preflight fails before any completion, because litellm cannot infer a provider.
- **Empty Enter at a remote prompt**: If the user submits an empty line, then nothing is saved and `ℹ No key saved.` prints, because a silent dummy would turn a clear error into an authentication failure.
- **Keyless provider**: If litellm reports no missing key, then the gate stays closed and nothing prints.
- **Hidden input**: If the user types a key, then the terminal must never echo it.
- **Stray library output**: If provider resolution fails, then the `Provider List:` line must be captured and never reach the CLI output.

## Key Unknowns
None. Provider resolution, key requiredness, host classification, and the prefix requirement were verified with two probes during discovery.

## Impact
1. `[NEW]` `session_cli_handlers._resolve_model_identity` — Returns the provider and the prefix-stripped model, with a fallback to the configured string.
2. `[NEW]` `session_cli_handlers._is_local_endpoint` — Classifies a host with no DNS lookup.
3. `[EXPAND]` `session_cli_handlers._prompt_for_api_key` — New copy, hidden input, and Enter-to-skip.
4. `[EXPAND]` `session_cli_handlers._ensure_api_key_configured` — Local-endpoint short circuit ahead of the prompt.
5. `[EXPAND]` `LiteLLMAdapter.validate_config` — Provider-resolution error with captured stdout.
6. `[CLEANUP]` The hardcoded OpenRouter warning branch and its test.
7. `[MIGRATE]` `resources/config/config.yaml` — Extend the local-model comment block with the prefix rule per server.

## Deliverables
- [ ] **Wiring** - Acceptance test: a loopback `api_base` persists the placeholder with no prompt. Implement `_is_local_endpoint` for loopback hosts and names, the local short circuit, and the placeholder write.
- [ ] **Wiring** - Acceptance test: an OpenRouter configuration prompts with the `Provider:` and stripped `Model:` lines. Implement `_resolve_model_identity` and the new prompt copy with hidden input and Enter-to-skip, and retire the obsolete OpenRouter warning assertion in the same commit.
- [ ] **Logic** - Cover the `_is_local_endpoint` host classifier with unit tests for loopback literals, private ranges, container aliases, a scheme-less value, a malformed value, and a public host.
- [ ] **Logic** - Add the provider-resolution error to `validate_config` with the library stdout captured, and cover the unresolvable-model and stray-output cases with unit tests.
- [ ] **Migration** - Extend the bundled config comment block with the per-server model prefix rule.

## Implementation Notes
- Orientation audit re-partitioned the deliverables. The original order could not keep the suite green, because the prompt copy change invalidates the OpenRouter warning assertion in `test_session_cli_handlers_api_key_gate.py` at that commit. The retirement therefore moves into the copy change.
- The audit split the single Wiring item into two atomic tracer bullets: the local placeholder path and the provider-aware copy. Each keeps every test green on its own commit.
- The standalone Contract deliverable was dropped. The two helpers are private module functions rather than ports or DTOs, so each arrives with the tracer bullet that needs it.
- The provider-resolution error is green-preserving because every existing preflight test uses a resolvable model. The bare-model guard appends an error only when litellm raises during resolution, so the mock-provider lazy-guard test stays green.
- The stdout capture wraps `litellm.get_llm_provider` in `redirect_stdout`, so the library provider list never reaches the CLI output.

## Verification
1. **Provider line:**
   Set `llm.model` to `openrouter/~deepseek/deepseek-flash-latest:nitro` and remove the key, then run `teddy start`.
   Verify the prompt shows `Provider: openrouter` and `Model: ~deepseek/deepseek-flash-latest:nitro`.
2. **Local endpoint:**
   Set `llm.model` to `openai/qwen3-coder-30b` and `llm.api_base` to `http://localhost:8080/v1`, then clear `TEDDY_LLM_API_KEY` in `.teddy/.env` and run `teddy start`.
   Verify the local-endpoint notice appears and no prompt does.
3. **Prefix error:**
   Set `llm.model` to `qwen3-coder-30b`, then run `teddy start`.
   Verify the error names `llm.model` in `.teddy/config.yaml` and suggests `openai/qwen3-coder-30b`.
