# Slice: Session-Hang Fence Sanitization
- **Status:** Completed
- **Milestone:** Ad-hoc (not tracked in the Roadmap per PROJECT.md)
- **Depends On:** None
- **Specs:** N/A (defect remediation; no permanent system invariant changes)
- **Prototype:** N/A (case file 07 is Resolved; the sanitizer is sandbox-proven)
- **Component Docs:** [ContextService](/docs/architecture/core/services/context_service.md)
- **Scope Slug:** `fence-sanitization`

## Business Goal
Prevent an interactive session from hanging when embedded session-history or workspace content contains a trailing unclosed code fence. Strip the dangling fence before computing the dynamic wrapper fence so the assembled context payload stays bounded and the session remains interruptible.

## Scenarios
> As a user, I want a session with a degenerate plan to keep running so that a single LLM degeneration does not hang the session.

```gherkin
Given a session-history file containing an unclosed giant backtick run
When the context payload is assembled
Then the embedded session-history section is bounded and no fence amplification occurs
```

```gherkin
Given a workspace file containing an unclosed giant backtick run
When the context payload is assembled
Then the embedded workspace section is bounded and no fence amplification occurs
```

## Edge Cases
- **Preserve balanced backtick fence**: If content contains a closed triple-backtick block, then it is returned byte-for-byte unchanged, because a balanced fence is legitimate Markdown.
- **Preserve balanced tilde fence**: If content contains a closed triple-tilde block, then it is returned byte-for-byte unchanged.
- **Preserve nested fence**: If content is a 4-backtick fence wrapping a 3-backtick fence, then it is returned byte-for-byte unchanged, because the outer fence closes the block.
- **Preserve inline code**: If content contains a double-backtick run on its own line or a single-backtick run mid-line, then it is unchanged, because a run shorter than three is inline code, not a fence.
- **Preserve indented fence**: If a fence is indented by up to three spaces, then it is still recognised and balanced content is unchanged.
- **Collapse unclosed backtick run**: If content ends inside an open backtick fence, then the dangling opening fence line is removed.
- **Collapse unclosed tilde run**: If content ends inside an open tilde fence, then the dangling opening fence line is removed.
- **Collapse unclosed opener with body**: If content opens a fence, includes a body, and never closes it, then the opening fence line is removed.
- **No fences**: If content has no fence lines, then it is returned byte-for-byte unchanged.
- **Empty content**: If content is empty, then `embed_in_fence` yields a minimal fenced block.

## Key Unknowns

**Taxonomy:** see template.

- [x] [Technical] Fence-amplification root cause and sanitizer reliability: RESOLVED — case file 07 is Resolved; the MRE (`spikes/debug/session-hang/05-backtick-strip-mre.py`) and the 10-case matrix (`spikes/debug/session-hang/06-fence-detector-matrix.py`) prove the detector collapses unclosed runs and preserves balanced fences byte-for-byte. Design Sensitivity: if the detector were unreliable, the shared helper would need a fallback; it is proven, so no fallback is needed.

## Impact
1. `[EXPAND]` `core/utils/markdown.py` — add `strip_trailing_open_fence(content)` and `embed_in_fence(content, lang)`. `get_fence_for_content` is unchanged.
2. `[MIGRATE]` `ContextService._format_session_history` — route the session-history embed through `embed_in_fence`.
3. `[MIGRATE]` `ContextService._format_workspace_contents` — route the workspace embed through `embed_in_fence`.
4. `[CONTRACT]` none — no port signature changes.

## Deliverables

- [x] **Logic** — Add `strip_trailing_open_fence(content)` to `core/utils/markdown.py`, porting the `_FENCE_RE` walk from `spikes/debug/session-hang/replica_embed_sanitizer.py`. Add unit tests to `tests/suites/unit/core/utils/test_markdown_utils.py` covering the preserve/collapse matrix from `spikes/debug/session-hang/06-fence-detector-matrix.py`.
- [x] **Logic** — Add `embed_in_fence(content, lang)` to `core/utils/markdown.py` that sanitizes via `strip_trailing_open_fence`, then fences via `get_fence_for_content`, returning `f"{fence}{lang}\n{content}\n{fence}"`. Add unit tests covering sanitized and balanced content.
- [x] **Migration** — Route `ContextService._format_session_history` through `embed_in_fence`. Add an end-to-end test in `tests/suites/unit/core/services/test_context_service.py` driving `get_context` with a degenerate session-history file, proving the section is bounded.
- [x] **Migration** — Route `ContextService._format_workspace_contents` through `embed_in_fence`. Add an end-to-end test driving `get_context` with a degenerate workspace file, proving the section is bounded.
- [x] **Cleanup** — Update `docs/architecture/core/services/context_service.md` to record the shared sanitize-then-fence seam. Run `git grep -n "get_fence_for_content" -- src/teddy_executor/core/services/context_service.py` and confirm both embed sites route through `embed_in_fence`.

