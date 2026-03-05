# Slice 2: Auto-Initialization

## 1. Business Goal

To eliminate manual setup friction for new projects or users by ensuring the `.teddy/` directory and its essential configuration files are automatically created with sensible defaults upon the first use of the `teddy` CLI.

- **Source Milestone:** [Milestone 09: Interactive Session Workflow & LLM Integration](/docs/project/milestones/09-interactive-session-and-config.md)

## 2. Acceptance Criteria (Scenarios)

### Scenario: First-time initialization of the .teddy directory

- **Given** a workspace without a `.teddy/` directory.
- **When** any `teddy` command (e.g., `teddy context`) is executed.
- **Then** a `.teddy/` directory MUST be created in the current working directory.
- **And** it MUST contain a `config.yaml` file with the default template.
- **And** it MUST contain an `init.context` file with the default template.

### Scenario: Partial initialization

- **Given** a workspace with a `.teddy/` directory but no `config.yaml`.
- **When** a `teddy` command is executed.
- **Then** the missing `config.yaml` MUST be created.
- **And** the existing `.teddy/` directory and other files MUST remain untouched.

### Scenario: Existing configuration is respected

- **Given** a workspace with an existing `.teddy/config.yaml`.
- **When** a `teddy` command is executed.
- **Then** the existing file MUST NOT be overwritten or modified.

## 3. User Showcase

### Verify Auto-Initialization

1. Navigate to a clean directory: `mkdir /tmp/teddy-test && cd /tmp/teddy-test`.
2. Run a command: `teddy context`.
3. **Expected Result:**
   - The command executes (it may report an empty tree).
   - A `.teddy/` folder exists.
   - `/tmp/teddy-test/.teddy/config.yaml` exists and contains comments/placeholders.
   - `/tmp/teddy-test/.teddy/init.context` exists.

## 4. Architectural Changes

- **CLI Entry Point:** Modify `src/teddy_executor/__main__.py` to include a "bootstrap" or "ensure_initialized" call before command execution.
- **Templates:** Define the default content within the application (e.g., as strings in a new service or resource files).

### Default Template: `config.yaml`
```yaml
# TeDDy Configuration

# LLM Settings
# llm:
#   model: "gemini/gemini-1.5-flash"
#   api_key: "your-api-key-here"
#   api_base: "https://generativelanguage.googleapis.com"
```

### Default Template: `init.context`
```markdown
# Initial Project Context
This file defines global instructions or context that is always included
in your AI planning sessions.
```

## 5. Deliverables

1. [x] Logic in `__main__.py` to trigger initialization.
2. [x] A service or utility to handle the creation of the `.teddy/` structure and templates.
3. [x] Unit tests for the initialization logic.
4. [x] Integration test verifying the CLI auto-initializes in a fresh directory.

## Implementation Summary

The project auto-initialization feature was implemented by centralizing all initialization logic into a new `InitService`. This service is invoked via a global `Typer` callback (`bootstrap`) in `__main__.py`, ensuring it runs before any project-specific command.

### Key Changes
- **New Service:** `InitService` implements the `IInitUseCase` port. It handles the idempotent creation of `.teddy/`, `.teddy/.gitignore`, `.teddy/config.yaml`, and `.teddy/init.context`.
- **Refactoring:** Existing ad-hoc initialization logic was removed from `ContextService` and `LocalFileSystemAdapter`, simplifying those components and ensuring a single source of truth for project setup.
- **Port Updates:** The `FileSystemManager` port was simplified by removing the `create_default_context_file` method, as its responsibility was moved to the service layer.
- **Testing:** Comprehensive unit and acceptance tests were added to verify first-time setup, partial initialization, and preservation of existing user configurations.
