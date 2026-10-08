# Bug: Uninformative Plan Validation Errors

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** [plan-format-validation.md](/docs/project/specs/invariants/plan-format-validation.md), [plan-format.md](/docs/project/specs/invariants/plan-format.md)

## Symptoms

**Expected:** When a submitted Markdown plan fails structural validation, the surfaced (headline) error message should be *actionable*: it should state what was expected, what was actually found, and ideally where in the plan the failure occurred — e.g. `expected a Level 3 Action Heading, but found a Paragraph: "</parameter></invoke>"`.

**Actual:** The failure is surfaced as the truncated, self-referential message:

> `Structural error: Plan content is invalid: a Level 3 Action Heading.`

This names only the *expected* node and omits the *actual* offending token, so the author (typically an LLM) cannot determine *why* the plan is invalid. Curiously, the detailed AST dump in the *same* execution report contains the real diagnosis — e.g. `[017] Paragraph: "</parameter></invoke>" (Error: Expected a Level 3 Action Heading)` — so the information exists downstream but is lost from the headline error.

**Minimal reproduction steps (to be confirmed against source):**
1. Submit a plan whose body contains an unexpected node at a position where the parser expects an action heading. Two observed inputs from the prior session:
   - Stray trailing tags `</parameter></invoke>` after the final action code block.
   - A `src/...` line surfacing as a Level 1 heading after the last valid action.
2. Observe the uninformative `Plan content is invalid: a Level 3 Action Heading.` message.

## Context & Scope

### Regressing Delta
No local workspace change introduced this defect — the working tree is clean on `main`. The terse/descriptive split lives in `parser_reporting.py::format_structural_mismatch_msg`; `git log` on that file shows it evolved through `c712df5b` (diagnostic clarity for AST/EDIT failures), `33cdcce7` (structural message protocol), `497030fc` (MRP in execution-report validation message) and `839e13c9` (MRP expected structure). A `git log -S "Plan content is invalid"` dates the terse phrasing to commit `86ef441d feat(cli): add dynamic prompt headers and refactor interactor for SLOC compliance` — confirming a **latent formatting defect** in shared message code, not a single-delta regression.

### Environmental Triggers
None. The symptom depends only on plan *content* (unexpected nodes mid-action-stream) and reproduces purely in-process; no OS/platform/environment condition is involved.

### Ruled Out
- **OS/platform dependence** — the uninformative headline is produced entirely by in-process string assembly from plan content.
- **`InvalidPlanError.__str__` truncation** — `InvalidPlanError` (`core/ports/inbound/plan_parser.py:9`) is a plain `Exception` subclass carrying `offending_nodes`; it does not override `__str__`, so the full multi-paragraph message (expected-structure + AST dump) reaches the top level. This is exactly why the dump still shows the real diagnosis while the separate one-line *headline* omits it.

## Diagnostic Analysis

### Causal Model
The plan parser raises `InvalidPlanError` with a fully-rendered message produced by `format_structural_mismatch_msg(doc, expected, mismatch_idx, offending_nodes)` in `src/teddy_executor/core/services/parser_reporting.py`. That formatter selects between two headline phrasings based on a `mismatch_idx` sentinel:

- `mismatch_idx == -1` → terse: `Plan content is invalid: {expected}.` (drops the node actually found).
- otherwise → descriptive: `Plan structure is invalid. {error_header}, but found {actual_name}.`

`MarkdownPlanParser._parse_actions` (`markdown_plan_parser.py:282`) raises the action-heading error with `expected="a Level 3 Action Heading"` and `mismatch_idx=-1`, forcing the terse branch. Result: the headline is emitted as `Plan content is invalid: a Level 3 Action Heading.` — a self-referential, grammatically broken string naming only the *expected* node and never the node actually found. `actual_name = format_node_name(primary_node)` is computed in the same function but is unused on this branch. Both branches still append the expected-structure + AST dump, which is why the offending node (`[✗] [017] Paragraph: "</parameter></invoke>" (Error: Expected a Level 3 Action Heading)`) is visible in the detailed dump yet absent from the headline sentence surfaced by `session_orchestrator.py` (`errors=[f"Structural error: {str(e)}"]`).

Two distinct call paths feed the terse (`-1`) branch for the reported symptom:

