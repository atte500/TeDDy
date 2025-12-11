# Vertical Slice 03: Implement `read` Action

### 1. Business Goal
To provide the AI agent with the ability to read the contents of local files and remote URLs, which is a fundamental capability for understanding project context and gathering information. The action must handle both success and failure cases gracefully, reporting the outcome clearly in the final Execution Report.

### 2. Acceptance Criteria (Scenarios)

*   **Scenario 1: Successfully read a local file**
    *   **Given:** A plan contains a `read` action with a valid local `source` path.
    *   **When:** The executor runs the plan.
    *   **Then:** The execution report for that action shows a `SUCCESS` status.
    *   **And:** The report's output contains the full content of the specified file within a formatted code block.

*   **Scenario 2: Successfully read a remote URL**
    *   **Given:** A plan contains a `read` action with a valid remote URL `source` that returns HTML.
    *   **When:** The executor runs the plan.
    *   **Then:** The execution report for that action shows a `SUCCESS` status.
    *   **And:** The report's output contains the main content of the URL, converted from HTML to Markdown.

*   **Scenario 3: Fail to read a non-existent local file**
    *   **Given:** A plan contains a `read` action with a local `source` path that does not exist.
    *   **When:** The executor runs the plan.
    *   **Then:** The execution report for that action shows a `FAILURE` status.
    *   **And:** The report's output contains a clear error message indicating the file was not found.

*   **Scenario 4: Fail to read an unreachable remote URL**
    *   **Given:** A plan contains a `read` action with a remote URL `source` that is unreachable (e.g., connection timeout, 404).
    *   **When:** The executor runs the plan.
    *   **Then:** The execution report for that action shows a `FAILURE` status.
    *   **And:** The report's output contains a clear error message indicating the URL could not be retrieved and the reason.

### 3. Interaction Sequence
1.  The `CLI Adapter` receives a YAML plan containing a `read` action.
2.  It parses the action and invokes the `RunPlanUseCase` (inbound port) on the `PlanService`.
3.  The `PlanService` identifies the action source as either a local path or a URL.
4.  **If local:** It invokes the `read_file` method on the `FileSystemManager` (outbound port).
    *   The `FileSystemAdapter` implements this, reads the file, and returns the content or an error.
5.  **If remote:** It invokes the `get_url_content` method on the `WebScraper` (new outbound port).
    *   The `WebScraperAdapter` (new adapter) implements this, fetches the URL, converts HTML to Markdown, and returns the content or an error.
6.  The `PlanService` receives the result and adds a new `ActionReport` to the `ExecutionReport`.
7.  The `CLI Adapter` formats and presents the final `ExecutionReport` to the user.

### 4. Scope of Work (Components)

*   **Domain Model (`docs/core/domain_model.md`):**
    *   [ ] Add `ReadAction` to the `Action` aggregate.
    *   [ ] Add `source` attribute to `ReadAction`.
*   **Core - Outbound Ports:**
    *   [ ] Create `WebScraper` port (`docs/core/ports/outbound/web_scraper.md`).
*   **Adapters - Outbound:**
    *   [ ] Create `WebScraperAdapter` (`docs/adapters/outbound/web_scraper_adapter.md`).
*   **Core - Services:**
    *   [ ] Modify `PlanService` to handle the `ReadAction`, orchestrating with the correct outbound port.
