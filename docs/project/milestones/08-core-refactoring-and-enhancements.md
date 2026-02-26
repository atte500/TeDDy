# Milestone 08: Core Refactoring & Enhancements

## 1. Goal (The "Why")

This milestone consolidates several critical technical debt cleanups and workflow enhancements into a single, cohesive initiative to improve system robustness and developer ergonomics:

1.  **Robust Plan Parsing:** Fix a critical bug where code block content containing markdown syntax breaks the `MarkdownPlanParser`.
2.  **Simplified Execution Syntax:** Remove explicit `cwd` and `env` parameters from the `EXECUTE` action in favor of a POSIX Shell Pre-Processor, allowing the AI to write natural shell scripts while preserving Windows compatibility and path security.
3.  **Enhanced Web Scraping:** Replace `markdownify` with `trafilatura` to strip boilerplate and dramatically improve the signal-to-noise ratio of AI context gathering.
4.  **Refactor Legacy DTOs:** Modernize legacy data transfer objects (`ContextResult`, `CommandResult`, `SERPReport`) into domain-aligned, strictly typed models (`ProjectContext`, `ShellOutput`, `WebSearchResults`).
5.  **Code Quality & Test Pyramid:** Introduce complexity linters (`ruff`), enforce test coverage in CI (`pytest-cov`), and invert the test pyramid by migrating overly broad acceptance tests down to the unit/integration level.
6.  **CLI UX Improvements:** Streamline the interactive execution approval output. Hide raw `FIND`/`REPLACE` blocks and new file content, display a single unified diff for `EDIT` actions, and show a standard file preview for `CREATE` actions.
7.  **Code Duplication Detection:** Integrate a Copy-Paste-Detector (CPD) tool into the CI pipeline to proactively flag and prevent duplicated code.

## 2. Proposed Solution (The "What")

-   **Parser Refactor:** Implement a single-pass AST traversal algorithm in `MarkdownPlanParser` to ensure code block content is safely isolated from structural parsing.
-   **POSIX Pre-Processor:** Update the parser for `EXECUTE` actions to intercept `cd` and `export` lines from multiline shell blocks. It will map these to internal `cwd` and `env` variables, stripping them from the raw command sent to the OS.
-   **Trafilatura Migration:** Use `trafilatura.extract()` with specific parameters (`output_format='markdown'`, `include_links=True`, `include_formatting=True`) in the `WebScraperAdapter`.
-   **DTO Modernization:** Systematically replace legacy DTOs with new `@dataclass` and `TypedDict` implementations in dedicated modules, migrating all dependent code.
-   **CI Quality Gates:** Add `pytest-cov` to track test coverage and configure `ruff` rules (e.g., McCabe complexity `C901`, `PLR` rules) in `pyproject.toml`. Integrate a CPD tool (e.g., `pmd-bin`) with a defined token threshold to detect duplicated code. Update `.github/workflows/ci.yml` to run all checks.
-   **Test Pyramid Refactoring:** Audit the 36 existing acceptance tests, isolating those that test internal implementation details, and migrate their assertions to the `tests/unit/` and `tests/integration/` directories.

## 3. Implementation Guidelines (The "How")

### 3.1. Strict Parser Validation & POSIX Pre-Processor
-   Refactor `MarkdownPlanParser` to enforce a strict structure within the `## Action Plan` section. Any interstitial content between action blocks (e.g., `---`, paragraphs) must trigger a clear validation error.
-   Inside the `EXECUTE` parsing logic, process the code block content line-by-line:
    -   If a line starts with `cd `, extract the path into the `cwd` parameter dictionary.
    -   If a line starts with `export `, extract the key/value into the `env` parameter dictionary.
    -   Strip these lines so only the true execution commands remain to be passed to the `ShellAdapter`.

### 3.2. Trafilatura Migration
-   Update `pyproject.toml` to remove `markdownify` and add `trafilatura` to the main dependencies.
-   Update `src/teddy_executor/adapters/outbound/web_scraper_adapter.py`.
-   Rewrite integration tests to verify boilerplate removal and structural preservation using realistic HTML mocks.

