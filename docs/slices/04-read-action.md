# Vertical Slice 04: Implement `read` Action

### 1. Business Goal
To empower the AI agent to gather context from the local filesystem and the web. This is a foundational capability that enables the agent to understand existing code, configuration, or external documentation before making changes.

### 2. Acceptance Criteria (Scenarios)

*   **Scenario 1: Read a local file successfully**
    *   **Given:** A file exists at `data/source.txt` with the content "Hello, TeDDy!".
    *   **When:** The `teddy` executor is run with a plan to `read` the `source` "data/source.txt".
    *   **Then:** The execution report indicates the action was `SUCCESSFUL`.
    *   **And:** The report's `output` field contains the exact string "Hello, TeDDy!".

*   **Scenario 2: Fail to read a non-existent local file**
    *   **Given:** No file exists at `data/nonexistent.txt`.
    *   **When:** The `teddy` executor is run with a plan to `read` the `source` "data/nonexistent.txt".
    *   **Then:** The execution report indicates the action `FAILED`.
    *   **And:** The report's `output` field contains an error message like "File not found".

*   **Scenario 3: Read a remote URL successfully**
    *   **Given:** A mock web server will return "Web Content" for the URL `http://mock-server/test-page`.
    *   **When:** The `teddy` executor is run with a plan to `read` the `source` "http://mock-server/test-page".
    *   **Then:** The execution report indicates the action was `SUCCESSFUL`.
    *   **And:** The report's `output` field contains the exact string "Web Content".

*   **Scenario 4: Fail to read an inaccessible remote URL**
    *   **Given:** A mock web server will return a 404 Not Found error for `http://mock-server/not-found`.
    *   **When:** The `teddy` executor is run with a plan to `read` the `source` "http://mock-server/not-found".
    *   **Then:** The execution report indicates the action `FAILED`.
    *   **And:** The report's `output` field contains an error message indicating an HTTP error (e.g., "404 Not Found").

### 3. Interaction Sequence

1.  The `CLIAdapter` receives a YAML plan containing a `read` action.
2.  It invokes the `RunPlanUseCase` (implemented by `PlanService`) with the parsed plan.
3.  The `PlanService` receives the list of action data and iterates through them.
4.  For the `read` action, the `PlanService` uses the `ActionFactory` to create a `ReadAction` domain object.
5.  The `PlanService` inspects the `source` attribute of the `ReadAction` to determine if it is a URL (starts with `http://` or `https://`) or a local file path.
6.  **If it's a file path:**
    *   The `PlanService` calls the `read_file(path)` method on the `FileSystemManager` outbound port.
    *   The `LocalFileSystemAdapter` implements this, reads the file from disk, and returns the content or raises an exception.
7.  **If it's a URL:**
    *   The `PlanService` calls the `get_content(url)` method on the `WebScraper` outbound port.
    *   The `WebScraperAdapter` implements this, makes an HTTP GET request, and returns the page content or raises an exception.
8.  The `PlanService` catches any exceptions, creates an `ActionReport` with the status (`SUCCESSFUL` or `FAILED`) and the result (content or error message), and adds it to the `ExecutionReport`.
9.  The final `ExecutionReport` is returned to the `CLIAdapter` to be formatted and displayed to the user.

### 4. Scope of Work (Components)

*   **Domain Model (`docs/core/domain_model.md`)**:
    *   [ ] Introduce a new `ReadAction` data class inheriting from `Action`.
*   **Core Ports (`docs/core/ports/outbound/`)**:
    *   [ ] Create a new `WebScraper` outbound port (`web_scraper.md`) with a `get_content(url: str) -> str` method.
    *   [ ] Update the `FileSystemManager` port (`file_system_manager.md`) to include a `read_file(path: str) -> str` method.
*   **Application Services (`docs/core/services/plan_service.md`)**:
    *   [ ] Update `PlanService` to depend on the `WebScraper` port.
    *   [ ] Modify the action execution logic to handle the `ReadAction`, differentiating between file paths and URLs and calling the appropriate outbound port.
*   **Factories (`docs/core/factories/action_factory.md`)**:
    *   [ ] Update the `ActionFactory` to recognize and create `ReadAction` objects.
*   **Adapters (`docs/adapters/outbound/`)**:
    *   [ ] Create a new `WebScraperAdapter` (`web_scraper_adapter.md`) that implements the `WebScraper` port using a standard HTTP client library.
    *   [ ] Update the `LocalFileSystemAdapter` (`file_system_adapter.md`) to implement the new `read_file` method from its port.
