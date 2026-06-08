# Slice: 02-16-Refactor Parser Complexity

- **Status:** In Progress
- **Type:** Refactor
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)
- **Component Docs:**
  - [MarkdownPlanParser](/docs/architecture/core/services/markdown_plan_parser.md)
  - [Parser Infrastructure](/docs/architecture/core/services/parser_infrastructure.md)

## Business Goal
Reduce the C901 cyclomatic complexity of `MarkdownPlanParser.parse()` from 10 to below the threshold of 9 by extracting the mutual exclusivity check and section routing logic into smaller, named helper methods.

## Scenarios
(Scenarios are optional for Refactor types. Behavioral coverage is already provided by existing parser tests.)

## Edge Cases
(None anticipated – extraction is purely mechanical, preserving all existing behavior.)

## Deliverables

This refactoring consists of three purely mechanical extractions that preserve all public contracts. Existing tests (e.g., `test_parser_message_protocol.py`, `test_bug_17_message_validation.py`, and all parser tests) already cover the extracted behavior, so no new harness deliverables are needed.

1. [▶] **Logic** - Extract `_validate_mutual_exclusivity(self, doc: Document) -> None` from `parse` method (current lines 93-101). The extracted method scans `doc.children` for H2 headings, checks for both "Action Plan" and "Message", and raises `InvalidPlanError` if both are present.
2. [ ] **Logic** - Extract `_parse_section_content(self, stream: _PeekableStream, clean_content: str, section_heading: Heading, doc: Document) -> List[ActionData]` from `parse` method (current lines 103-132). The extracted method checks the section heading text: if "Message" calls `parse_message_action` (with raw content extracted from `clean_content`), otherwise calls `self._parse_actions(stream, doc)`.
3. [ ] **Logic** - Refactor `parse` method: Call the two new helpers in place of the extracted code, ensuring the method complexity drops below 9.

## Implementation Notes

No new tests required – existing parser tests already cover the extracted logic. The extraction is purely mechanical with zero behavioral change. Any outdated inline comments are removed as part of the extraction; no separate cleanup step is needed. The standard test suite is run by the developer during implementation to confirm no regressions.

## Implementation Plan

### Changes Required

**File: `src/teddy_executor/core/services/markdown_plan_parser.py`**

The `parse` method (approximately lines 61-145) currently has complexity 10. Two clear extraction targets exist:

1. **Mutual exclusivity check (lines 93-101):**
   ```python
   # Mutual Exclusivity Check
   from mistletoe.block_token import Heading
   doc_children = doc.children or []
   h2_headings = [n for n in doc_children if isinstance(n, Heading) and n.level == H2_LEVEL]
   h2_texts = [get_child_text(h) for h in h2_headings]
   if "Action Plan" in h2_texts and "Message" in h2_texts:
       raise InvalidPlanError(...)
   ```
   → Extract to `_validate_mutual_exclusivity(self, doc: Document) -> None`

2. **Section routing (lines 103-132):**
   ```python
   section_name = get_child_text(section_heading).strip()
   if "Message" in section_name:
       raw_content = None
       start_line = getattr(section_heading, "line_number", None)
       if start_line is not None and start_line > 0:
           lines = clean_content.splitlines(keepends=True)
           if start_line < len(lines):
               raw_content = "".join(lines[start_line:]).lstrip("\n")
       actions = [parse_message_action(stream, node=section_heading, raw_content=raw_content)]
   else:
       actions = self._parse_actions(stream, doc)
   ```
   → Extract to `_parse_section_content(self, stream, clean_content, section_heading, doc) -> List[ActionData]`

**No test changes required.** The existing test suite (e.g., `test_parser_message_protocol.py`, `test_bug_17_message_validation.py`, and all parser tests) already covers the mutual exclusivity and section routing behavior. Since the extraction is purely mechanical and preserves all public contracts, these tests serve as the regression safety net.

### Test Strategy

No new tests needed. Existing parser tests (mutual exclusivity, message parsing, action plan parsing) already cover the extracted logic. Standard test suite execution during implementation verifies no regressions.

### Complexity Impact

After extraction, the `parse` method will contain:
- Call to `_validate_mutual_exclusivity(doc)`: 1 statement, no branching.
- Call to `_parse_section_content(...)`: 1 statement, no branching.
- The remaining flow (title extraction, metadata, etc.) is already simple.

Estimated final complexity: 5-6 (well below threshold of 9).
