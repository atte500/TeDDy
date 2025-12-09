# The `TeDDy` Executor: The Hands of the AI

`teddy` is a command-line tool that acts as the bridge between AI-generated YAML plans and your local filesystem. It allows for safe, transparent, and user-supervised execution of development tasks.

## Execution Flow

1.  **Plan Generation:** An AI agent generates a multi-step plan in YAML format.
2.  **Execution:** You run `teddy` in your terminal, piping or pasting the plan to it.
3.  **Interactive Approval:** By default, `teddy` runs in interactive mode. It prints each action and prompts for your approval (`y/n`). If you reject a step, you will be prompted for an optional reason. The action is not performed, and the final report will mark it as `SKIPPED`, including your reason, confirming that no changes were made.
4.  **Feedback Report:** After execution, `teddy` generates a markdown **Execution Report**, copies it to your clipboard, and prints it to the console. This report is pasted back to the AI, providing a complete feedback loop.
5.  **Automated Context Tip:** If an Execution Report is particularly long, a tip is automatically added at the end. This tip instructs the AI to first summarize the report's key outcomes into its reasoning process before asking you to delete the large message. This helps manage the context window effectively without losing critical information.

## Installation & Dependencies

The `teddy` tool requires Python 3.9+ and the following libraries:

*   `Typer`: For building the command-line interface.
*   `PyYAML`: For parsing YAML action plans.
*   `repotree`: For generating the file tree structure.
*   `pyperclip`: For cross-platform clipboard access.
*   `markdownify`: For converting HTML to Markdown.
*   `SerpScrap`: For scraping search engine result pages.

This project is packaged and can be installed via pip. For local development, install it in editable mode from the root of the repository:

```bash
pip install -e .
```

Once published, it will be available from PyPI:
```bash
pip install teddy
```

## Command-Line Reference

### Executing a Plan

**From Clipboard (Recommended):**
```bash
# Get plan from clipboard and execute with interactive approval
teddy

# Get plan from clipboard and automatically approve all steps
teddy -y
```

**From a File or Pipe:**
```bash
# Execute from a file
teddy my_plan.yaml

# Pipe a plan from another command
echo '- action: execute\n  params:\n    command: "ls -la"' | teddy
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
Creates a new file. Fails if the file already exists.

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

- If `find_block` is a string, it must be a literal match. The action fails if the block is not found.
- If `find_block` is an empty string (`""`) or null (`~`), the entire file content is replaced.

```yaml
- action: edit
  description: "Update a dependency version in a config file." # Optional
  params:
    file_path: "requirements.txt"
    find_block: "typer==0.4.0"
    replace_block: "typer==0.5.0"
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
Prompts the user with a question and waits for their input. The input is then available in the execution report.

```yaml
- action: chat_with_user
  description: "Ask for user confirmation." # Optional
  params:
    prompt_text: "A new database will be created. Is this okay? (y/n)"
```

### `research`
Performs web searches and returns a SERP report.

```yaml
- action: research
  description: "Find info on Python's Typer." # Optional
  queries: |
    typer python cli tutorial
    typer best practices site:realpython.com
```
