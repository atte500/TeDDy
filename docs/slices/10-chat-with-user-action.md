# Vertical Slice 10: Implement `chat_with_user` Action

### 1. Business Goal

To provide a mechanism for the AI to ask the user open-ended questions and capture their free-text responses during the execution of a plan, enabling more complex, interactive workflows.

### 2. Acceptance Criteria (Scenarios)

**Scenario: Successful Chat Interaction**
```gherkin
Given a plan containing a 'chat_with_user' action with a prompt "What is your favorite color?"
When the plan is executed
And the user approves the action by entering "y"
And the executor displays the prompt "What is your favorite color?"
And the user enters "Blue" and presses Enter twice
Then the action should be marked as SUCCEEDED
And the execution report should contain the user's response "Blue"
```

**Scenario: User Skips Chat Action**
```gherkin
Given a plan containing a 'chat_with_user' action
When the plan is executed
And the user rejects the action by entering "n"
Then the action should be marked as SKIPPED
And the prompt should not be displayed to the user
```

### 3. Interaction Sequence

1.  The `PlanService` receives a `ChatWithUserAction` object from the `ActionFactory`.
2.  The `PlanService` invokes the `ask_question` method on its `IUserInteractor` outbound port, passing the `prompt_text`.
3.  The `ConsoleInteractorAdapter` (implementing the port) prints the prompt to the console.
4.  The `ConsoleInteractorAdapter` reads lines from standard input until the user provides two consecutive newlines.
5.  It returns the captured string back to the `PlanService`.
6.  The `PlanService` creates a `Success` result object containing the user's response and marks the action as complete.

### 4. Scope of Work (Components)

-   [ ] **Hexagonal Core:** `docs/core/domain_model.md` (Update to add `ChatWithUserAction` model)
-   [ ] **Hexagonal Core:** `docs/core/services/action_factory.md` (Update to create the new action model)
-   [ ] **Hexagonal Core:** `docs/core/services/plan_service.md` (Update to orchestrate the new action)
-   [ ] **Hexagonal Core (NEW):** `docs/core/ports/outbound/user_interactor.md` (Define the new outbound port)
-   [ ] **Adapter (NEW):** `docs/adapters/outbound/console_interactor.md` (Define the new adapter to implement the port)
-   [ ] **Framework Integration:** `src/teddy/main.py` (Update wiring to inject the new adapter into the service)
