# Slice: Suppression Audit and Enforced Bypass Policy
- **Status:** Planned
- **Milestone:** [Milestone 5: Quality Gate & Debt Reconciliation](/docs/project/milestones/05-quality-gate-debt-reconciliation.md)
- **Depends On:** [05-01-static-analysis-green](./05-01-static-analysis-green.md)
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [CLI Adapter](/docs/architecture/adapters/inbound/cli.md)
- **Scope Slug:** `suppression-audit`

## Goal
Make every quality-gate bypass either disappear or explain itself, and enforce that rule with a deterministic hook, so the bypass policy stops being prose that decays and becomes a check that fails the build.

## Context
- `noqa` distribution in `src/`, measured 2026-11-26: `PLR0913` 30, `PLC0415` 10, `F401` 6, `F811` 1, `C901` 1. Total 49 lines. The `PLR0915`, `PLR0912`, and `noqa: CODE` tokens an earlier census recorded no longer occur — `noqa: CODE` is not a ruff rule at all, so it suppressed nothing.
- `type: ignore` count in `src/`: 10.
- `pyproject.toml` `[tool.ruff.lint.per-file-ignores]`: fifteen entries — one repo-wide rule set for `tests/**/*` and fourteen file-scoped entries across `src`, `tests`, and `scripts/demo/drive.py`. Several carry a comment stating remediation is "scheduled with the broader quality-gate debt" — this slice is that schedule coming due, and 05-01 already removed the findings inside them.
- Some suppressions are legitimate by design: `PLC0415` marks function-local imports, which `docs/architecture/ARCHITECTURE.md` mandates so heavy libraries (`litellm`, `trafilatura`) load lazily and the CLI initializes under 500 ms. The audit must distinguish a mandated pattern from an escape hatch, and convert the mandated one into a documented helper rather than suppressing the rule by habit.
- `PLR0913` at 30 is the largest block. Each site is a function with more than five parameters; a parameter object or a keyword-only grouping removes the finding. Where the count is dictated by a framework (a Typer command signature) or by a composition-root factory, a config-level ignore with a reason is the honest resolution.
- Enforcement gap: nothing fails today on a bare `# noqa` or a bare `# type: ignore`. The Quality-Gate Bypass Policy in the agent protocol is therefore unenforceable in this repository.
- Ordering: `Depends On` 05-01 because both edit `pyproject.toml` and the same test modules; running them concurrently would guarantee a conflict in the ignore block.

## Scenarios

> As a maintainer, I want a suppression to state why it exists.

```gherkin
Given a line carrying an inline suppression
When the hook runs over the repository
Then it passes only if the suppression names a rule code and a reason
```

> As a maintainer, I want a stale bypass deleted rather than inherited.

```gherkin
Given a per-file-ignores entry whose finding 05-01 already fixed
When this slice completes
Then the entry is gone
And removing it leaves ruff green
```

> As a maintainer, I want the lazy-import rule silenced deliberately rather than per line.

```gherkin
Given a module that imports litellm inside a function for startup latency
When the audit resolves that site
Then the import is expressed through the documented lazy-loading helper
And no per-line PLC0415 suppression remains
```

