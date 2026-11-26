# Slice: Migrate the LiteLLM Probe Tests onto Injected Providers
- **Status:** Planned
- **Milestone:** [Milestone 5: Quality Gate & Debt Reconciliation](/docs/project/milestones/05-quality-gate-debt-reconciliation.md)
- **Depends On:** [05-01-static-analysis-green](./05-01-static-analysis-green.md), [05-02-suppression-audit](./05-02-suppression-audit.md)
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [LiteLLMAdapter](/docs/architecture/adapters/outbound/litellm_adapter.md), [TestComposition](/docs/architecture/tests/setup/composition.md)
- **Scope Slug:** `litellm-probe-seam`

## Goal
Drive the LiteLLM adapter's preflight, provider resolution, completion, and retry paths through its injected provider seam instead of mutating the third-party module, so those tests prove the adapter's behaviour rather than the module's, and then make the ban on module-level third-party patching deterministic.

## Context
- `LiteLLMAdapter` accepts an injected provider seam, so `validate_environment`, `get_llm_provider`, and `completion` can be driven without touching the `litellm` module.
- Six modules carry function-scoped `monkeypatch.setattr`, 24 sites in total: `test_litellm_adapter_preflight.py` 8, `test_litellm_adapter_provider_resolution.py` 6, `test_litellm_adapter_robustness.py` 4, `test_litellm_adapter.py` 2, `test_litellm_adapter_laziness.py` 2, and `test_litellm_retries.py` 2. The litellm-targeted subset is enumerated per site during the migration, because a `setattr` may target an unrelated module.
- `TID251` does not catch this shape: it flags `mock.patch` and bare `MagicMock` imports, not `monkeypatch.setattr` on a third-party module, so the practice survives every existing gate.
- The naming divergence is two files, not a contradiction: `test_litellm_retries.py` carries 2 sites while `test_litellm_adapter_retries.py` carries none, so both the milestone's patched list and its compliant example are correct. Six modules migrate, not four.
- Already compliant and the pattern to copy: `test_litellm_adapter_stream_guard.py`, `test_planning_service_preflight.py`, and the adapter-retries module, which injects its provider through `register_mock`.
- `FakeLitellmProvider` in `tests/harness/setup/litellm_doubles.py` is the shared double; it needs scripted completions and scripted failures before the robustness and retry cases can drive it.
- Ordering: `Depends On` 05-01, because the same test modules are being migrated off bare doubles, and 05-02, because both edit `[tool.ruff.lint.per-file-ignores]` and register a structural hook in `.pre-commit-config.yaml`.
- Rule placement: the structural ban lands in the same change as the migration, never before it, so the non-blocking quality job does not accrue another standing red.

## Scenarios

> As a maintainer, I want a retry test to script a failure without mutating a library.

```gherkin
Given a provider double scripted to fail once and then succeed
When the adapter's completion path runs
Then the retry is exercised end to end
And the litellm module was never mutated
```

> As a maintainer, I want the ban to be enforceable rather than advisory.

```gherkin
Given a new test that patches a third-party module directly
When the structural hook runs
Then it fails naming the module and the line
```

> As a maintainer, I want a migrated test to prove the adapter, not the module.

```gherkin
Given a preflight test whose provider double reports a missing dependency
When the adapter validates its environment
Then the failure is attributed to the adapter's own check
And the assertion inspects the double's recorded calls rather than module state
```

## Edge Cases
- **Import-time attribute**: If a test depended on a module attribute resolved at import, then it asserts the adapter's resolved default instead, because no seam can express a binding that happens before the adapter exists.
- **Per-attempt scripting**: If a retry case needs a different answer per attempt, then the fake exposes a response queue, because a single canned response cannot distinguish attempt one from attempt two.
- **Kwarg passthrough**: If a test needs to prove a specific keyword reached the library call, then the fake records its call arguments, because the assertion belongs to the double's observed surface.
- **Order dependence**: If the migrated test passed only because a previous test left module state behind, then it becomes order-independent by construction — the provider is constructed per test.
- **Hook false positive on stdlib**: If a test patches `os.environ` through `monkeypatch.setattr`, then the hook ignores it, because an environment variable is process state rather than a vendored library with a substitutable seam.
- **Hook cannot infer ownership**: If the hook cannot decide statically whether a dotted target is third-party, then it consults an explicit module allowlist that is extended when a new adapter is added, because a guess-based rule either misses or blocks legitimate patches.
- **Streaming path**: If a migrated case needs a streamed response, then the fake yields chunked deltas, because the stream guard module already proves that shape is expressible.
- **Per-file ignore residue**: If a migrated module carried a `per-file-ignores` entry for a related rule, then the entry is deleted once the module no longer needs it, because an ignore that outlives its finding hides the next one.

## Key Unknowns
- None. `FakeLitellmProvider` exposes `validate_environment`, `get_llm_provider`, `completion`, and a nested `AuthenticationError`, and constructs from a `missing_keys` list alone — it has no scripted failure and no per-attempt queue, so the Interface deliverable below is required rather than conditional.

## Impact
1. `[EXTEND]` `FakeLitellmProvider` in `tests/harness/setup/litellm_doubles.py` — scripted successes, scripted failures, per-attempt responses, and recorded call arguments.
2. `[MIGRATE]` The six module-level patching tests — preflight, provider resolution, robustness, the adapter suite, laziness, and the standalone retries module — driven through the injected seam.
3. `[NEW]` `.githooks/check_third_party_module_patching.py` — a structural check failing on a monkeypatch of a listed third-party module.
4. `[MIGRATE]` `.pre-commit-config.yaml` — register the hook in the `manual` stage beside the other structural checks.
5. `[NEW]` A unit test for the hook covering a banned patch, an allowed stdlib patch, and an allowed seam-injected double.
6. `[MIGRATE]` The `LiteLLMAdapter` and `TestComposition` component pages — record the seam as the only supported substitution point.
7. `[MIGRATE]` Milestone 05's requirement text — correct the retry-test filename contradiction the census resolves.

## Deliverables
- [ ] **Interface** — Extend `FakeLitellmProvider` with scripted failures and per-attempt responses, proving both through its own tests.
- [ ] **Harness** — Add the hook unit test and register the hook in the `manual` stage.
- [ ] **Migration** — Migrate the six modules onto the seam, keeping every behavioural assertion and deleting any per-file ignore that outlives its finding.
- [ ] **Env** — Land the structural ban in the same commit as the last migration, never before it.
- [ ] **Cleanup** — Record the seam as the sole substitution point on both component pages, and correct the milestone's retry-test filename.

## Implementation Notes

## Verification
1. **No module mutation:**
   Run `git grep -n "monkeypatch.setattr(\"litellm\|monkeypatch.setattr('litellm" -- tests`.
   Verify no hit remains.
2. **Retry still proven:**
   Run the migrated retry module and confirm it drives failure then success through the fake.
3. **Hook bites:**
   Add a module-level patch of `litellm` to a scratch test and run `uv run python .githooks/check_third_party_module_patching.py`.
   Verify it exits non-zero naming the module and line.
