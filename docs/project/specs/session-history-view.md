# Specification: Automatic Session Log

## 1. Overview (The "Why")

The current session structure, with each turn in a separate directory, is optimized for detailed auditing but makes it difficult to get a high-level, chronological overview of a session's progression. This specification defines a new, automatically generated artifact: the Session Log. This single, consolidated Markdown file presents the entire session history in a clean, readable, "chat-like" format.

## 2. Guiding Principles

-   **Readability First:** The output should be optimized for human consumption, summarizing the key events of the session in chronological order.
-   **Focus on Intent and Outcome:** The view should highlight the AI's plan (`plan.md`) and the factual result of that plan (the `Action Log` from `report.md`), omitting verbose, intermediate artifacts.
-   **Alignment with Core Philosophy:** The feature should align with the project's "Local-First" and "Markdown as Interface" principles, favoring plain-text, portable formats.

## 3. Core Requirements (The "What")

### 3.1. Artifact Definition

1.  **File Name:** `session-log.md`
2.  **Location:** The file will be created at the root of the session directory (e.g., `.teddy/<session_name>/session-log.md`).
3.  **Generation:** This file is automatically created and appended to by the `teddy execute` command upon the successful completion of each turn. It is a living document that grows with the session.

### 3.2. History Reconstruction Logic

The session log must be resilient to manual user actions (renaming, branching). The generation logic will use a hybrid approach that combines metadata for robustness with folder names for user-friendly display.

1.  **Build Dependency Graph:** The system will scan all turn directories and read their `meta.yaml` files to build a dependency graph using the `turn_id` and `parent_turn_id` fields. This correctly maps out all branches.
2.  **Sort Turns:** Within each branch, turns will be sorted chronologically using the `creation_timestamp` from their `meta.yaml`. *(Note: We rely on this explicit timestamp rather than the OS-level file modification time (`mtime`) because `mtime` is fragile and is not preserved across `git clone` operations. If two sibling branches have an identical `creation_timestamp` due to a user manually copying a turn folder, the system falls back to sorting alphabetically by folder name to break the tie.)*
3.  **Generate Log:** The system will traverse the sorted graph to generate the final `session-log.md`, ensuring all branches are represented in a logical, chronological order.

This ensures the underlying logic is robust and handles branching correctly, while still allowing for flexible sorting and display.

### 3.3. Content Structure

To ensure a clean, readable document, each turn will be appended using the following hierarchical format, separated by a horizontal rule (`---`).

1.  **Turn Header (H2):** A single Level 2 header will be created for the turn. It will use the **turn's folder name** as the primary identifier, followed by the title from the plan's H1 header. This provides a direct visual link to the file system while maintaining a good document structure.
    -   *Example:* `## Turn: 02-branch - Refactor the Core Service`

2.  **Plan Details:** The full content of the `plan.md` file, **excluding** its top-level H1 header, will be included. This preserves the plan's metadata, rationale, and action plan while fitting correctly into the document's structure.

3.  **Execution Outcome (H3):** A Level 3 header, `### Execution Outcome`, will be added.
    -   Beneath this header, the `Action Log` section (including its `### Action Log` header) will be extracted verbatim from the corresponding `report.md`. If a turn has not been executed, this entire section will be omitted.

#### Example Turn Entry:
````````markdown
---
## Turn: 01-initial-research - Research and Propose a New Agent

- **Status:** Green 🟢
- **Plan Type:** Exploration
- **Agent:** Pathfinder

## Rationale
...

## Action Plan
...

### Execution Outcome

### Action Log
#### `CREATE`: ...
- **Status:** SUCCESS
...
````````

## 4. Implementation Guide

The generation process will be a pure Python function that takes a session directory path as input and writes the `session-log.md` file as output. The core logic can be broken down into four distinct steps.

### Step 1: Data Ingestion and Graph Construction

1.  **Scan Directories:** Use `pathlib.Path.glob` to find all subdirectories within the session directory.
2.  **Parse Metadata:** For each directory, attempt to read and parse its `meta.yaml` file using the `PyYAML` library. If `meta.yaml` is missing or invalid, the directory is skipped.
3.  **Build Turn Nodes:** Store the parsed metadata, along with the directory path (for later use as the display name), in a simple data structure (e.g., a dictionary or a dataclass). A dictionary mapping `turn_id` to this turn object will be the primary data structure.
4.  **Build Adjacency List:** Create an adjacency list (e.g., a `dict` mapping a `turn_id` to a `list` of its children `turn_id`s) by iterating through all turn nodes and linking each `parent_turn_id` to its child.

### Step 2: Identify Branches and Sort

1.  **Find Roots:** Identify all root nodes of the graph (turns with no parent).
2.  **Find Leaves:** Identify all leaf nodes (turns with no children).
3.  **Trace Branches:** For each leaf node, perform a traversal up to its root using the parent links. This reconstructs the linear history for each individual branch. The turns within each branch will be sorted chronologically using the `creation_timestamp`.

### Step 3: Generate Markdown Content

1.  **Iterate Branches:** Process each reconstructed branch one by one. If there's more than one branch, a top-level header (e.g., `## Branch starting from Turn: [root_folder_name]`) could be added to delineate them.
2.  **Process Turns:** For each turn in a branch:
    -   Read the `plan.md` file.
    -   Extract its H1 title and the rest of its content.
    -   Read the `report.md` file (if it exists).
    -   Extract the content of the `### Action Log` section. This can be done with a simple string search or a more robust Markdown parser if needed, but string splitting should suffice initially.
    -   Format the extracted content into the string template defined in the specification.

### Step 4: Write to File

1.  **Concatenate:** Join all the generated Markdown strings for each turn.
2.  **Write:** Overwrite the `session-log.md` file in the session's root directory with the complete, newly generated content.

### Key Libraries & Dependencies

-   **`pathlib`**: (Standard Library) For robust file system scanning.
-   **`PyYAML`**: For parsing `meta.yaml` files. This will be the only new external dependency required.

### Edge Cases to Handle

-   **Missing Files:** The logic must gracefully handle cases where `meta.yaml`, `plan.md`, or `report.md` are missing for a given turn directory.
-   **Orphaned Turns:** Turns whose `parent_turn_id` does not correspond to any existing turn will be treated as roots of their own branches.
-   **Circular Dependencies:** While unlikely, the graph construction logic should ideally detect and handle circular dependencies to prevent infinite loops (e.g., by keeping track of visited nodes during traversal).