## Implementation Notes
- **No Wiring deliverable.** The fix reuses the existing `ContextService` embed seam and introduces no new boundary, so no hardcoded-skeleton tracer bullet applies. This mirrors slice `00-37`'s documented precedent. The end-to-end acceptance coverage is carried by the session-history migration deliverable.
- **Scope of the shared seam.** Case file 07 scopes the fix to the two context embed sites (`_format_session_history`, `_format_workspace_contents`). The other `get_fence_for_content` call sites (`parser_reporting.py`, `session_lifecycle_manager.py`, `validation_rules/edit.py`, `markdown_report_formatter.py`) are out of scope for this slice and are recorded for a possible roadmap entry.
- **`get_fence_for_content` is unchanged.** The fix sanitizes the content BEFORE the fence is derived, so no fence-clamping logic is needed and no magic number is introduced.
- **Reference implementation.** The detector is proven in `spikes/debug/session-hang/replica_embed_sanitizer.py`; port the `_FENCE_RE` walk into `core/utils/markdown.py`.
- **Two strip behaviours.** `_format_session_history` strips leading/trailing whitespace before fencing; `_format_workspace_contents` does not. `embed_in_fence` sanitizes only (it does not strip), so each caller keeps its existing whitespace behaviour.

### Deliverable 1 — As-Built (strip_trailing_open_fence)
- **Implementation:** added the `_FENCE_RE` module constant and `strip_trailing_open_fence(content)` to `core/utils/markdown.py`, immediately after `get_fence_for_content`, porting the fence-walk verbatim from `spikes/debug/session-hang/replica_embed_sanitizer.py`. `get_fence_for_content` is unchanged.
- **Test coverage:** added the parameterized preserve/collapse matrix (10 preserve cases, 4 collapse cases) to `tests/suites/unit/core/utils/test_markdown_utils.py`, ported from `spikes/debug/session-hang/06-fence-detector-matrix.py`. The file imports `strip_trailing_open_fence` from the production module, so no shadow logic exists.
- **Red step:** the new tests failed at collection with `ImportError: cannot import name 'strip_trailing_open_fence' from 'teddy_executor.core.utils.markdown'`, proving the test-first state.
- **Green step:** `uv run pytest tests/suites/unit/core/utils/test_markdown_utils.py -q` reported `19 passed`.
- **Integration gate:** `make test` reported the full suite green (1788 passed, 5 skipped), confirming the additive helper is regression-free.
- **No deviation from the replica:** the port is byte-for-byte; no signature or semantic change was required.

### Deliverable 2 — As-Built (embed_in_fence)
- **Implementation:** added `embed_in_fence(content, lang)` to `core/utils/markdown.py`, immediately after `strip_trailing_open_fence`. It composes the existing helpers: `sanitized = strip_trailing_open_fence(content)`, then `fence = get_fence_for_content(sanitized)`, then returns `f"{fence}{lang}\n{sanitized}\n{fence}"`. `get_fence_for_content` is unchanged.
- **Sanitize-only contract:** `embed_in_fence` sanitizes only and does NOT strip whitespace, so each caller keeps its own whitespace behaviour (`_format_session_history` strips before calling; `_format_workspace_contents` does not).
- **Test coverage:** added three tests to `tests/suites/unit/core/utils/test_markdown_utils.py` — a sanitized giant backtick run, balanced content wrapped in a longer fence, and empty content yielding a minimal block. The file imports `embed_in_fence` from the production module, so no shadow logic exists.
- **Red step:** the new tests failed at collection with `ImportError: cannot import name 'embed_in_fence' from 'teddy_executor.core.utils.markdown'`, proving the test-first state.
- **Green step:** `uv run pytest tests/suites/unit/core/utils/test_markdown_utils.py -q` reported `22 passed`.
- **Integration gate:** `make test` reported the full suite green (1791 passed, 5 skipped), confirming the additive seam is regression-free.
- **No local refactor required:** the function is a three-line pure composition with no duplicated literal, no magic number, and no shadow logic.

