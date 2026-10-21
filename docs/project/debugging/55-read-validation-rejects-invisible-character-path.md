# Bug: READ Validation Rejects a Path With Invisible Characters
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** [Plan Format Validation](/docs/project/specs/plan-format-validation.md)

## Symptoms
A plan whose `READ` resource was the Markdown link `[.gitignore](/.gitignore)` failed pre-flight validation with `File to read does not exist: .gitignore`, even though `.gitignore` existed at the project root. Ordinary files written with the same root-relative link form validated successfully. The rejected resource rendered identically to the real file, because it differed from the on-disk name only by an invisible codepoint.

## Context & Scope
### Regressing Delta
No commit introduced the behaviour. The parser normalization seam never removed Unicode format characters, so a resource created with one failed the existence check on its first attempt.

### Environmental Triggers
The defect triggers whenever a plan carries a Unicode `Cf` (format) codepoint inside a path value, for example a zero-width space pasted from a chat interface or a word processor. It does not depend on the operating system, on dotfile names, or on the link form.

### Ruled Out
- `ReadActionValidator`: it passes the raw parameter value to `path_exists` and performs no rewriting.
- `normalize_resource_path` in `core/utils/paths.py`: it removes an exact `./` prefix, so a leading dot survives.
- The `lstrip("./")` call sites in `core/utils/markdown.py`: they only classify review display labels.
- A leading-dot rule: four clean dotfile variants validated successfully, so dotfiles receive no special treatment.

## Diagnostic Analysis
### Causal Model
The plan parser extracts a link target and routes it through `normalize_link_target` and then `normalize_path`. Both helpers converted backslashes and stripped a leading slash, but neither removed Unicode format characters, which render as nothing yet occupy a codepoint in the string. Pre-flight validation therefore probed a sibling name that never existed. Confirmed by executing the real parser with the real validator against a temporary project root: the clean variants were accepted with `path_exists: True` and the variant carrying U+200B was rejected with `resource: '\u200b.gitignore'`.

### Discrepancies
- [x] Validation reported a missing file for a path that exists on disk. (Resolved: the resource string carried a zero-width space, so the probed name was a different file.)
- [x] The shared path normalizer preserved leading dots, yet the failure behaved as if the path were corrupted. (Resolved: the dot was preserved and the corruption was an invisible codepoint inside the name.)

### Investigation History
1. Read `validation_rules/filesystem.py`; observed that `ReadActionValidator` rejects only when `path_exists` returns false and never rewrites the value, which ruled out the validator.
2. Read `core/utils/paths.py`; observed that `normalize_resource_path` strips an exact `./` prefix, which ruled out dot loss there.
3. Searched every `lstrip` and `removeprefix` site under `src/`; observed the remaining character-set strips only classify review labels, which ruled them out for this path.
4. Ran the MRE `spikes/debug/read-validation-dotfile-path/01-read-validation-dotfile-mre.py` over five variants; observed the four clean dotfile forms accepted and only the U+200B variant rejected with `resource: '\u200b.gitignore'`, which reframed the defect as invisible-character corruption.
5. Scanned `.teddy/sessions`, `src`, `tests`, and `docs` with `spikes/debug/read-validation-dotfile-path/02-invisible-character-forensics.py`; found U+200B on the recorded `Resource:` line of every input for this session, which proved the failing input carried the character.
6. Proved the fix in a replica via `spikes/debug/read-validation-dotfile-path/03-verify-replica-fix.py`; the patched normalizers stripped format characters and all six variants validated with the expected resource.
7. Audited every consumer of the seam; observed that all plan paths funnel through `parser_metadata` into the two normalizers with no bypass, which confined the fix to one production module.
8. Applied the scrub to `src/teddy_executor/core/services/parser_infrastructure.py` and added regression tests; `make test` reported 1953 passed, 5 skipped.
9. Refined the scrub to preserve the shaping joiners U+200C and U+200D, because they bind emoji sequences and control cursive joining; `make test` reported 1954 passed, 5 skipped.
10. Relocated `strip_format_characters` into `core/utils/paths.py` and applied it inside `normalize_resource_path` before link extraction; `parser_infrastructure` now imports and re-exports it, which keeps the utility layer free of service imports and passed 18 targeted tests.
11. Added shared-helper scrubbing tests for the link branch, the raw-path branch, and joiner preservation; 20 targeted tests passed.
12. Added context-membership seam tests proving that a zero-width space on either side of `is_path_in_context` still matches; 27 targeted tests passed.
13. Created the `core/utils/paths.md` component design document and ran the full suite after the relocation; `make test` reported 1958 passed, 5 skipped.
14. Attempted the commit; the staged-file lint gate reported `PLR0911` on `coerce_param` in `parser_infrastructure.py`, a function this change never edited, so the finding predates the fix and surfaces only because the file is now staged. Split the numeric and boolean branches into `_coerce_numeric` and `_coerce_bool`, which cleared the finding without a suppression comment; the coercion and parser modules passed 22 targeted tests.

## Solution
### Root Cause
The parser path normalizers did not remove Unicode `Cf` (format) codepoints. A resource such as `/.gitignore` carried a zero-width space into the `resource` parameter, so `path_exists` probed an identically rendered but non-existent name. The fix strips format characters in `normalize_link_target` and in `normalize_path`, before and after percent decoding, while preserving U+200C and U+200D because those codepoints shape adjacent glyphs.

The canonical helper now lives in `core.utils.paths`, where `normalize_resource_path` also applies it before link extraction. Context membership therefore compares a scrubbed resource against scrubbed context paths, so an invisible character on either side cannot break the match.

The fix was applied directly to production code after an isolated replica proof verified the same logic through the real parser chain.

### Affected Components
- `src/teddy_executor/core/utils/paths.py`: hosts the canonical `strip_format_characters` helper and applies it inside `normalize_resource_path` before link extraction.
- `src/teddy_executor/core/services/parser_infrastructure.py`: imports and re-exports the canonical helper and applies it in both path normalizers. Also splits the parameter-coercion branches into `_coerce_numeric` and `_coerce_bool`, which clears a pre-existing return-count finding that blocked the commit.
- `tests/suites/unit/core/utils/test_paths.py`: regression tests for the link branch, the raw-path branch, and joiner preservation.
- `tests/suites/unit/core/services/test_parser_infrastructure.py`: regression tests for invisible codepoints, percent-encoded invisible codepoints, and joiner preservation.
- `tests/suites/unit/core/services/test_validation_helpers.py`: context-membership seam tests covering a zero-width space on either side of the comparison.
- `docs/architecture/core/services/parser_infrastructure.md`: scrubbing invariant, the `core.utils.paths` dependency, and both updated postconditions.
- `docs/architecture/core/utils/paths.md`: component design document for the canonical helper.
- `spikes/debug/read-validation-dotfile-path/01-read-validation-dotfile-mre.py`: preserved MRE that now guards the fixed contract.
- `spikes/debug/read-validation-dotfile-path/03-verify-replica-fix.py` with `replica_parser_infrastructure.py`: preserved replica proof.
- `spikes/debug/read-validation-dotfile-path/02-invisible-character-forensics.py`: preserved forensic scanner that located the offending codepoint.
