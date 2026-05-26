# Spec: Stability & Bug Fixes

## 1. Infrastructure & Environment
- **LiteLLM Warnings:** Suppress `LiteLLM:WARNING` regarding missing `botocore` dependency in production environments (e.g., PyPI installs).
- **SSL/API Resilience:** Implement a retry mechanism (3 attempts) for LLM completion failures involving `SSLV3_ALERT_BAD_RECORD_MAC` errors or OpenRouter timeouts.
- **Web Scraper (403 Bypassing):** The `WebScraperAdapter` must attempt to bypass 403 Forbidden errors (e.g., PNAS) by rotating User-Agents or using common headers.
- **GitHub Raw Compatibility:** Fix the issue where `raw.githubusercontent.com` links return `SUCCESS` but with empty content.
- **RESEARCH Full Scrape:** The `RESEARCH` action should attempt to scrape and return full contents (or at least significant excerpts) instead of just SERP snippets.

## 2. Context Service & Session Management
- **Recursive Expansion:** If a path in a `.context` file or `-c` flag is a directory, the `ContextService` must recursively expand it and include all files, respecting `.gitignore` and `.teddyignore`.
- **Deduplication & Cleanliness:** Ensure context items are deduplicated. Resource contents must NOT be added to `report.md` in session mode if the file is already in the turn's context (since it's already in `input.md`).
- **Auto-Addition:** The `CREATE` action must automatically add the newly created file to the current turn's `turn.context`.
- **Mid-Execution Consistency:** Prevent crashes if a file is modified during execution (e.g., an `EXECUTE` command modifies a file that an `EDIT` action later attempts to touch). In such cases, the `EDIT` should report `FAILURE` gracefully.

## 3. TUI & CLI UX
- **Editor Precision:** Ensure the `(e)` key in the TUI strictly respects the `editor` configuration in `config.yaml` as the highest priority.
- **Validation Visibility:** "Validation failed replanning" logs must include the concise version of the encountered errors and remove redundant empty lines.
- **Layout Consistency:** Ensure padding for Rationale items and Message sections matches the padding of the right-hand panel across all views.
- **Tier 2 Editing:** If a parameter is multiline or exceeds 100 characters, automatically open the external editor for that parameter instead of an inline prompt.
- **UX Hints:** In the hint appended to user request messages, remind the user to "update reference documents accordingly if needed."
- **Parser Resilience:** Ignore and clean up unforeseen codeblocks or thematic breaks following an action block (e.g., `READ`) or trailing text (e.g., `~~~~~~ Useful link...`) without throwing validation errors.