### Deliverable 3 — As-Built (session-history embed migration)
- **Implementation:** routed `ContextService._format_session_history` through the shared `embed_in_fence` helper. The two-line composition (`fence = get_fence_for_content(content_str)` plus the f-string assembly) was replaced by a single `parts.append(embed_in_fence(content_str, lang))`. The `embed_in_fence` import was added to the module's `markdown` import block.
- **Whitespace behaviour preserved:** `_format_session_history` keeps its `content_str = content.strip()` call before delegating, so the sanitize-only contract of `embed_in_fence` is respected.
- **`get_fence_for_content` retained:** the import stays because `_format_workspace_contents` still uses it (the next deliverable migrates that site), so no dead import exists.
- **Test coverage:** added `test_get_context_bounds_degenerate_session_history_fence` to `tests/suites/unit/core/services/test_context_service.py`, driving `get_context` with a `01/plan.md` containing an unclosed 10,000-backtick run and asserting the assembled section is bounded.
- **Red step:** the new test failed with the predicted `AssertionError` (`1 failed, 15 passed`); the traceback showed the unbounded path deriving a 10,001-backtick wrapper fence.
- **Green step:** `uv run pytest tests/suites/unit/core/services/test_context_service.py -q` reported `16 passed`.
- **Integration gate:** `make test` reported the full suite green (1792 passed, 5 skipped), confirming the migration is regression-free.
- **No local refactor required:** the change is a minimal substitution with no duplicated literal, magic number, or shadow logic.

### Deliverable 4 — As-Built (workspace-contents embed migration)
- **Implementation:** routed `ContextService._format_workspace_contents` through the shared `embed_in_fence` helper. The two-line composition (`fence = get_fence_for_content(content)` plus the f-string assembly) was replaced by a single `parts.append(embed_in_fence(content, lang))`.
- **Import pruned:** dropped the now-unused `get_fence_for_content` import from the module's `markdown` import block, because line 400 was its only remaining consumer in this file.
- **Whitespace behaviour preserved:** `_format_workspace_contents` does not strip, so the sanitize-only contract of `embed_in_fence` is respected.
- **Test coverage:** added `test_get_context_bounds_degenerate_workspace_fence` to `tests/suites/unit/core/services/test_context_service.py`, driving `get_context` with a non-session `degenerate.py` containing an unclosed 10,000-backtick run and asserting the `## Resource Contents` section is bounded.
- **Local Flaw resolved:** the existing `test_get_context_uses_dynamic_fences_for_safe_encapsulation` used malformed content (a mid-line opener plus a trailing lone fence). The migration strips that dangling fence, so the test's content was changed to a balanced triple-backtick block and its assertion was updated to the balanced-block expectation, preserving its dynamic-fence-sizing intent.
- **Red step:** the new test failed with the predicted `AssertionError` (`1 failed, 16 passed`); the traceback showed the unbounded path deriving a 10,001-backtick wrapper fence.
- **Green step:** `uv run pytest tests/suites/unit/core/services/test_context_service.py -q` reported `17 passed`.
- **Integration gate:** `make test` reported the full suite green (1793 passed, 5 skipped), confirming the migration is regression-free.
- **No local refactor required:** both embed sites now route through the shared seam, and no duplicated literal, magic number, or shadow logic remains.

### Deliverable 5 — As-Built (ContextService component-doc cleanup)
- **Documentation:** added the "Content Embedding & Fence Sanitization" section to `docs/architecture/core/services/context_service.md`. It names both embed sites (`_format_session_history`, `_format_workspace_contents`), the sanitize-then-fence composition (`strip_trailing_open_fence` then `get_fence_for_content`), the byte-for-byte preservation of well-formed Markdown, and the two distinct whitespace behaviours.
- **Heading renumbered:** the trailing "Implementation Notes" heading moved from section 6 to section 7 to keep the document's section sequence monotonic.
- **Verification:** the deliverable grep reports no `get_fence_for_content` match in `context_service.py` and three `embed_in_fence` matches (import line 7, call sites 399 and 474), confirming both embed sites route through the shared seam.
- **Integration gate:** `make test` reported the full suite green (1793 passed, 5 skipped), confirming the doc-only change is regression-free.
- **No local refactor required:** the deliverable is a documentation section only; no production code changed.

## Verification
- [ ] **CLI:** Run `make test` and verify the full suite passes (green-to-green).
- [ ] **Unit:** Run `uv run pytest tests/suites/unit/core/utils/test_markdown_utils.py -q` and verify the preserve/collapse matrix passes.
- [ ] **Unit:** Run `uv run pytest tests/suites/unit/core/services/test_context_service.py -q` and verify the bounded session-history and workspace tests pass.
- [ ] **CLI:** Run `uv run python spikes/debug/session-hang/05-backtick-strip-mre.py` and verify the collapse assertion and the byte-for-byte preservation assertions pass.
- [ ] **Interactive:** Resume a session whose prior plan contains an unclosed giant backtick run and verify the session advances instead of hanging.
