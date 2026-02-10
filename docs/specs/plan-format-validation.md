# Specification: Plan Validation

## 1. Overview & Principles

This document specifies the pre-flight validation checks that **must** be run on any `plan.md` file before it is presented to the user for approval. This validation phase is a critical gatekeeper in the TeDDy workflow, designed to catch common, predictable errors early and enable the automated self-correction loop.

### Principles

-   **Fail Fast:** The system must identify and report errors at the earliest possible opportunity, preventing "approve-then-fail" scenarios that waste time and effort.
-   **Provide Actionable Feedback:** Validation errors must be specific, clear, and provide enough context for an AI agent to understand the mistake and correct it.
-   **Enable Self-Correction:** This validation system is the foundation of the **Automated Re-plan Loop**, as defined in the [Interactive Session Workflow Specification](/docs/specs/interactive-session-workflow.md). A failure here triggers the AI's self-correction mechanism.

## 2. The Validation Process

-   **Trigger:** Validation is automatically performed at the beginning of the `teddy execute` command, regardless of whether it is run in a stateful interactive session or as a stateless manual command.
-   **Success Outcome:** If all checks pass, the system proceeds to the interactive "Approval & Execution Phase".
-   **Failure Outcome:** If any check fails, execution is immediately halted. The system triggers the **Automated Re-plan Loop**, generating a validation failure report and initiating a new turn for the AI to correct the plan.

## 3. Validation Checks

The following checks are performed in order. The first failure terminates the validation process.

---

### 3.1. General Plan Structure

These checks ensure the overall document is well-formed.

-   **[✓] Must be valid Markdown:** The file must be parsable as a standard Markdown document.
-   **[✓] Must have a single H1 Title:** The plan must contain exactly one Level 1 (`#`) heading, which is treated as the plan's title.
-   **[✓] Must contain core sections:** The plan must contain `## Rationale` and `## Action Plan` Level 2 (`##`) headings.

---

### 3.2. Action Block Checks

These checks ensure the `## Action Plan` section and the individual action blocks are correctly structured according to the [New Plan Format Specs](/docs/specs/new-plan-format.md).

-   **[✓] Action headers must be H3:** Each action must be defined by a Level 3 (`###`) heading (e.g., `### `CREATE``).
-   **[✓] Actions must be separated by a horizontal rule:** A `---` must exist between each action block.

---

### 3.3. Action-Specific Logical Checks

These checks validate the *content* of an action against the current state of the file system and session context.

#### `CREATE`
-   **[✓] `File Path` must be specified:** The metadata block must contain a valid `File Path`.
-   **[✓] Target path must not exist:** The file path specified must not already exist on the file system.
    -   *Failure Example:* A plan tries to `CREATE` `src/main.py` but that file already exists.

#### `EDIT`
-   **[✓] `File Path` must be specified:** The metadata block must contain a valid `File Path`.
-   **[✓] Target path must exist:** The specified file must already exist on the file system.
    -   *Failure Example:* A plan tries to `EDIT` `src/utils.py` but that file does not exist.
-   **[✓] Target path must be in context:** The specified file must be listed in the current turn's context (`turn.context`). This is a safety measure to ensure the AI is not editing files it hasn't "read."
-   **[✓] Must contain `FIND`/`REPLACE` pairs:** The action block must contain at least one pair of `#### FIND:` and `#### REPLACE:` headings.
-   **[✓] `FIND` block must match exactly once:** For each `FIND`/`REPLACE` pair, the content of the `FIND` code block must be found **exactly one time** within the target file.
    -   *Failure (0 matches):* The specified text to find does not exist in the file.
    -   *Failure (>1 matches):* The specified text is ambiguous because it appears multiple times in the file.

#### `READ`
-   **[✓] `Resource` must be specified:** The metadata block must contain a `Resource`.
-   **[✓] Local file must exist:** If the resource is a local file path (e.g., `[path/to/file.md](/path/to/file.md)`), that file must exist on the file system. (Note: URLs are not validated at this stage).

#### `PRUNE`
-   **[✓] `Resource` must be specified:** The metadata block must contain a `Resource`.
-   **[✓] Target must be in context:** The specified file must be listed in the current turn's context (`turn.context`).
    -   *Failure Example:* A plan tries to `PRUNE` `docs/OLD_SPEC.md` but that file is not listed in `turn.context`.
