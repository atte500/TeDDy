# Slice: Implement `trafilatura` for Web Scraping

- **Status:** Done
- **Milestone:** [08-core-refactoring-and-enhancements](/docs/project/milestones/08-core-refactoring-and-enhancements.md)
- **Spec:** None

## 1. Business Goal & Interaction Sequence
**Goal:** To improve the quality of context gathered from web pages by replacing the existing `markdownify`-based web scraper with a more sophisticated one using the `trafilatura` library. This new implementation should extract the main content from a URL, stripping away ads, navigation, and other boilerplate, thus providing cleaner, more relevant information to the AI agents.

**Interaction:**
1.  An AI agent generates a plan with a `READ` action targeting a URL.
2.  The user approves the action.
3.  The system's `WebScraperAdapter` uses `trafilatura` to fetch the URL's content.
4.  `trafilatura` processes the HTML, extracts the main article/content, and converts it to Markdown.
5.  The system returns the clean Markdown content in the execution report.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Scraping a Content-Heavy Article
**Given** a URL pointing to a typical news article or blog post with significant boilerplate (headers, footers, sidebars)
**When** the `WebScraperAdapter` processes the URL
**Then** the resulting Markdown should contain the main article text
**And** it should NOT contain common boilerplate text from the navigation bars, sidebars, or footers.

### Scenario 2: Dependency Replacement
**Given** the project's dependencies listed in `pyproject.toml`
**When** the file is inspected
**Then** `trafilatura` should be listed as a main dependency
**And** `markdownify` should NOT be listed as a dependency.

## 3. User Showcase

This is an improvement to the quality of data provided to the AI and is not directly user-facing. Verification can be done by running the `WebScraperAdapter`'s integration tests, which will use realistic HTML mocks to assert that boilerplate is removed while main content is preserved.

## 4. Architectural Changes

The `WebScraperAdapter` will be refactored to implement a more robust, hybrid scraping strategy. This decision was validated through a series of technical spikes that proved the limitations of a single-library approach.

The new implementation will follow a "smart router" pattern:
1.  **For GitHub URLs:** The adapter will detect URLs pointing to files on `github.com` (containing `/blob/`), transform them to their corresponding `raw.githubusercontent.com` equivalent, and fetch the raw text content directly. This guarantees perfect fidelity for source code.
2.  **For all other URLs:** The adapter will use the `trafilatura` library to intelligently extract the main content of the page, stripping away boilerplate like ads, navigation, and footers before converting the result to Markdown.

This approach ensures the system uses the best tool for each specific context. The detailed implementation contract is specified in the updated component design document.

- **Component Contract:** [WebScraperAdapter Design](/docs/architecture/adapters/outbound/web_scraper_adapter.md)

## 5. Scope of Work

1.  **Manage Dependencies (Atomic Change):**
    -   Run `poetry remove markdownify` to remove the old library.
    -   Run `poetry add trafilatura` to add the new library as a main dependency. This ensures the environment change is atomic with the code changes.
2.  **Refactor `WebScraperAdapter`:**
    -   Open `src/teddy_executor/adapters/outbound/web_scraper_adapter.py`.
    -   Update the import from `markdownify` to `trafilatura`.
    -   Update the implementation to match the new contract defined in the [WebScraperAdapter Design](/docs/architecture/adapters/outbound/web_scraper_adapter.md).
    -   Implement the "smart router" logic to detect and transform GitHub URLs.
    -   Use `requests` to fetch the raw content for transformed GitHub URLs.
    -   Use `trafilatura.extract` with `output_format='markdown'` for all other URLs.
3.  **Update Integration Tests:**
    -   Open `tests/integration/adapters/outbound/test_web_scraper_adapter.py`.
    -   Delete or refactor existing tests that rely on `markdownify`.
    -   Add a new test case to verify that a GitHub file URL is correctly transformed and its raw content is fetched perfectly.
    -   Ensure all tests pass.

## Implementation Summary

The `WebScraperAdapter` was successfully refactored to use `trafilatura` instead of `markdownify`. The implementation followed a standard TDD workflow, starting with new integration tests that codified the desired behavior for handling GitHub URLs and stripping boilerplate from article content.

A significant challenge arose during the process: `trafilatura`'s content extraction algorithm proved more sophisticated than `markdownify`'s, causing it to return empty strings for the overly simplistic HTML mocks used in the existing acceptance tests. This introduced a regression. The issue was resolved by following the established recovery protocol:
1. A spike was conducted to verify that `trafilatura`'s `favor_precision=True` setting, combined with a more realistic HTML structure in the mock, would yield the correct behavior.
2. This validated learning was applied to both the integration tests (to make them more robust) and the failing acceptance test (to fix the regression).

The final implementation is robust and well-tested, fulfilling all acceptance criteria. A minor CI warning regarding deprecated pre-commit hooks was also discovered and fixed in a separate `chore` commit.
