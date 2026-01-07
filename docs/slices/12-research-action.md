# Vertical Slice 11: Implement `research` action

### 1. Business Goal
To empower the AI agent to gather external information by performing web searches. This allows the agent to find information about libraries, APIs, or general programming concepts without needing pre-existing knowledge.

### 2. Acceptance Criteria (Scenarios)

**Scenario 1: Successful Web Search**
*   **Given** a plan with a `research` action containing one or more queries.
*   **When** the TeDDy executor runs the plan.
*   **Then** the executor performs a web search for each query.
*   **And** the final execution report for the `research` action shows a `SUCCESS` status.
*   **And** the `output` field contains a JSON object with the search results, matching the format defined in the `README.md`.

**Scenario 2: Web Search Fails**
*   **Given** a plan with a `research` action.
*   **When** the web search component fails to retrieve results (e.g., network error, API key invalid).
*   **Then** the final execution report for the `research` action shows a `FAILURE` status.
*   **And** the `details` field contains a clear error message explaining the cause of the failure.

### 3. Interaction Sequence
1.  The `CliInboundAdapter` receives the plan and passes it to the `PlanService` via the `RunPlanUseCase` port.
2.  The `PlanService` iterates through the actions and encounters the `research` action.
3.  The `ActionFactory` creates a `ResearchAction` domain object.
4.  The `PlanService` executes the `ResearchAction`.
5.  The `ResearchAction` calls the `search` method on the `IWebSearcher` outbound port, passing the list of queries.
6.  The `WebSearcherAdapter`, which implements `IWebSearcher`, receives the queries.
7.  The `WebSearcherAdapter` interacts with an external search service/API to perform the searches.
8.  The `WebSearcherAdapter` transforms the API response into the `SERPReport` domain value object and returns it.
9.  The `PlanService` receives the `SERPReport`, serializes it to JSON, and records it as the `output` of the successful action.
10. The `CliInboundAdapter` formats the final execution report and prints it to the console.

### 4. Scope of Work (Components)

*   [ ] **Hexagonal Core:** `MODIFY` [Domain Model](./../core/domain_model.md) to add `ResearchAction` and `SERPReport` value objects.
*   [ ] **Hexagonal Core:** `MODIFY` [Action Factory](./../core/services/action_factory.md) to recognize and create `ResearchAction` objects.
*   [ ] **Hexagonal Core:** `MODIFY` [Plan Service](./../core/services/plan_service.md) to handle the execution logic for a `ResearchAction`.
*   [ ] **Hexagonal Core:** `CREATE` [IWebSearcher Port](./../core/ports/outbound/web_searcher.md) to define the contract for performing web searches.
*   [ ] **Adapter:** `CREATE` [WebSearcherAdapter](./../adapters/outbound/web_searcher_adapter.md) to implement the `IWebSearcher` port using a third-party search library/API.
