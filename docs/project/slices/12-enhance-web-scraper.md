# Slice: Enhance Web Scraper to Bypass Anti-Scraping Measures

- **Status:** Planned
- **Milestone:** [08-core-refactoring-and-enhancements](/docs/project/milestones/08-core-refactoring-and-enhancements.md)
- **Spec:** None

## 1. Business Goal & Interaction Sequence
**Goal:** To improve the reliability of the `WebScraperAdapter` by implementing a fallback mechanism that can handle websites (like Medium.com) that block standard `requests` calls with a `403 Forbidden` error.

**Interaction:**
1.  An AI agent generates a plan with a `READ` action targeting a URL known to block simple scrapers.
2.  The user approves the action.
3.  The system's `WebScraperAdapter` first attempts to fetch the content using `requests.get`.
4.  The request fails with a `403 Forbidden` error.
5.  The adapter automatically falls back to using `trafilatura.fetch_url` to re-attempt the download.
6.  The fallback succeeds, and `trafilatura` extracts the content.
7.  The system returns the clean Markdown content in the execution report.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Successfully Scrapes a Protected Site
**Given** a URL that is known to return a `403 Forbidden` error to standard `requests` calls
**When** the `WebScraperAdapter` processes the URL
**Then** the adapter should successfully return the main content of the page
**And** the initial request should be mocked to return a 403 status code
**And** a second request using the fallback mechanism should be observed.

## 3. Architectural Changes

The `WebScraperAdapter` will be refactored to implement a `try-except` fallback strategy. This decision was made to optimize for performance by using the fastest method first and only escalating to a more robust method when necessary.

-   **Primary Method:** The adapter will first attempt to fetch content using a standard `requests.get()` call. This is the "fast path" for the majority of permissive websites.
-   **Fallback Method:** If the primary method results in a `requests.exceptions.HTTPError` with a 403 status code, the adapter will catch this specific exception. It will then automatically re-attempt the fetch using `trafilatura.fetch_url`, which is more robust at emulating a real browser.

This approach balances performance for the common case with reliability for edge cases.

- **Component Contract:** [WebScraperAdapter Design](/docs/architecture/adapters/outbound/web_scraper_adapter.md) (Note: This document will need to be updated by the implementing agent to reflect the new fallback logic).

## 4. Scope of Work

1.  **Create Failing Integration Test:**
    -   Open `tests/integration/adapters/outbound/test_web_scraper_adapter.py`.
    -   Add a new test case that mocks a `403 Forbidden` response for a `requests.get()` call.
    -   The test should assert that despite the initial failure, the adapter successfully returns content by using a fallback mechanism.
2.  **Implement Fallback Logic:**
    -   Open `src/teddy_executor/adapters/outbound/web_scraper_adapter.py`.
    -   Refactor the `get_content` method to include the `try-except` block.
    -   The `except` block should specifically catch `requests.exceptions.HTTPError` and check for a `403` status code before initiating the fallback.
    -   The fallback should call `trafilatura.fetch_url` and then process the result with `trafilatura.extract`.
    -   Ensure all tests, including the new one, pass.
3.  **Refactor and Finalize:**
    -   Refactor the code for clarity.
    -   Update the component design document `docs/architecture/adapters/outbound/web_scraper_adapter.md` to describe the new fallback strategy.
