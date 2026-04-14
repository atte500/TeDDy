# Vertical Slice: GitHub Issue Comment Scraping
- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Specs:** [web-scraper-adapter](../architecture/adapters/outbound/web_scraper_adapter.md)
- **Prototype:** [prototypes/github_issue_scraper_spike.py](/prototypes/github_issue_scraper_spike.py)

## Business Goal
As a developer using TeDDy, I want the `context` and `research` commands to capture the full conversation of a GitHub issue or pull request, so that the AI has the complete context of bug reports and discussions.

### Deliverables
- [x] **Contract** - Update `WebScraper` port to accept optional extraction hints (Internal).
- [ ] **Harness** - Add integration test for GitHub Issue/PR scraping in `tests/integration/adapters/outbound/test_web_scraper_adapter.py`.
- [ ] **Logic** - Implement `_extract_github_conversation` in `WebScraperAdapter` using the hybrid JSON/HTML strategy.
- [ ] **Wiring** - Add routing logic in `get_content` to detect `/issues/` or `/pull/` URLs and invoke the specialized extractor.

## Scenarios

> As a developer, I want to scrape a GitHub issue URL so that I can see the issue description and all subsequent comments in Markdown.

### Scenario: Successfully extract issue content and comments
- **Given** a valid GitHub issue URL (e.g., `https://github.com/octocat/Spoon-Knife/issues/1`)
- **When** the scraper is invoked
- **Then** the output should contain the issue title
- **And** the output should contain the main issue body
- **And** the output should contain all visible comment bodies
- **And** the formatting should be clean Markdown

### Scenario: Fallback for non-issue GitHub URLs
- **Given** a GitHub URL that is not an issue or PR (e.g., `https://github.com/octocat/Spoon-Knife/labels`)
- **When** the scraper is invoked
- **Then** it should fallback to the standard `trafilatura` extraction logic

## Delta Analysis
The current `WebScraperAdapter` uses `trafilatura` for all non-blob URLs. `trafilatura` fails on GitHub's complex React-hydrated comment structures.

### Integration Strategy
1.  **Routing Seam:** In `get_content(self, url: str)`, add a check for `github.com/.../issues/` and `github.com/.../pull/`.
2.  **Hybrid Scraper:** Implement `_extract_github_conversation(self, html: str)` which performs a two-pass extraction:
    -   **Pass 1 (JSON):** Locates `script[data-target="react-app.embeddedData"]`. Uses a recursive search for the `issue` or `pullRequest` key to find the primary data container and `edges` for the timeline. This captures high-fidelity Markdown and metadata.
    -   **Pass 2 (HTML Fallback):** If JSON extraction is partial, uses BeautifulSoup to scrape `.markdown-title` and `.markdown-body` / `.comment-body` blocks.
3.  **Dependencies:** No new dependencies required. Uses the existing `beautifulsoup4` and standard `json` library.
4.  **Performance:** Extraction is purely CPU-bound (logic-only) and maintains the CLI's responsiveness (<500ms for parsing).

### Risks Mitigated
-   **DOM Brittleness:** Recursive JSON search bypasses GitHub's frequent class name changes and deep nesting in the React-rendered DOM.
-   **Missing Comments:** Hybrid fallback ensures that even if specific comments are lazy-loaded or fragmented, we capture visible content from the HTML.
- **Tooling:** Use `beautifulsoup4` and `json` (standard library).
- **Integration:** Inject a router in `WebScraperAdapter.get_content` that detects GitHub Issue/PR URLs and routes to the JSON extractor.

## Guidelines for Implementation

### Hybrid Extraction Algorithm
1.  **Identify Target URL:** Use regex or string inspection to detect `/issues/` or `/pull/` in GitHub URLs.
2.  **JSON Extraction (Primary):**
    -   Look for `script` tags with type `application/json`.
    -   Parse and use a recursive helper to find the `issue` or `pullRequest` keys.
    -   Collect all items in `edges` arrays where `__typename` matches `IssueComment`, `PullRequestReview`, or `PullRequestReviewComment`.
    -   Extract `title`, `body` (or `bodyHTML`), and `author.login`.
3.  **HTML Extraction (Fallback):**
    -   Use `BeautifulSoup` to find `.markdown-title`.
    -   Collect all elements matching `.markdown-body` or `.comment-body`.
    -   Use `get_text(separator='\n', strip=True)` for clean text.
4.  **Deduplication:** Use the `id` from JSON nodes or a simple content hash to ensure comments aren't duplicated if both JSON and HTML extraction succeed.
5.  **Integration Seam:** The logic belongs in a private `_extract_github_conversation` method within `WebScraperAdapter`.

### Performance & Security
-   Keep the logic purely text-based (no browser automation).
-   Reuse the `DEFAULT_USER_AGENT` defined in the adapter.
-   Set a reasonable timeout (15-30s) for the initial `requests.get` call.

## Implementation Notes

### Deliverable: Contract Update
- Updated `WebScraper` protocol to include `@runtime_checkable` and accept `**kwargs` in `get_content`.
- Updated `WebScraperAdapter` implementation signature.
- Added signature verification unit tests in `tests/suites/unit/adapters/outbound/test_web_scraper_contract.py`.
