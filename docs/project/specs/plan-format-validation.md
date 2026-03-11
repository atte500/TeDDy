# Specification: Plan Validation

## 1. Overview & Principles

This document specifies the pre-flight validation checks that **must** be run on any `plan.md` file before it is presented to the user for approval. This validation phase is a critical gatekeeper in the TeDDy workflow, designed to catch common, predictable errors early and enable the automated self-correction loop.

### Principles

-   **Fail Fast:** The system must identify and report errors at the earliest possible opportunity, preventing "approve-then-fail" scenarios that waste time and effort.
-   **Provide Actionable Feedback:** Validation errors must be specific, clear, and provide enough context for an AI agent to understand the mistake and correct it.
-   **Enable Self-Correction:** This validation system is the foundation of the **Automated Re-plan Loop**, as defined in the [Interactive Session Workflow Specification](./interactive-session-workflow.md). A failure here triggers the AI's self-correction mechanism.
-   **Guarantee Graceful Handling:** The validation layer is the primary defense against runtime errors. If a plan passes all validation checks, it should execute without unexpected crashes. Any potential error that can be anticipated (e.g., file not found, command failure) must be caught, handled gracefully, and documented clearly in the final execution report.

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
-   **[✓] Must start with a single H1 Title:** The plan must begin with exactly one Level 1 (`#`) heading.
-   **[✓] Must contain core sections:** The plan must contain `## Rationale` and `## Action Plan` Level 2 (`##`) headings.
-   **[✓] H1 must be followed by required metadata:** The H1 heading must be immediately followed by an unordered list containing the keys `Status`, `Plan Type`, and `Agent`.

---

### 3.2. Action Block Checks

These checks ensure the `## Action Plan` section and the individual action blocks are correctly structured according to the [New Plan Format Specs](./new-plan-format.md).

-   **[✓] Action headers must be H3:** Each action must be defined by a Level 3 (`###`) heading (e.g., `### `CREATE``).

---

### 3.3. Action-Specific Logical Checks

These checks validate the *content* of an action against the current state of the file system and session context.

#### `CREATE`
-   **[✓] `File Path` must be specified:** The metadata block must contain a valid `File Path`.
-   **[✓] Target path must not exist (unless Overwrite is true):** By default, the file path specified must not already exist. If `Overwrite: true` is provided, validation passes even if the file exists.
    -   *Failure Example:* A plan tries to `CREATE` `src/main.py` but that file already exists and `Overwrite` is omitted.

#### `EDIT`
-   **[✓] `File Path` must be specified:** The metadata block must contain a valid `File Path`.
-   **[✓] Target path must exist:** The specified file must already exist on the file system.
    -   *Failure Example:* A plan tries to `EDIT` `src/utils.py` but that file does not exist.
-   **[✓] Target path must be in context:** The specified file must be listed in the current turn's context (`turn.context`). This is a safety measure to ensure the AI is not editing files it hasn't "read."
-   **[✓] Must contain `FIND`/`REPLACE` pairs:** The action block must contain at least one pair of `#### FIND:` and `#### REPLACE:` headings.
-   **[✓] `FIND` and `REPLACE` must be different:** For each pair, the content of the `FIND` and `REPLACE` blocks must not be identical.
-   **[✓] `FIND` block must match exactly once:** For each `FIND`/`REPLACE` pair, the content of the `FIND` code block must be found **exactly one time** within the target file.
    -   *Failure (0 matches):* The specified text to find does not exist in the file.
    -   *Failure (>1 matches):* The specified text is ambiguous because it appears multiple times in the file.
    -   **Enhanced Feedback on Mismatch:** If the `FIND` block fails with 0 matches, the validation system will find the "best" or "closest" match in the document using `difflib.SequenceMatcher`. The failure report provided to the AI must then include a high-clarity, intra-line `diff` (generated via a method like `difflib.ndiff`) that uses character-level markers to pinpoint the exact locations of the discrepancies. This provides a precise, actionable signal for self-correction.

#### `READ`
-   **[✓] `Resource` must be specified:** The metadata block must contain a `Resource`.
-   **[✓] Local file must exist:** If the resource is a local file path (e.g., `[path/to/file.md](/path/to/file.md)`), that file must exist on the file system. (Note: URLs are not validated at this stage).
-   **[✓] Target must NOT be in context:** The specified file must NOT be already listed in the session context (`session.context`) or the current turn's context (`turn.context`).
    -   *Failure Example:* A plan tries to `READ` `README.md` but that file is already in `session.context`.

#### `EXECUTE`
-   **[✓] Must contain a core command:** The command code block must not be empty.
-   **[✓] Allow Failure is optional:** Defaults to `false` if omitted. If present, the value MUST be `true` or `false`.
-   **[✓] Background is optional:** Defaults to `false` if omitted. If present, the value MUST be `true` or `false`.
-   **[✓] Timeout is optional:** If present, the value MUST be an integer representing seconds.
-   **[✓] Supports Chaining & Directives:** Validation no longer blocks shell operators (&&, ||, ;, |) or directives (cd, export) in the command block.

#### `PRUNE`
-   **[✓] `Resource` must be specified:** The metadata block must contain a `Resource`.
-   **[✓] Target must be in context:** The specified file must be listed in the current turn's context (`turn.context`).
    -   *Failure Example:* A plan tries to `PRUNE` `docs/OLD_SPEC.md` but that file is not listed in `turn.context`.

#### `PROMPT`
-   **[✓] Message must be specified:** The action must contain free-form markdown content under the heading. Because this action is parsed as a single block of text, the system does not perform automated validation of referenced file paths.

#### `INVOKE`
-   **[✓] `Agent` must be specified:** The metadata block must contain a valid target agent name.
-   **[✓] `Description` must be specified:** The metadata block must contain a short explanation of the handoff.
-   **[✓] Reference Files must exist:** If the optional `Reference Files` list is provided, all specified local files must exist on the file system.

#### `RETURN`
-   **[✓] `Description` must be specified:** The metadata block must contain a short explanation of the task completion.
-   **[✓] Reference Files must exist:** If the optional `Reference Files` list is provided, all specified local files must exist on the file system.
