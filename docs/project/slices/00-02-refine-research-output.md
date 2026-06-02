# Slice: Refine Research Output Format

- **Status:** Completed
- **Type:** Refactor
- **Milestone:** N/A
- **Specs:** [docs/project/specs/report-format.md](/docs/project/specs/report-format.md)

## Business Goal
Improve the readability and scannability of research results in the execution report by aligning them with the "Action Log" visual language used for other actions (like EXECUTE). This replaces the dense code-blocked layout with a structured, link-free metadata list.

## Scenarios
> As an agent reviewing research results, I want a structured layout that explicitly lists URLs and uses standard metadata bullet points so that I can easily scan and refer to results in subsequent turns.
```gherkin
Given a successful RESEARCH action with multiple queries and results
When the execution report is rendered
Then each query should be a Level 4 heading
And each result should be a numbered item starting with a raw URL
And the Title and Description should be nested bullet points
And no Markdown links ([text](url)) should be used for the results
```

## Edge Cases
- **Long URLs/Descriptions**: Ensure the indentation and bullet points handle wrapping gracefully.
- **Empty Results**: Ensure the "No results found" or empty list state is still handled within the new structure.

## Deliverables
- [x] **Wiring** - Update `src/teddy_executor/core/services/templates/execution_report.md.j2` and align `tests/suites/unit/core/services/test_formatter_action_logs.py`.
- [x] **Cleanup** - Update any identified integration or acceptance tests asserting on research output formatting.

## Implementation Notes
- **Refined Layout**: Replaced dense code-blocked layout for research results with Level 4 headings for queries and bulleted metadata for results (Title/Description).
- **Indentation**: Used 3-space indentation for bulleted metadata to ensure proper Markdown nesting and readability.
- **Raw URLs**: URLs are now rendered as raw text in backticks to facilitate easy copying and direct referral without hidden links.
- **Verification**: Global test suite passed, confirming that most tests either don't assert on exact formatting or use resilient parsers.

## Implementation Plan
1. **Template Refactor**:
   - Locate the `RESEARCH` action rendering logic in `execution_report.md.j2`.
   - Replace the `**Query:**` bolding with `#### Query: "{{ qr['query'] }}"`.
   - Update the results loop to output the `1. URL` followed by `- **Title:** ...` and `- **Description:** ...`.
2. **Test Alignment**:
   - Run the test suite to identify all tests asserting on the old ` ```description ` format.
   - Update assertions to match the new bulleted metadata structure.
3. **Verification**:
   - Manually verify a rendered report (if possible via a spike or by checking test output) to ensure no unexpected newlines or formatting glitches.

## Implementation Notes
- **Constraint**: No embedded links. The user explicitly requested that the URL be visible as raw text, not hidden behind a title link.
- **Labeling**: Use `Description` (Title Case) as the label for the snippet.

## Example Output
Below is the exact expected rendering for a RESEARCH action with multiple results:

#### Query: "search query one"
1. `https://example.com/article-one`
   - **Title:** First Result Title
   - **Description:** This is the snippet for the first result...
2. `https://example.com/article-two`
   - **Title:** Second Result Title
   - **Description:** This is the snippet for the second result...

#### Query: "search query two"
1. `https://example.com/article-three`
   - **Title:** Third Result Title
   - **Description:** This is the snippet for the third result...

*(Use `READ` on the URLs above to inspect the full content)*
