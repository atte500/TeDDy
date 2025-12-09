# Proposal: Execution Report Contract

This document defines the structure and content of the **Execution Report** that `teddy` generates and copies to the clipboard after every run. The report is crucial for providing a complete feedback loop to the AI.

## Guiding Principles

1.  **Machine-Readable:** The report should have clear headings and code fences to be easily parsable by the AI.
2.  **Comprehensive:** It must include the status of every action, along with any output or errors.
3.  **Contextual:** The report should include metadata about the execution environment.

## Proposed Report Structure (Markdown)

````
# Execution Report

**Run Summary:**
- **Status:** [ SUCCESS | FAILURE | PARTIAL_SUCCESS ]
- **Start Time:** [ ISO 8601 Timestamp ]
- **End Time:** [ ISO 8601 Timestamp ]
- **Duration:** [ e.g., 5.23 seconds ]

**Environment:**
- **Operating System:** [ e.g., darwin, linux, win32 ]
- **Working Directory:** [ /path/to/project ]

---

## Action Log

### Action 1: [action_name]

- **Status:** [ SUCCESS | FAILURE | SKIPPED ]
- **Details:** [ A short summary, e.g., "File 'src/main.py' created successfully." ]
- **Output:**
```
[ Standard output or file content from the command. For `read`, this is the file content. For `execute`, the stdout. For `research`, the SERP. For `edit`, it could be a confirmation message. This block is omitted if there is no output. ]
```
- **Error:**
```
[ Standard error output from the command. This block is omitted if there is no error. ]
```

---

### Action 2: [action_name]

- **Status:** [ SUCCESS | FAILURE | SKIPPED ]
- **Details:** [ ... ]
- **Output:**
```
[ ... ]
```

---

[ ... more actions ... ]
```

```
````

---

## Context Management Tip

To proactively manage the AI's context window, `teddy` appends a tip to large reports. This tip guides the AI on how to summarize key outcomes before requesting that the user prune the context, ensuring no critical information is lost.

- **Trigger:** This tip is added if the entire generated markdown report exceeds a configurable threshold (e.g., default: 80 lines or 4000 characters).
- **Placement:** Appended after all action logs, as the final element of the report.

**Example of a Report with a Final Pruning Tip:**
```markdown
# Execution Report
...
### Action 4: execute
...
---

> **Tip:** This execution report is large. Before proceeding, summarize the key outcomes, errors, and any new file contents into your rationale. After you have processed all necessary information, ask the user to delete the message containing this report to preserve context.
```

---

**Example of a Skipped Action:**

When an action is rejected by the user in interactive mode, the executor will prompt for an optional reason. This reason is then included in the report.

### Action 3: edit

- **Status:** SKIPPED
- **Details:** User rejected this action. These changes have not been implemented, and the previous state is still the current one.
- **Reason:** "I don't think this is the right file to edit for this change."
