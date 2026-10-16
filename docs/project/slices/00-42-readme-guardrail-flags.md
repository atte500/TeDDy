# Slice: README Guardrail Flags
- **Status:** Completed
- **Milestone:** N/A (ad-hoc slice)
- **Depends On:** N/A
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:** N/A
- **Scope Slug:** `readme`

## Business Goal
Document the `--max-turns` and `--max-cost` optional flags in the README, so operators can discover the guardrail limits from the user-facing reference instead of the source code.

## Scenarios

> As an operator, I want the README to list the guardrail flags, so that I can bound a non-interactive run without reading the source.

```gherkin
Given the README documents the CLI optional flags
When I read the Optional Flags list
Then it names --max-turns and --max-cost with their purpose
```

## Edge Cases
- **Config override mention**: If a flag overrides a config value, then the entry names the config key, because operators need the fallback path.
- **No duplication**: The Environment Variables table already carries both variables, so this slice must not duplicate them.

## Key Unknowns
- [x] [Domain] Edit target: RESOLVED — the README `### Optional Flags` list omits both flags; the Environment Variables table already carries both variables.

## Impact
1. `[MIGRATE]` `README.md` `### Optional Flags` list — add the `--max-turns` and `--max-cost` entries.

## Deliverables
- [x] **Cleanup** - Add `--max-turns` and `--max-cost` to the README Optional Flags list.

## Implementation Notes

### Cleanup (delivered)

- Appended two entries to the README `### Optional Flags` list: `--max-turns` ("Maximum turns for a non-interactive run. Overrides `guardrails.max_turns` in `.teddy/config.yaml`.") and `--max-cost` ("Maximum session cost in dollars for a non-interactive run. Overrides `guardrails.max_session_cost` in `.teddy/config.yaml`.").
- Each entry names its overriding config key, per the slice Edge Case, so an operator can find the fallback path.
- The Environment Variables table already carried `TEDDY_MAX_TURNS` and `TEDDY_MAX_SESSION_COST`, so this slice did not duplicate them.
- Added a focused unit guard `tests/suites/unit/test_readme_guardrail_flags.py` that scopes its assertion to the `### Optional Flags` section. A whole-file check would falsely pass, because the Environment Variables table already names both variables.
- Cleanup proof: the Red step reported `2 failed`, each an `AssertionError` naming the missing flag, and the Green step reported `2 passed`.
- Integration proof: `make test` reports `1840 passed, 5 skipped`.
- No component-design doc changed, because the slice touched only the user-facing README and one self-contained test.

## Verification
- [ ] **README flags:**
    Open `README.md` and read the `### Optional Flags` section.
    Verify it lists `--max-turns` and `--max-cost`.
