# Slice: README Guardrail Flags
- **Status:** In Progress
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
- [▶] **Cleanup** - Add `--max-turns` and `--max-cost` to the README Optional Flags list.

## Implementation Notes

## Verification
- [ ] **README flags:**
    Open `README.md` and read the `### Optional Flags` section.
    Verify it lists `--max-turns` and `--max-cost`.
