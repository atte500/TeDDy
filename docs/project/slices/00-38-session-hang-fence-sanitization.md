# Slice: Session-Hang Fence Sanitization
- **Status:** In Progress
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

- [▶] **Logic** — Add `strip_trailing_open_fence(content)` to `core/utils/markdown.py`, porting the `_FENCE_RE` walk from `spikes/debug/session-hang/replica_embed_sanitizer.py`. Add unit tests to `tests/suites/unit/core/utils/test_markdown_utils.py` covering the preserve/collapse matrix from `spikes/debug/session-hang/06-fence-detector-matrix.py`.
- [ ] **Logic** — Add `embed_in_fence(content, lang)` to `core/utils/markdown.py` that sanitizes via `strip_trailing_open_fence`, then fences via `get_fence_for_content`, returning `f"{fence}{lang}\n{content}\n{fence}"`. Add unit tests covering sanitized and balanced content.
- [ ] **Migration** — Route `ContextService._format_session_history` through `embed_in_fence`. Add an end-to-end test in `tests/suites/unit/core/services/test_context_service.py` driving `get_context` with a degenerate session-history file, proving the section is bounded.
- [ ] **Migration** — Route `ContextService._format_workspace_contents` through `embed_in_fence`. Add an end-to-end test driving `get_context` with a degenerate workspace file, proving the section is bounded.
- [ ] **Cleanup** — Update `docs/architecture/core/services/context_service.md` to record the shared sanitize-then-fence seam. Run `git grep -n "get_fence_for_content" -- src/teddy_executor/core/services/context_service.py` and confirm both embed sites route through `embed_in_fence`.

## Implementation Notes
- **No Wiring deliverable.** The fix reuses the existing `ContextService` embed seam and introduces no new boundary, so no hardcoded-skeleton tracer bullet applies. This mirrors slice `00-37`'s documented precedent. The end-to-end acceptance coverage is carried by the session-history migration deliverable.
- **Scope of the shared seam.** Case file 07 scopes the fix to the two context embed sites (`_format_session_history`, `_format_workspace_contents`). The other `get_fence_for_content` call sites (`parser_reporting.py`, `session_lifecycle_manager.py`, `validation_rules/edit.py`, `markdown_report_formatter.py`) are out of scope for this slice and are recorded for a possible roadmap entry.
- **`get_fence_for_content` is unchanged.** The fix sanitizes the content BEFORE the fence is derived, so no fence-clamping logic is needed and no magic number is introduced.
- **Reference implementation.** The detector is proven in `spikes/debug/session-hang/replica_embed_sanitizer.py`; port the `_FENCE_RE` walk into `core/utils/markdown.py`.
- **Two strip behaviours.** `_format_session_history` strips leading/trailing whitespace before fencing; `_format_workspace_contents` does not. `embed_in_fence` sanitizes only (it does not strip), so each caller keeps its existing whitespace behaviour.

## Verification
- [ ] **CLI:** Run `make test` and verify the full suite passes (green-to-green).
- [ ] **Unit:** Run `uv run pytest tests/suites/unit/core/utils/test_markdown_utils.py -q` and verify the preserve/collapse matrix passes.
- [ ] **Unit:** Run `uv run pytest tests/suites/unit/core/services/test_context_service.py -q` and verify the bounded session-history and workspace tests pass.
- [ ] **CLI:** Run `uv run python spikes/debug/session-hang/05-backtick-strip-mre.py` and verify the collapse assertion and the byte-for-byte preservation assertions pass.
- [ ] **Interactive:** Resume a session whose prior plan contains an unclosed giant backtick run and verify the session advances instead of hanging.
