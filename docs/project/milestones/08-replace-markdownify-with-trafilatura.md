# Replace Markdownify with Trafilatura

## 1. Goal (The "Why")

The current `WebScraperAdapter` uses the `markdownify` library, which converts the entire HTML body of a webpage into Markdown. This approach is too "noisy" for the AI's primary use case, as it includes non-essential content like navigation, ads, and footers that dilute the core information.

This initiative will replace `markdownify` with a more intelligent extraction library to ensure the AI receives only the essential content from a webpage, improving the quality of its context.

## 2. Proposed Solution (The "What")

Following a series of technical spikes, the `trafilatura` library has been validated as the chosen solution. It excels at extracting the main article text while discarding boilerplate.

The implementation will use the `trafilatura.extract()` function with the following key parameters:
-   `output_format='markdown'`: To produce Markdown-native output.
-   `include_links=True`: To preserve hyperlinks.
-   `include_formatting=True`: To preserve semantic structures, including code blocks.

This configuration was empirically proven to meet all success criteria.

## 3. Implementation Analysis (The "How")

The implementation requires changes in three key areas:

1.  **Dependency Management (`pyproject.toml`):** The `markdownify` dependency must be removed, and the `trafilatura` dependency must be moved from the `dev` group to the main production dependencies.
2.  **Adapter Logic (`web_scraper_adapter.py`):** The core logic in the `get_content` method of the `WebScraperAdapter` needs to be updated to import and use `trafilatura.extract` instead of `markdownify`.
3.  **Integration Testing (`test_web_scraper_adapter.py`):** The existing integration test is insufficient. It uses a simple JSON string as a mock response and has assertions specific to `markdownify`'s output quirks. This test must be rewritten to use a realistic HTML mock containing boilerplate, a main article, links, and code blocks. The assertions must be updated to verify that `trafilatura` correctly strips the boilerplate and preserves the essential formatted content.

## 4. Vertical Slice

- [ ] **Implement `trafilatura` and Update System**
    - [ ] **Dependencies:**
        - [ ] In `pyproject.toml`, remove the `markdownify` line from `[tool.poetry.dependencies]`.
        - [ ] In `pyproject.toml`, move `trafilatura` from the `dev` group to main dependencies.
        - [ ] Run `poetry lock --no-update` and `poetry install`.
    - [ ] **Adapter Logic:**
        - [ ] In `src/teddy_executor/adapters/outbound/web_scraper_adapter.py`, replace the `markdownify` import and usage with `trafilatura.extract(html_content, output_format='markdown', include_links=True, include_formatting=True)`.
    - [ ] **Integration Test:**
        - [ ] In `tests/integration/adapters/outbound/test_web_scraper_adapter.py`, rewrite `test_get_content_success`.
        - [ ] The new test must use a mock HTML response containing boilerplate (header/footer), a main article, links, and code blocks.
        - [ ] Assertions must confirm boilerplate is removed and that essential content (article text, links, code blocks) is correctly preserved in the final output.
