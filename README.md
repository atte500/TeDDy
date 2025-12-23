# The `TeDDy` Executor: The Hands of the AI

`teddy` is a command-line tool that acts as the bridge between AI-generated YAML plans and your local filesystem. It allows for safe, transparent, and user-supervised execution of development tasks.

## Execution Flow

1.  **Plan Generation:** An AI agent generates a multi-step plan in YAML format.
2.  **Execution:** You run `teddy` in your terminal, piping or pasting the plan to it.
3.  **Interactive Approval:** By default, `teddy` runs in interactive mode. It prints each action and prompts for your approval (`y/n`). If you reject a step, you will be prompted for an optional reason. The action is not performed, and the final report will mark it as `SKIPPED`, including your reason, confirming that no changes were made.
4.  **Feedback Report:** After execution, `teddy` generates a markdown **Execution Report**, copies it to your clipboard, and prints it to the console. This report is pasted back to the AI, providing a complete feedback loop.
5.  **Automated Context Tip:** If an Execution Report is particularly long, a tip is automatically added at the end. This tip instructs the AI to first summarize the report's key outcomes into its reasoning process before asking you to delete the large message. This helps manage the context window effectively without losing critical information.

## Installation & Dependencies

The `teddy` tool is managed using `Poetry` and requires Python 3.9+. The main dependencies include:

*   `Typer`: For building the command-line interface.
*   `PyYAML`: For parsing YAML action plans.
*   `requests`: For making HTTP requests (e.g., in the `read` action).
*   `markdownify`: For converting HTML to Markdown.
*   `playwright`: For advanced web automation (planned for future use).

For local development, use Poetry to install the dependencies and the tool in editable mode:

```bash
# This will create a virtual environment and install all dependencies
poetry install
```

Once published, it will be available from PyPI:
```bash
pip install teddy
```

## Command-Line Reference

### Executing a Plan

To avoid conflicts between plan input and interactive prompts (like `y/n` approval or `chat_with_user`), plans must be passed using the `--plan-file` option. Standard input (`stdin`) is now reserved exclusively for interactive I/O.

**From a File:**
```bash
# 1. Save the AI-generated plan to a file (e.g., plan.yaml)
# 2. Execute the plan with interactive approval:
teddy --plan-file plan.yaml

# To automatically approve all steps, use the -y flag:
teddy --plan-file plan.yaml -y
```

### Utility Commands

These commands are for the user to gather information for the AI. Their output is printed to the console AND copied to the clipboard.

| Command         | Description                                               |
| --------------- | --------------------------------------------------------- |
| `context`       | Provides a project snapshot (`repotree`).                 |
| `copy-unstaged` | Copies a `git diff` of unstaged changes to the clipboard. |

---

## YAML Action Reference

This section defines the contract for the YAML plans the AI can generate.

### `create_file`
Creates a new file. If the file already exists, the action is marked as `FAILED`, no changes are made to the file, and its current content is returned in the execution report.

```yaml
- action: create_file
  description: "Create a new configuration file." # Optional
  params:
    file_path: "path/to/new_file.txt"
    content: |
      Initial content for the file.
      Can be multi-line.
```

### `read`
Reads the content of a local file or a remote URL.

```yaml
- action: read
  description: "Read the project's main entry point." # Optional
  params:
    source: "src/main.py" # Can also be "https://example.com"
```

### `edit`
Modifies an existing file by finding and replacing a block of text.

- If `find` is a string, it must be a literal match. If the string is not found, the action is marked as `FAILED`, no changes are made to the file, and its current content is returned in the execution report.
- If `find` is an empty string (`""`), the entire file content is replaced with the `replace` content.

```yaml
- action: edit
  description: "Update a dependency version in a config file." # Optional
  params:
    file_path: "pyproject.toml"
    find: "typer = \"0.20.0\""
    replace: "typer = \"0.21.0\""
```

### `execute`
Executes a shell command.

```yaml
- action: execute
  description: "Install project dependencies." # Optional
  params:
    command: "pip install -r requirements.txt"
    cwd: "." # Optional working directory
    background: false # Optional, run in background
    timeout: 60 # Optional, in seconds
```

### `chat_with_user`
Asks the user a question and captures their free-text response. This action is subject to the same global `(y/n)` approval as all other actions. If approved, the prompt is displayed, and the executor waits for the user to enter their response. The user must press Enter twice to signal the end of their input. The captured response is then included in the execution report.

```yaml
- action: chat_with_user
  description: "Get user feedback on a proposed approach." # Optional
  params:
    prompt_text: "I'm about to refactor the database schema. Are there any performance-critical queries I should be aware of?"
```

### `research`
Performs web searches and returns a SERP report in JSON format within the execution report.

**Input:**
```yaml
- action: research
  description: "Find info on Python's Typer." # Optional
  queries: |
    typer python cli tutorial
    typer best practices site:realpython.com
```

**Output (in Execution Report):**
The `output` field for a successful `research` action will contain a JSON object with the following structure:
```json
{
  "results": [
    {
      "query": "typer python cli tutorial",
      "search_results": [
        {
          "title": "Typer - The official tutorial",
          "url": "https://typer.tiangolo.com/tutorial/",
          "snippet": "Learn how to use Typer, the library for building powerful CLIs with Python, based on type hints."
        },
        {
          "title": "Python Typer Tutorial - Real Python",
          "url": "https://realpython.com/python-typer-cli/",
          "snippet": "A comprehensive guide to building command-line interfaces in Python with Typer, covering commands, arguments, and options."
        }
      ]
    }
  ]
}
```

---

## Project Roadmap

This section outlines the high-level milestones for the project.

*   **Implement `research` action:** Implement the ability for the agent to perform web searches.
    *   **Status:** In Progress
