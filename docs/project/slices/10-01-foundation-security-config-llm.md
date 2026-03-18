# Slice 1: Foundation (Security, Config, LLM Client)

## 1. Business Goal

To establish the foundational security, configuration, and LLM interaction capabilities required for the interactive session workflow. This involves integrating comprehensive security gates into the development lifecycle, creating a configuration service to manage settings and secrets, and implementing a decoupled LLM client to handle communication with language models.

-   **Source Milestone:** [Milestone 09: Interactive Session Workflow & LLM Integration](/docs/project/milestones/10-interactive-session-and-config.md)

## 2. Interaction Sequence

This is a foundational slice with no direct user-facing interaction sequence. The primary interactions are with the development environment (pre-commit hooks, CI pipeline) and the application's internal composition root.

## 3. Acceptance Criteria (Scenarios)

### Scenario: Secret scanning prevents leaks

-   **Given** a file is created with content containing a mock AWS key.
-   **When** a developer attempts to commit this file.
-   **Then** the `detect-secrets` pre-commit hook MUST fail the commit.
-   **And** an error message indicating a secret was found MUST be displayed.

### Scenario: Insecure code is blocked locally

-   **Given** a Python file is modified to include an insecure pattern, such as `import subprocess; subprocess.run("ls", shell=True)`.
-   **When** a developer attempts to commit this file.
-   **Then** the `bandit` pre-commit hook MUST fail the commit.
-   **And** an error message detailing the security issue (e.g., "B602: shell-true") MUST be displayed.

### Scenario: Vulnerable dependencies are caught in CI

-   **Given** a version of a dependency with a known vulnerability is added to `pyproject.toml`.
-   **When** the CI pipeline is executed.
-   **Then** the `pip-audit` quality gate MUST fail the build.
-   **And** the CI log MUST clearly report the vulnerable package and the nature of the vulnerability.

### Scenario: Foundational services are available for injection

-   **Given** the application has started.
--   **When** the Dependency Injection container is inspected.
-   **Then** it MUST be possible to resolve concrete implementations for `IConfigService` and `ILlmClient` ports.

## 4. User Showcase

This section provides manual steps to verify the foundational changes.

### Verify Secret Scanning (detect-secrets)

1.  Create a temporary file.
2.  Add it to git: `git add temp_secret_file.py`
3.  Attempt to commit: `git commit -m 'test: add secret'`
4.  **Expected Result:** The commit should fail with an error from `detect-secrets`.
5.  Clean up: `rm temp_secret_file.py` and `git reset`.

### Verify Code Security Scanning (bandit)

1.  Create a temporary file with insecure code: `echo "import subprocess; subprocess.run('ls', shell=True)" > temp_insecure_file.py`
2.  Add it to git: `git add temp_insecure_file.py`
3.  Attempt to commit: `git commit -m 'test: add insecure code'`
4.  **Expected Result:** The commit should fail with an error from `bandit`.
5.  Clean up: `rm temp_insecure_file.py` and `git reset`.

## 5. Architectural Changes

The approved architecture introduces two new outbound ports and their corresponding adapters to decouple configuration and LLM interaction from the core application logic.

-   **New Ports:**
    -   [IConfigService](/docs/architecture/core/ports/outbound/config_service.md): An interface for retrieving application settings and secrets.
    -   [ILlmClient](/docs/architecture/core/ports/outbound/llm_client.md): A generic interface for communicating with Large Language Models.
-   **New Adapters:**
    -   [YamlConfigAdapter](/docs/architecture/adapters/outbound/yaml_config_adapter.md): Implements `IConfigService` by reading from `.teddy/config.yaml`.
    -   [LiteLLMAdapter](/docs/architecture/adapters/outbound/litellm_adapter.md): Implements `ILlmClient` using the `litellm` library.
-   **Quality Gates:**
    -   The local development environment will be enhanced with `detect-secrets` and `bandit` pre-commit hooks.
    -   The CI pipeline will be hardened with a `pip-audit` step to scan for vulnerable dependencies.

The central [Component & Boundary Map](/docs/architecture/ARCHITECTURE.md#2-component--boundary-map) has been updated to reflect these new components.

## 6. Deliverables

This checklist outlines the foundational components and security gates delivered in this slice.

### 1. Security & Environment Foundation

1.  [x] **Updated project dependencies** in `pyproject.toml` supporting security scanning and configuration parsing.
2.  [x] **Security-hardened `/.pre-commit-config.yaml`** integrated with `detect-secrets` and `bandit` gates.
3.  [x] **Active local pre-commit environment** for all developers.
4.  [x] **Validated `.secrets.baseline`** reflecting a clean state of the existing codebase.
5.  [x] **Configured `bandit` settings** in `pyproject.toml` ensuring relevant coverage.
6.  [x] **Hardened CI pipeline** in `/.github/workflows/ci.yml` with automated `pip-audit` checks.

### 2. Foundational Services (Ports & Adapters)

7.  [x] **Formal outbound port definitions** for `IConfigService` and `ILlmClient` (including `LlmApiError`).
8.  [x] **Concrete `YamlConfigAdapter` and `LiteLLMAdapter` implementations** satisfying the port contracts.
9.  [x] **Wired Dependency Injection container** registering the new foundational services for application-wide use.

### 3. Verification & Quality Assurance

10. [x] **Unit test suites** validating the logic of both `YamlConfigAdapter` and `LiteLLMAdapter`.
11. [x] **Integration tests** verifying successful container resolution and service wiring.
12. [x] **Verified local security environment** via manual showcase scenarios.

## Implementation Summary

### Work Completed

- **Security Gates:** Integrated `detect-secrets`, `bandit`, and `pip-audit` into the development lifecycle.
- **Security Baselining:** Performed a comprehensive security audit of the existing codebase. Resolved 9 legacy issues through surgical fixes (adding timeouts to `requests` calls, enabling autoescape where safe) and `# nosec` annotations for intentional patterns (subprocess usage in adapters).
- **Foundational Ports:** Defined `IConfigService` and `ILlmClient` outbound ports.
- **Foundational Adapters:** Implemented `YamlConfigAdapter` for local configuration and `LiteLLMAdapter` for generic LLM interaction.
- **Integration:** Wired all new services into the `punq` DI container.
- **Quality Assurance:** Reached 100% test coverage for all new components and verified the entire system remains stable with 243 passing tests.

### Significant Refactoring & Discoveries

- **Secrets Baseline Tracking:** During CI hardening, it was discovered that `.secrets.baseline` MUST be tracked by Git, contrary to the initial slice instruction to ignore it. Without the baseline file, the `detect-secrets` hook fails in CI environments. This was resolved by removing it from `.gitignore`.
- **Markdown Escaping Regression:** Enabling global Jinja2 `autoescape=True` caused regressions in Markdown report formatting. This was resolved by explicitly setting `autoescape=False` in the `MarkdownReportFormatter` and baselining the `B701` security check.

### [NEW] Reminders for Next Cycle

- **[NEW]:** Ensure all future test mock data using keywords like "key" or "secret" includes the `# pragma: allowlist secret` comment to prevent `detect-secrets` false positives.
- **[NEW]:** The `LiteLLMAdapter` currently requires API keys to be set in the environment or passed via `kwargs`. Future work should enhance it to automatically load keys from `IConfigService` as defined in the adapter's planned logic.
