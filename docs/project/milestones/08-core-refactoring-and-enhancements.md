# Milestone 08: Core Refactoring & Enhancements

## 1. Goal (The "Why")

This milestone consolidates several critical technical debt cleanups and workflow enhancements into a single, cohesive initiative to improve system robustness and developer ergonomics:

1.  **Robust Plan Parsing:** Fix a critical bug where code block content containing markdown syntax breaks the `MarkdownPlanParser`.
2.  **Simplified Execution Syntax:** Remove explicit `cwd` and `env` parameters from the `EXECUTE` action in favor of a POSIX Shell Pre-Processor, allowing the AI to write natural shell scripts while preserving Windows compatibility and path security.
3.  **Enhanced Web Scraping:** Replace `markdownify` with `trafilatura` to strip boilerplate and dramatically improve the signal-to-noise ratio of AI context gathering.
4.  **Refactor Legacy DTOs:** Modernize legacy data transfer objects (`ContextResult`, `CommandResult`, `SERPReport`) into domain-aligned, strictly typed models (`ProjectContext`, `ShellOutput`, `WebSearchResults`).

-   **Referenced Specification:** [Spec: Robust Plan Parsing](./../specs/robust-plan-parsing.md)

## 2. Proposed Solution (The "What")

-   **Parser Refactor:** Implement a single-pass AST traversal algorithm in `MarkdownPlanParser` to ensure code block content is safely isolated from structural parsing.
-   **POSIX Pre-Processor:** Update the parser for `EXECUTE` actions to intercept `cd` and `export` lines from multiline shell blocks. It will map these to internal `cwd` and `env` variables, stripping them from the raw command sent to the OS.
-   **Trafilatura Migration:** Use `trafilatura.extract()` with specific parameters (`output_format='markdown'`, `include_links=True`, `include_formatting=True`) in the `WebScraperAdapter`.
-   **DTO Modernization:** Systematically replace legacy DTOs with new `@dataclass` and `TypedDict` implementations in dedicated modules, migrating all dependent code.

## 3. Implementation Guidelines (The "How")

### 3.1. Single-Pass AST Parser & POSIX Pre-Processor
-   Rewrite `_parse_actions` in `MarkdownPlanParser` to consume nodes from a shared stream, eliminating the fragile multi-pass approach.
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

## 4. Vertical Slices

- [ ] **Slice 1: Refactor Parser and Fix Bug** (Implement the single-pass AST strategy and verify against bug repro).
- [ ] **Slice 2: Simplify EXECUTE Action Syntax** (Implement the POSIX Shell Pre-Processor in the parser).
- [ ] **Slice 3: Implement `trafilatura`** (Dependency swap and adapter update).
- [ ] **Slice 4: Refactor `CommandResult` to `ShellOutput`** (Create, migrate, delete).
- [ ] **Slice 5: Refactor `SERPReport` to `WebSearchResults`** (Create, migrate, delete).
- [ ] **Slice 6: Refactor `ContextResult` to `ProjectContext`** (Create, migrate, delete).
