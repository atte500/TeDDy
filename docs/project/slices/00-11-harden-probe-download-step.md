# Slice: Harden `make probe` Download Step
- **Status:** Planned
- **Milestone:** [05-quality-gate-debt-reconciliation.md](/docs/project/milestones/05-quality-gate-debt-reconciliation.md)
- **Depends On:** N/A
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:** N/A
- **Scope Slug:** `probe-download`

## Goal
A failed probe artifact download must never silently reuse a stale `spikes/debug/probe_output.txt`, so a probe result is either fresh or an explicit, loud error.

## Context
- `make/probe.mk`: the `probe` recipe's download line is `gh run download "$$RUN_ID" --name probe-result --dir spikes/debug >/dev/null 2>&1 || true;`, followed by `cat spikes/debug/probe_output.txt 2>/dev/null || echo "(no output file)"`. A failed download is suppressed, so the prior run's file is printed unchanged and looks fresh.
- `docs/templates/makefile.md` and `src/teddy_executor/resources/templates/makefile.md`: carry the identical recipe. `tests/suites/unit/test_default_make_targets.py::test_template_copies_are_byte_identical` pins byte-identity between the two templates, so both must receive the same change in lockstep.
- `tests/suites/unit/test_default_make_targets.py`: currently pins template byte-identity, Makefile ASCII-only text, and `make help` success. It does NOT assert the probe recipe text or exercise the download branch.
- `.github/workflows/debug.yml`: uploads `spikes/debug/probe_output.txt` as artifact `probe-result`. The download contract (`--name probe-result --dir spikes/debug`) must be preserved verbatim.
- `gh run watch "$$RUN_ID" --exit-status >/dev/null 2>&1 || true`: intentionally tolerated. A probe run exits non-zero in the expected diagnostic case, so the watch suppression is correct and out of scope; only the download must fail loudly (Failure Transparency).

## Scenarios
> As a Debugger, I want `make probe` to fail when the artifact cannot be retrieved so that I never analyze stale probe output as if it were fresh.

```gherkin
Given a dispatched probe run whose artifact download succeeds
When I run make probe REASON="..."
Then the fresh spikes/debug/probe_output.txt is printed and the target exits 0
```

```gherkin
Given a dispatched probe run whose artifact download fails
When I run make probe REASON="..."
Then the target clears any prior output file before download, prints a stderr error naming the run, and exits non-zero
```

## Edge Cases
- **Stale file present**: If `spikes/debug/probe_output.txt` exists from a prior run and the new download fails, then the target must NOT print the stale file; it must exit non-zero, because the output is not fresh evidence.
- **Missing artifact**: If the workflow uploads no `probe-result` artifact, then the download returns nonzero and the target reports the failure, because the artifact contract is unmet.
- **Template parity**: If the recipe changes in `make/probe.mk`, then both template copies must change identically, because `test_template_copies_are_byte_identical` pins byte-identity and a one-sided edit fails the suite.

## Key Unknowns
- [x] None. The recipe location, artifact contract, and lockstep copies are fully identified via static reading.

## Impact
1. `[MIGRATE]` `make/probe.mk` `probe` recipe — remove the stale-file fallback, clear the output before download, and fail loudly when the download returns nonzero.
2. `[MIGRATE]` `docs/templates/makefile.md` — apply the identical recipe change.
3. `[MIGRATE]` `src/teddy_executor/resources/templates/makefile.md` — apply the identical recipe change so bootstrapped projects inherit the fix.

## Deliverables
- [ ] **Harness** - Extend `tests/suites/unit/test_default_make_targets.py` with a structural pin that the `probe` recipe clears `spikes/debug/probe_output.txt` before the download and that the download is not suppressed with `|| true`.
- [ ] **Migration** - Harden the `probe` recipe in `make/probe.mk`: `rm -f spikes/debug/probe_output.txt` before the download, and replace the suppressed download with a conditional that prints a stderr error naming the run and exits nonzero on failure.
- [ ] **Migration** - Mirror the identical recipe change into `docs/templates/makefile.md` and `src/teddy_executor/resources/templates/makefile.md`, keeping the two byte-identical.

## Implementation Notes
Free-form notes recording decisions, deviations, or discoveries during implementation.

## Verification
1. **Recipe shape:**
   Run `grep -n "probe_output" make/probe.mk`.
   Verify an `rm -f spikes/debug/probe_output.txt` precedes the download and the download line carries no `|| true` suppression.
2. **Template lockstep:**
   Run `diff docs/templates/makefile.md src/teddy_executor/resources/templates/makefile.md`.
   Verify the two files are identical (no output).
3. **Live behavior (requires a real dispatch):**
   Run `make probe REASON="verify download hardening"`.
   Confirm a successful download prints fresh output, and that a forced download failure exits nonzero with a stderr error naming the run instead of printing stale output.