### 3.3. Legacy DTO Refactoring
Execute a safe "Create, Migrate, Delete" sequence for each legacy model:
-   `CommandResult` -> `ShellOutput` (Use `TypedDict` in `shell_output.py`)
-   `SERPReport` -> `WebSearchResults` (Use nested `TypedDict`s in `web_search_results.py`)
-   `ContextResult` -> `ProjectContext` (Use `@dataclass` in `project_context.py`)

### 3.4. CI Quality Gates & Test Pyramid
-   **Phase 1 (Stop the Bleeding):** Update `pyproject.toml` to include `pytest-cov`. Add `tool.ruff.lint.extend-select = ["C901", "PLR"]`. Explicitly define target thresholds for Cyclomatic Complexity (e.g., McCabe `C901` <= 10) and Source Lines of Code / Statements (e.g., `PLR0915` <= 50). Initially configure these as warnings or with temporary `noqa` exclusions so CI doesn't break immediately, creating a clear burndown list. Add a step to `.github/workflows/ci.yml` to download and run a CPD tool like `pmd-bin`, configured with a reasonable `--minimum-tokens` threshold (e.g., 50). Add this check alongside `ruff check` and `pytest --cov=src`.
-   **Phase 2 (The Great Refactor):** Review `tests/acceptance/`. Move assertions verifying individual components (e.g., `MarkdownPlanParser` behavior, `ActionDispatcher` routing) into corresponding unit/integration tests. Delete redundant acceptance tests to speed up the suite.
-   **Phase 3 (Complexity Remediation):** Refactor the most complex functions identified by `ruff` (e.g., addressing "too many branches/statements") using the newly bolstered unit test suite to ensure safety.

### 3.5. CLI UX Improvements
- Update `ConsoleInteractorAdapter._get_diff_content` to apply all `FIND`/`REPLACE` pairs of an `EDIT` action in memory to generate the `after_content` for the diff.
- Modify the approval prompt logic in `ConsoleInteractorAdapter.confirm_action` or `ExecutionOrchestrator` to suppress the printing of the raw action payload (specifically hiding `FIND`/`REPLACE` and new file content) before the diff/preview is shown.
- Update `ConsoleInteractorAdapter._show_in_terminal_diff` to handle `CREATE` actions by simply printing the new file content with a generic "New File Preview" header, rather than a full diff against an empty string.

## 4. Vertical Slices

- [x] **Slice 1: Refactor Parser and Fix Bug** (Implement the single-pass AST strategy and verify against bug repro).
- [x] **Slice 2: Simplify EXECUTE Action Syntax** (Implement the POSIX Shell Pre-Processor in the parser).
- [x] **Refactor Slice: Fix Parser Nesting Bug** (Implement strict structural AST validation to prevent nesting crashes).
- [x] **Slice 3: Implement `trafilatura`** (Dependency swap and adapter update).
- [x] **Refactor Slice: Enhance Web Scraper to Bypass Anti-Scraping Measures** (Implement fallback for 403 errors).
- [ ] **Refactor Slice: Trim Plan Preamble** (Update parser to ignore text before the H1 heading).
- [ ] **Slice 4: Refactor `CommandResult` to `ShellOutput`** (Create, migrate, delete).
- [ ] **Slice 5: Refactor `SERPReport` to `WebSearchResults`** (Create, migrate, delete).
- [ ] **Slice 6: Refactor `ContextResult` to `ProjectContext`** (Create, migrate, delete).
- [ ] **Slice 7: Configure CI Quality Gates** (Add `pytest-cov`, set strict targets for Cyclomatic Complexity and SLOC via `ruff`, update `ci.yml`).
- [ ] **Slice 8: Add CPD to CI Quality Gates** (Integrate PMD/CPD check into the CI workflow).
- [ ] **Slice 9: Audit and Invert Test Pyramid** (Migrate acceptance tests to unit/integration).
- [ ] **Slice 10: Remediate High-Complexity Code** (Refactor flagged functions and tighten thresholds).
- [ ] **Slice 11: Refine CLI Help Descriptions** (Update Typer command docstrings/help parameters in `main.py`).
- [ ] **Slice 12: Implement CLI UX Improvements** (Consolidate EDIT diffs, simplify CREATE previews, and hide raw payloads).
