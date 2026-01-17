# Brief: Quality of Life Improvements

This document outlines the plan for a set of features aimed at improving the usability and developer experience of the `teddy` CLI and its plan execution workflow.

## 1. Problem Definition (The Why)

-   **Goal:** To enhance the developer experience by making YAML plans more readable, CLI output more user-friendly, and interactive actions more informative.
-   **User Stories:**
    1.  **As a developer creating a plan**, I want to add a `description` field to any action, so that the purpose of the action is clear to human readers and can be used in interactive prompts.
    2.  **As a developer running a plan**, I want the output in my terminal (both the approval prompts and the final report) to be well-formatted and easy to read.
    3.  **As a developer using the `chat_with_user` action**, I want the user's response to be captured and clearly displayed in the final execution report.
-   **Constraint:** The `description` field must be implemented in a way that does not require changing the method signatures of the underlying outbound adapters.

## 2. Selected Solution (The What)

The selected solution involves a series of targeted improvements to the core service layer and the CLI formatting layer.

1.  **Universal `description` Field:** The `ActionDispatcher` service will be modified to recognize the `description` parameter in any action. It will extract this field, use it for logging/prompts (in a future slice), and then strip it from the parameter dictionary before passing the remaining arguments to the outbound adapter. This prevents `TypeError` exceptions and achieves the goal without altering the adapter contracts.
2.  **CLI Output Formatting:** The `cli_formatter.py` module and the `main.py` command definitions will be reviewed and refactored to improve the presentation of data, potentially using rich text formatting or better-structured layouts.
3.  **Enhanced `chat_with_user` Action:** The `ActionDispatcher`'s handling of the `chat_with_user` result will be modified to ensure the user's response is captured and placed in the `details.response` field of the `ActionLog`.

## 3. Implementation Analysis (The How)

-   The investigation of `packages/executor/src/teddy_executor/core/services/action_dispatcher.py` has confirmed that it is the correct and safest place to implement the logic for the universal `description` field. The change will be localized to the `dispatch_and_execute` method.
-   The formatting improvements will primarily affect `packages/executor/src/teddy_executor/adapters/inbound/cli_formatter.py` and `packages/executor/src/teddy_executor/main.py`.
-   The `chat_with_user` enhancement will also be implemented in the `ActionDispatcher`.

## 4. Vertical Slices

- [ ] **Implement Quality of Life Improvements:**
    - [ ] **Universal `description` Field:**
        - [ ] In `ActionDispatcher`, modify `dispatch_and_execute` to recognize and strip the `description` parameter from `action_data.params` before calling the action handler. This prevents `TypeError` exceptions on the adapters.
        - [ ] In `main.py`, update the interactive approval prompt to display the action's `description` if it exists, providing better context to the user.
    - [ ] **Improve CLI Output Formatting:**
        - [ ] Refactor the interactive approval prompt logic in `main.py` to present the action and its parameters in a more readable, multi-line format.
        - [ ] Review and refactor `cli_formatter.py` to improve the final YAML report's readability, especially for multi-line strings and nested data like the `chat_with_user` response.
    - [ ] **Update Documentation:**
        - [ ] In `docs/ARCHITECTURE.md`, update the "YAML Plan Specification" to document that `description` is a supported optional field for all actions.
        - [ ] In the same document, update the `chat_with_user` example to show how the user's response appears in the final report.