1. **Mid-stream content error** — `MarkdownPlanParser._parse_actions` (`markdown_plan_parser.py:280-284`) encounters a node that is neither a Level-3 action heading, a `CodeFence`/`BlockCode`, nor a `ThematicBreak`; it accumulates the offending nodes via `consume_content_until_next_action` and raises with `mismatch_idx=-1`. This is the reported case (trailing `</parameter></invoke>` paragraph, or a stray `# src/...` H1 heading mid-body).
2. **Re-wrapped error** — `MarkdownPlanParser.parse` (`markdown_plan_parser.py:138-147`) catches any other `InvalidPlanError` whose message does NOT already contain the `### Expected Response Structure (MRP) ` block (e.g. `Unknown action type: …`, the MESSAGE mutual-exclusivity error) and re-formats it via `format_structural_mismatch_msg(doc, str(e).splitlines()[0], -1, e_nodes)` — again forcing the terse branch.

`error_header = f"Expected {expected}"` is computed at `parser_reporting.py:238-240` *before* the branch, so the per-node `(Error: {error_header})` suffix inside the AST dump is identical on both branches — only the one-line headline sentence differs. `actual_name = format_node_name(primary_node)` is already computed at `parser_reporting.py:236` yet is unused on the `-1` branch: the actionable data is present at the raise site and simply discarded. No existing test asserts the headline sentence (tests assert only the AST-dump `(Error: …)` suffix, e.g. `test_parser_errors.py:47`), so the defect is uncovered.

**UPDATE (turn 8) — model COMPLETE (two-file defect).** An instrumented trace of `format_structural_mismatch_msg` shows BOTH scenarios reach the SAME call site — `markdown_plan_parser.py:281` `_parse_actions` — with `expected='a Level 3 Action Heading'` and `mismatch_idx=-1`. The only difference is the offender payload: `trailing-tags` → `offenders=['Paragraph']`; `stray-h1` → `offenders=[]` (EMPTY).

Root of the empty payload: `_parse_actions` builds the offender list solely from `consume_content_until_next_action` (`parser_infrastructure.py:176`), whose loop **breaks immediately without consuming** when the peeked node is a Heading at level ≤ `H2_LEVEL` (a section boundary):
``````
if isinstance(node, Heading):
    if node.level <= H2_LEVEL:
        break
``````
For `stray-h1` the offending node IS such a heading (a stray `# src/...` H1), so the loop returns `[]` and the offender is silently lost. (A `Paragraph` offender is not a boundary, so it is appended and returned.)

Therefore the defect is TWO-FOLD and needs TWO fixes:

1. **Formatter** (`parser_reporting.py::format_structural_mismatch_msg`): on the `mismatch_idx == -1` branch, when `expected` is a node-type expectation and a real offender exists, interpolate the found node instead of dropping it. (Proven: fixes `trailing-tags`.)
2. **Parser** (`markdown_plan_parser.py::_parse_actions`): seed the offender list with the peeked node when `consume_content_until_next_action` returns empty, so a boundary-Heading offender is never lost. (Proven: with the formatter fix, resolves `stray-h1`.)

Both fixes were jointly verified via the Shadow File methodology (`src/` untouched): real `src/` reproduces the terse headline for BOTH inputs (`exit 1`), while the combined shadow replica (fixed formatter + fixed `_parse_actions`) emits an informative `… but found {node}` headline for BOTH (`exit 0`).

### Discrepancies
- The MRE `trailing-tags` case raised **no error**, contradicting the Symptoms section's claim that trailing `</parameter></invoke>` tags trigger the uninformative headline. (Resolved: two MRE-fidelity defects, not a model error. (a) The tags were appended to a plan ending in a READ **list item**; absent a blank line, CommonMark **lazy continuation** folds the tag lines into the list-item paragraph, so no separate offending node is created. The reported plan ended in a **closing code fence**, which terminates the paragraph context. (b) The tags were spread across two lines; a lone `</parameter>` on its own line is a CommonMark **type-7 HTML block** — not skipped by `_parse_actions` and rendered as an `HtmlBlock`, not a `Paragraph`. The reported AST shows a single `Paragraph: "</parameter></invoke>"`, i.e. both tags on ONE line, which is not a valid single close-tag line and therefore falls through to a `Paragraph`. The MRE is corrected: fenced-ending base + single-line tags.)
- Shadow mode (fixed formatter) fixes `trailing-tags` but leaves `stray-h1` terse (`'Plan content is invalid: a Level 3 Action Heading.'`), contradicting the Causal Model's assumption that one formatter branch governs BOTH reported symptoms. (Resolved: the trace shows both reach the SAME call site (`_parse_actions:281`) with `mismatch_idx=-1`; `stray-h1` passes an EMPTY `offenders=[]` because `consume_content_until_next_action` breaks without consuming a boundary Heading (level ≤ H2), dropping the offender. The formatter fix is therefore necessary-but-insufficient; a second fix in `_parse_actions` must seed the offender list with the peeked node.)

