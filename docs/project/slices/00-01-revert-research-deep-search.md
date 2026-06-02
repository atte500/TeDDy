# Slice: Revert Research Deep Search

- **Status:** Completed
- **Type:** Refactor
- **Milestone:** N/A
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)

## Business Goal
Revert the `RESEARCH` action behavior to return only the URL, Page Title, and Meta Description (Snippet) without attempting to scrape the full content of each result. This restores the previous performance profile and reduces the volume of the execution report.

## Scenarios
> As an agent performing research, I want to see only search results so that I get a concise overview of the search landscape.
```gherkin
Given a set of search queries
When I execute a RESEARCH action
Then the results should contain ONLY the title, URL, and snippet (body)
And no full "Content" blocks should be present in the report
```

## Edge Cases
- **Scraper Persistence**: Ensure the `WebScraperAdapter` itself remains unchanged, as its 403-bypassing and GitHub raw fixes are still required for `READ` actions.

## Deliverables
- [x] **Contract** - Remove `content` field from `SearchResult` DTO in `src/teddy_executor/core/domain/models/web_search_results.py`.
- [x] **Contract** - Rename `body` field to `description` in `SearchResult` DTO.
- [x] **Logic** - Remove `IWebScraper` dependency and scraping loop from `WebSearcherAdapter`.
- [x] **Logic** - Update `WebSearcherAdapter` to populate `description` instead of `body`.
- [x] **Wiring** - Remove IWebScraper injection from `src/teddy_executor/registries/infrastructure.py` for the `WebSearcherAdapter`.
- [x] **Wiring** - Update `src/teddy_executor/core/services/templates/execution_report.md.j2` to use `description` and change codeblock extension from snippet to description but **keep** the "Use READ on the URLs above" hint.
- [x] **Cleanup** - Align tests in `tests/suites/integration/adapters/outbound/test_web_searcher_adapter.py` and `tests/suites/integration/core/services/test_research_parsing_integration.py`.
- [x] **Logic** - Update `RESEARCH` action description in all system prompts (`src/teddy_executor/resources/prompts/*.xml`).
- [x] **Wiring** - Update documentation (specs, standards, and roadmap) to align with the revert and ad-hoc slice rules.

## Implementation Plan
1. **DTO Cleanup**: Remove the `content` field from the `SearchResult` TypedDict and rename `body` to `description`.
2. **Adapter Refactor**: Remove the `_scraper` from the constructor and the logic in `_execute_single_query` that calls it. Update it to populate the new `description` field.
3. **Template Update**: Update the `RESEARCH` section of the Jinja2 template to use `description` while preserving the "Use READ" hint.
4. **Registry Update**: Remove the scraper from the dependency injection container setup for the searcher.
5. **Test Alignment**: Run the test suite and remove/refactor tests that now fail due to the missing `content` field.

## Implementation Notes
- **Contract Contraction**: Removed `content` from `SearchResult` TypedDict. Verified via `get_type_hints` in unit tests.
- **Runtime Reality**: Python `TypedDict` does not enforce key constraints at runtime. Existing logic in `WebSearcherAdapter` that still populates `item["content"]` does not trigger runtime errors, which explains why the global test suite remained green. This logic will be removed in the next deliverable.
- **Contract Renaming**: Renamed `body` to `description` in `SearchResult` DTO. Verified via `get_type_hints`.
- **Global Alignment**: Performed a bulk `sed` replacement of dictionary keys in `tests/` to align the test harness with the new DTO contract.
- **Template Cleanup**: Removed `content` block from `execution_report.md.j2` and renamed `Snippet` codeblock label to `description` to match the DTO field name and the "revert" business goal.
- **Cleanup Verification**: Verified that integration and unit tests are correctly aligned with the `description` field and no longer reference `content`. Verified `test_formatter_action_logs.py` renders `description` block.