## Edge Cases
- **`noqa: CODE` token**: If `CODE` is not a real ruff rule, then it suppresses nothing and is either a placeholder inside a comment or a typo; it must be verified and corrected, not counted as coverage.
- **`F811` redefinition**: If the suppression hides a genuine redefinition, then removing it surfaces a real defect, because a redefinition is never a style preference.
- **Third-party untypeable call**: If a `type: ignore` covers a call whose library ships no types, then it stays with a bracketed code and a reason naming the library.
- **Repo-wide `PLR2004` for tests**: If the ignore is removed, then hundreds of assertion literals flood the linter, because magic values in assertions are the point of a test; it stays as a reasoned config-level entry.
- **`TID251` per-file ignores**: If an entry remains after 05-01 migrated the site, then the ignore is stale and deletion is mandatory, because a stale mock-hygiene bypass silently re-permits bare doubles.
- **`C901` on a linear demo script**: If the script has no test coverage and splitting it would risk a timing regression, then a config-level entry with that reason is acceptable, and it already carries one.
- **Windows-only `attr-defined`**: If a suppression covers a platform-conditional member that 05-01's accessor did not absorb, then it must name `attr-defined` and the platform, so the next audit can re-evaluate it.
- **Reason rot**: If a reason names a ticket or a milestone instead of a mechanism, then the hook rejects it, because a reason must explain *why the rule cannot hold here*, not who deferred it.
- **Historical bypass**: If the audit finds a past commit that bypassed the gate, then it records the finding rather than rewriting history, because the durable value is the pattern the bypass reveals, not a retroactive clean-up.
- **Audit finds no markers**: If the history carries no explicit bypass marker, then the audit records that absence as its own result, because "no bypass is visible in history" is a fact worth keeping and not a licence to widen the search into guesswork.

## Key Unknowns
- [ ] [Technical] Whether the 10 `PLC0415` sites are exactly the mandated lazy heavy imports. Design Sensitivity: if they are → one documented lazy-loading helper absorbs all ten and no suppression survives; if some are circular-import workarounds → those sites need an interface extraction instead, which becomes its own deliverable and may exceed this slice's scope.

## Impact
1. `[NEW]` `.githooks/check_suppression_reasons.py` — a structural check that fails on a bare `noqa`/`type: ignore`, on a suppression without a reason, and on a `per-file-ignores` entry lacking a comment.
2. `[MIGRATE]` `pyproject.toml` — prune the stale entries, keep only reasoned config-level ones.
3. `[MIGRATE]` The 49 inline `noqa` sites and 10 `type: ignore` sites — removed, narrowed, or converted to the lazy-loading helper.
4. `[MIGRATE]` `.pre-commit-config.yaml` — register the hook in the `manual` stage beside the other structural checks.
5. `[NEW]` A unit test for the hook proving it rejects a bare suppression, accepts a reasoned one, and accepts a reasoned config entry.
6. `[MIGRATE]` `docs/architecture/ARCHITECTURE.md` — point the Quality-Gate Bypass bullet and the Deterministic Boundary & Anti-Pattern Enforcement bullet at the hook as the enforcement.
7. `[NEW]` A commit-history bypass ledger recorded in this slice's `## Implementation Notes`, because a past bypass cannot be re-run as a test and its only durable form is the record.

## Deliverables
- [ ] **Env** — Add the suppression-reason hook, register it in the `manual` stage, and wire it into the structural-check step list.
- [ ] **Harness** — Unit-test the hook against a bare suppression, a reasoned inline suppression, and a reasoned `per-file-ignores` entry.
- [ ] **Interface** — Introduce the lazy-loading helper that expresses a mandated deferred import without a suppression.
- [ ] **Migration** — Reconcile all 59 inline suppressions and every `per-file-ignores` entry, keeping the suite green throughout.
- [ ] **Audit** — Walk the commit history for past gate bypasses — `--no-verify`, `-n`, skip-CI markers, and commits that introduced a suppression in the same change as the code it silences — and record each in `## Implementation Notes` with its disposition.
- [ ] **Cleanup** — Point the two ARCHITECTURE bullets at the hook and delete the "scheduled for remediation" comments the entries carried.

## Implementation Notes

## Verification
1. **Hook bites:**
   Add a bare `# noqa` to a scratch file and run `uv run python .githooks/check_suppression_reasons.py`.
   Verify it exits non-zero naming the file and line.
2. **Audit residue:**
   Run `git grep -c "noqa" -- src` and inspect each remaining hit.
   Verify every one names a rule code and a reason.
3. **Config residue:**
   Inspect `[tool.ruff.lint.per-file-ignores]`.
   Verify each entry carries a comment explaining why the rule cannot hold in that file.