### Investigation History
1. Session opened from the bug report "uninformative validation errors". Case File created. Located the emitting source: `parser_reporting.py:245`.
2. Read `parser_reporting.py:180-300`, `markdown_plan_parser.py:240-320`, `exceptions.py:1-70`. Hypothesis: the terse branch is selected by the `mismatch_idx == -1` sentinel, which `_parse_actions` passes unconditionally, dropping the actual offending node from the headline message. Next: read the remaining formatter internals (`format_node_name`, AST renderer), all call sites, and the existing parser-error tests to pin expected behaviour.
3. Read `parser_reporting.py:1-180`, `markdown_plan_parser.py:1-160`, `test_parser_errors.py`, `test_parser_reporting.py`; ran `git grep` for `InvalidPlanError`/`format_structural_mismatch_msg` call sites and `git log` on `parser_reporting.py`. Confirmed: `InvalidPlanError` is defined at `core/ports/inbound/plan_parser.py:9`; the `-1` sentinel is fed by `_parse_actions` AND by `parse`'s re-wrap of other `InvalidPlanError`s; `error_header` is branch-independent (only the headline differs). Key observation: existing tests assert only the AST-dump `(Error: …)` line, never the headline — the defect is uncovered. Next: build the diagnostic MRE.
4. Created MRE `spikes/debug/03-uninformative-validation-errors-mre.py` (imports the real `MarkdownPlanParser`). First run: `stray-h1` reproduced the defect exactly — `headline : 'Plan content is invalid: a Level 3 Action Heading.'`, `ast_dump : True`. `trailing-tags` raised NO error (MRE infidelity — see Discrepancies, now resolved). Fixing the MRE base to end in a code fence and putting the tags on one line.
5. Refined MRE (fenced-ending base plan via `add_create`; tags on ONE line). Both `trailing-tags` and `stray-h1` now reproduce the exact defect: `headline : 'Plan content is invalid: a Level 3 Action Heading.'`, `ast_dump : True`, script exits 1. `git log -S "Plan content is invalid"` traced the terse phrasing to commit `86ef441d` — a latent design choice, not a recent regression. Next: prove the fix via the Shadow File (`shadow_parser_reporting.py` + MRE `--shadow` mode).
6. Created the shadow replica `spikes/debug/shadow_parser_reporting.py` (faithful copy; the sole deviation is the `mismatch_idx == -1` branch — when `expected` is a node-type expectation and a real offending node exists, emit `Plan content is invalid. Expected …, but found {actual_name}.`) and added a `--shadow` mode to the MRE that re-points `markdown_plan_parser`'s module-global `format_structural_mismatch_msg` at the replica. First shadow run (single compound EXECUTE: real `; echo exit` real; then shadow): real mode reproduced cleanly (`headline : 'Plan content is invalid: a Level 3 Action Heading.'`, `ast_dump : True` for BOTH cases), but the executor aborted the compound shell on the real-mode `SystemExit(1)`, so the `real_exit=$?` echo AND the entire shadow block were never captured. Harness artifact, not a model error. Next: re-run both modes with command-substitution exit-code capture.
7. Shadow verification (harness-robust capture via `set +e` + command substitution). Real mode: both cases still `'Plan content is invalid: a Level 3 Action Heading.'`, `real_exit=1` (bug confirmed against `src/`). Shadow mode SPLIT: `trailing-tags` FIXED → `'Plan content is invalid. Expected a Level 3 Action Heading, but found Paragraph: "</parameter></invoke>".'`; `stray-h1` UNCHANGED → `'Plan content is invalid: a Level 3 Action Heading.'` (`shadow_exit=1`). Conclusion: the formatter fix is NECESSARY for the Paragraph case but INSUFFICIENT for the Heading case — a second call path emits the `stray-h1` terse headline with (apparently) an empty offender payload. Next: instrument the formatter to trace caller + args for `stray-h1`, and read `consume_content_until_next_action`.
8. Ran the instrumented-formatter trace (`spikes/debug/03-trace-formatter-calls.py`) and read `consume_content_until_next_action` (`parser_infrastructure.py:176`). Both scenarios reach `markdown_plan_parser.py:281:_parse_actions` with `expected='a Level 3 Action Heading'`, `mismatch_idx=-1`; `trailing-tags` passes `offenders=['Paragraph']` while `stray-h1` passes `offenders=[]`. Mechanism CONFIRMED: `consume_content_until_next_action` breaks without consuming a Heading at level ≤ H2, returning `[]`, so a boundary-Heading offender is dropped. Defect is two-fold (formatter + `_parse_actions`). Next: build the combined shadow fix (formatter + parser) and re-verify BOTH scenarios.
9. Built and proved the combined two-file fix via the Shadow File methodology (`src/` untouched). Added `spikes/debug/shadow_markdown_plan_parser.py` — a subclass of the real parser overriding only `_parse_actions` to seed `offending_nodes = [node]` when `consume_content_until_next_action` returns empty, and binding the fixed shadow formatter (`spikes/debug/shadow_parser_reporting.py`); EDITed the MRE so `--shadow` selects the fixed parser class. Ran both modes: **real** → both cases `'Plan content is invalid: a Level 3 Action Heading.'`, `ast_dump : True`, `real_exit=1` (bug present); **shadow (fixed replicas)** → both cases fixed, `ast_dump : True`, `shadow_exit=0`: `trailing-tags` → `'Plan content is invalid. Expected a Level 3 Action Heading, but found Paragraph: "</parameter></invoke>".'`; `stray-h1` → `'Plan content is invalid. Expected a Level 3 Action Heading, but found Heading (Level 1): …'.'`. FIX EMPIRICALLY PROVEN for BOTH reported inputs. Next: Alignment gate.
10. Systemic Audit (Phase 4). `git grep` bounded the blast radius of the two-file fix. `consume_content_until_next_action` has exactly TWO callers — `markdown_plan_parser.py::_parse_actions` (the bug site) and `action_parser_complex.py:175` (the RESEARCH parser). The RESEARCH path does NOT rely on the helper for offender reporting (it raises its own `RESEARCH action found no query code blocks.` on empty content), so the boundary-heading offender-drop is unique to `_parse_actions`. `mismatch_idx` is consumed ONLY inside `parser_reporting.py` (the `-1` sentinel is fed by `_parse_actions` AND by `parse`'s re-wrap of non-MRP `InvalidPlanError`s). No test asserts the terse string `Plan content is invalid` (grep: only the definition site `parser_reporting.py:245`), and no `but found` assertion exists on the `-1` path. Conclusion: fix scope is bounded to TWO production files with NO Port/Signature/DTO change and NO hidden test contract. Next: Documentation + Implementation.
11. RED phase. Wrote the behavioural regression test `tests/suites/unit/core/services/test_parser_action_error_messages.py` (two cases mirroring the reported inputs: a mid-stream `Paragraph` offender; a boundary `Heading` offender), driving `MarkdownPlanParser` via `MarkdownPlanBuilder`. Ran it against UNFIXED `src/` → `2 failed`, both emitting `'Plan content is invalid: a Level 3 Action Heading.'`. RED confirmed: the tests capture the defect and are fit to gate the fix.
12. GREEN phase. Applied the empirically proven two-file fix to `src/` (transplanted from the turn-9 combined shadow): (a) `parser_reporting.py::format_structural_mismatch_msg` — on the `mismatch_idx == -1` branch, emit `Plan content is invalid. {error_header}, but found {actual_name}.` when `is_direct and primary_node is not None`, else keep the terse wording (preserving free-form re-wrapped messages); (b) `markdown_plan_parser.py::_parse_actions` — seed `offending_nodes = [node]` when `consume_content_until_next_action` returns empty. Regression test → `2 passed` (GREEN); MRE against the fixed real `src/` → BOTH cases `… but found {node}`, `mre_exit=0`.
13. Integration verification (Phase 6 Step 5). Ran the full suite (`uv run pytest -q`) against the fixed code → `1683 passed, 5 skipped`. No regressions; the shared formatter/parser change is non-breaking. Next: Version Control (teardown + commit).

## Solution

### Root Cause

The plan parser surfaces validation failures through a single shared formatter, `format_structural_mismatch_msg` (`src/teddy_executor/core/services/parser_reporting.py`), which selects its one-line headline from a `mismatch_idx` sentinel:

```python
# parser_reporting.py (current, defective)
if mismatch_idx == -1:
    msg = f"Plan content is invalid: {expected}.\n\n"
else:
    msg = f"Plan structure is invalid. {error_header}, but found {actual_name}.\n\n"
```

The `-1` branch drops `actual_name` — the node actually found — even though it is computed one line above (`actual_name = format_node_name(primary_node)`) and even when `expected` is a concrete node-type expectation. **Two** call paths feed this branch:

1. `_parse_actions` (`markdown_plan_parser.py:280-284`) raises the action-heading error with `mismatch_idx=-1` whenever it meets a node that is neither a Level-3 action heading, a code block, nor a thematic break — e.g. a stray trailing `</parameter></invoke>` paragraph.
2. `parse` (`markdown_plan_parser.py:138-147`) re-wraps any other `InvalidPlanError` (e.g. `Unknown action type: …`) with `mismatch_idx=-1`.

So the actionable diagnosis (`found Paragraph: …`) existed only in the AST dump and was silently dropped from the headline: `Structural error: Plan content is invalid: a Level 3 Action Heading.`

The investigation further revealed a **second, independent** defect hiding behind the first. For a *boundary* offender (a stray `# src/...` H1), `_parse_actions` builds its offender list solely from `consume_content_until_next_action`, whose loop intentionally **breaks without consuming** a Heading at level ≤ H2:

```python
# parser_infrastructure.py::consume_content_until_next_action
if isinstance(node, Heading):
    if node.level <= H2_LEVEL:
        break
```

The helper therefore returns an empty list for that node, so the offender is lost and even a corrected formatter has nothing to print. Hence **two** fixes are required.

### Verified Fix

1. **Formatter** — on the `mismatch_idx == -1` branch, when `expected` is a node-type expectation and a real offending node exists, interpolate it:

```python
# parser_reporting.py::format_structural_mismatch_msg
if mismatch_idx == -1:
    if is_direct and primary_node is not None:
        msg = f"Plan content is invalid. {error_header}, but found {actual_name}.\n\n"
    else:
        msg = f"Plan content is invalid: {expected}.\n\n"
else:
    msg = f"Plan structure is invalid. {error_header}, but found {actual_name}.\n\n"
```

Free-form messages (e.g. `Unknown action type: X`, which does not begin with `a `/`an `/`Heading`/`List`) keep their current self-contained wording, so the re-wrap path is preserved.

2. **Parser** — in `_parse_actions`, seed the offender list with the peeked node when the helper returns empty:

```python
# markdown_plan_parser.py::_parse_actions
offending_nodes = consume_content_until_next_action(stream, self._valid_actions)
if not offending_nodes:          # a section-boundary Heading was left unconsumed
    offending_nodes = [node]
raise InvalidPlanError(
    format_structural_mismatch_msg(
        doc, "a Level 3 Action Heading", -1, offending_nodes
    ),
    offending_nodes=offending_nodes,
)
```

**Evidence (Shadow File methodology — no production code touched):**

- MRE vs. real `src/` → BOTH inputs print `Plan content is invalid: a Level 3 Action Heading.` (`exit 1`, bug reproduced).
- Same MRE vs. the combined shadow (fixed formatter + fixed `_parse_actions`) → BOTH inputs print `Plan content is invalid. Expected a Level 3 Action Heading, but found …` (`exit 0`, fix proven).

### Preventative Measures

**Class:** *a shared diagnostic formatter (or an offender-capture helper) silently drops the actionable "what was actually found" context for a distinct input category, degrading a rich error into a self-referential one.*

1. **Preserve the found node on every branch.** The formatter must never emit a node-type expectation without also naming the node actually encountered when one exists.
2. **Never lose an offender at the raise site.** When an offender-capture helper legitimately declines to consume a boundary token, the caller must retain that token as the offender.
3. **Pin the headline contract with a behavioural regression test.** Assert on the *surfaced headline* (not just the AST dump) for both offender shapes (mid-stream `Paragraph`, boundary `Heading`), so the informative wording can never silently regress. The existing suites only asserted the branch-independent AST-dump `(Error: …)` suffix — a blind spot that let this defect persist.

### Systemic Audit (Phase 4)

- **Blast radius (bounded):** `consume_content_until_next_action` has exactly two callers — `_parse_actions` (the bug site) and `action_parser_complex.py:175` (RESEARCH), which reports its own `RESEARCH action found no query code blocks.` and does not depend on the helper for offender reporting. `mismatch_idx` is consumed only inside `parser_reporting.py`. No Port/Signature/DTO change; no test pins the terse string `Plan content is invalid`.
- **Categorical siblings:** none — the drop was localized to the two sites above.

### Disposition

**Trivial, localized direct fix.** One formatter branch plus one caller guard; no interface change. Executed directly via Phase 6 (no Vertical Slice required).
