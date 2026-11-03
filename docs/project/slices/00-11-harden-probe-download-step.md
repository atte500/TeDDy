# Slice: Harden `make probe` Download Step
- **Status:** In Progress
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
- [x] **Harness** - Extend `tests/suites/unit/test_default_make_targets.py` with a structural pin that the `probe` recipe clears `spikes/debug/probe_output.txt` before the download and that the download is not suppressed with `|| true`.
- [x] **Migration** - Harden the `probe` recipe in `make/probe.mk`: `rm -f spikes/debug/probe_output.txt` before the download, and replace the suppressed download with a conditional that prints a stderr error naming the run and exits nonzero on failure.
- [x] **Migration** - Mirror the identical recipe change into `docs/templates/makefile.md` and `src/teddy_executor/resources/templates/makefile.md`, keeping the two byte-identical.

## Implementation Notes

### Harness (Deliverable 1)
- Added `test_probe_recipe_clears_output_and_fails_loudly_on_download_failure` to `tests/suites/unit/test_default_make_targets.py`. It locates the `rm -f spikes/debug/probe_output.txt` line and the `gh run download` line in `make/probe.mk` and asserts the clear precedes the download and that the download line carries no `|| true` suppression. It also asserts both lines exist.
- Genuine Red was proven with `--runxfail`: the test fails at `AssertionError: probe recipe must clear spikes/debug/probe_output.txt` against the current recipe, confirming the pin exercises the real gap rather than trivially passing.
- The hardened recipe does not exist until Deliverable 2. To honor the green-at-every-commit gate, the pin is staged with `@pytest.mark.xfail(strict=True)`. Strict mode forces removal of the marker the moment the recipe is hardened (an unexpected pass becomes a failure otherwise). The marker MUST be removed in Deliverable 2's Green step.
- Integration gate passed: full `make test` reports `2121 passed, 5 skipped, 1 xfailed`, exit 0.

### Migration (Deliverable 2)
- Hardened the `probe` recipe in `make/probe.mk`: inserted `rm -f spikes/debug/probe_output.txt` on the line immediately before the download so a stale file can never be printed as if fresh, and replaced the `|| true`-suppressed download with `|| { echo "Probe: failed to download probe-result artifact for run $$RUN_ID." >&2; exit 1; }` so a failed download names the run and exits nonzero.
- Preserved the `gh run watch "$$RUN_ID" --exit-status >/dev/null 2>&1 || true` suppression verbatim, because a probe run legitimately exits nonzero in the expected diagnostic case; only the download must fail loudly.
- Preserved the `--name probe-result --dir spikes/debug` download contract verbatim.
- Removed the `@pytest.mark.xfail(strict=True)` marker and the now-unused `import pytest` from `test_default_make_targets.py`. Genuine Red was re-confirmed against the unhardened recipe (failure at "probe recipe must clear spikes/debug/probe_output.txt") before the fix; the pin now passes as a normal strict test.
- Integration gate passed: full `make test` reports `2122 passed, 5 skipped`, exit 0.

### Migration (Deliverable 3)
- Mirrored the identical hardened recipe into both `docs/templates/makefile.md` and `src/teddy_executor/resources/templates/makefile.md` using the same tab-safe inline-Python replacement that asserted exactly one suppressed-download occurrence per file.
- Genuine Red was proven first: editing only `docs/templates/makefile.md` made `test_template_copies_are_byte_identical` FAIL (byte diff at index 22483), confirming the lockstep guard cannot be bypassed by a one-sided edit.
- Restored green by applying the identical edit to the bundled template; `diff` reports the two files IDENTICAL and the targeted file reports 4 passed.
- Both template copies now carry `rm -f spikes/debug/probe_output.txt` immediately before the download and the loud `|| { echo "Probe: failed to download probe-result artifact for run $$RUN_ID." >&2; exit 1; }` guard, with the `gh run watch ... || true` suppression and the `--name probe-result --dir spikes/debug` contract preserved verbatim.
- Integration gate passed: full `make test` reports `2122 passed, 5 skipped`, exit 0.

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
