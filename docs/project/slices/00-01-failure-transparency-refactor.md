# Slice: Failure Transparency Refactor
- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Specs:** N/A

## Business Goal
Apply the newly codified "Failure Transparency" (Stop the Line) standards to the existing codebase to eliminate silent failures and improve system diagnosability. This is a foundational refactor to ensure future development is built on transparent error handling.

## Scenarios
> As a Developer, I want a clear trace of what went wrong when an action fails, so that I can quickly isolate the root cause.

```gherkin
Given a plan execution that encounters a logic error inside an action
When the action_executor attempts to run the action
Then it MUST NOT swallow the exception via except Exception:
And it MUST log the error or re-raise with context.
```

## Deliverables
- [x] Logic - Refactor `src/teddy_executor/core/services/action_executor.py`: Replace `except Exception:` in `_enrich_failed_log` with logging.
- [x] Logic - Refactor `src/teddy_executor/core/services/execution_orchestrator.py`: Replace silent `pass` with `# nosec` in temp file cleanup with `logger.debug`.
- [x] Logic - Refactor `src/teddy_executor/core/services/session_planner.py`: Replace silent `pass` blocks in message/name resolution with diagnostic logging.
- [x] Logic - Refactor `src/teddy_executor/adapters/inbound/cli_helpers.py`: Clean up 4+ `nosec` blocks to ensure report formatting errors are visible.
- [x] Logic - TUI Sweep (Part 1): Refactor `src/teddy_executor/adapters/outbound/console_interactor_helpers.py` (Terminal restoration failures).
- [ ] Logic - TUI Sweep (Part 2): Refactor `src/teddy_executor/adapters/inbound/textual_plan_reviewer_app.py` (App lifecycle and mounting).
- [ ] Logic - TUI Sweep (Part 3): Refactor `src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py` (External editor/diff subprocesses).
- [ ] Logic - TUI Sweep (Part 4): Refactor `src/teddy_executor/adapters/inbound/textual_plan_reviewer_previews.py` and `textual_plan_reviewer_execution.py` (Diff generation and status updates).
- [ ] Logic - TUI Sweep (Part 5): Refactor `src/teddy_executor/adapters/inbound/textual_plan_reviewer_helpers.py` (Formatting and utility failures).
- [ ] Cleanup - Final validation: Execute `grep -rn "# nosec B110" src/` to ensure all "intentional" silent failures are converted to "transparent" failures.

## Delta Analysis
- **action_executor.py**: `except Exception` in log enrichment hides filesystem errors.
- **session_planner.py**: Silent `pass` in turn resolution can lead to disconnected conversation history.
- **nosec B110 Audit**: 15+ instances found where security linters were bypassed to allow silent failures. These MUST be replaced with either logging or a detailed comment justifying the no-op.

## Guidelines for Implementation
- Follow the "Context-First" strategy: add informative messages (e.g., `raise RuntimeError(f"Action {name} failed") from e`).
- Ensure every `try/except` block being modified has a clear justification for its existence or is removed if redundant.
- Use the project's `logging` system to record errors that are caught for UI stability.

## Implementation Notes
- `action_executor.py`: Added module-level `logger` and replaced silent `except Exception:` in `_enrich_failed_log` with a `logger.debug` call. Kept the `except Exception:` broad since the operation is explicitly a "best effort" context enrichment that must not block the core execution flow.
- `execution_orchestrator.py`: Added module-level `logger` and replaced `except Exception: # nosec B110 \n pass` in the `finally` block of `execute` with `logger.debug("Failed to clean up temporary plan file...")`.
- `session_planner.py`: Added module-level `logger` and replaced silent `pass` statements in `_resolve_message_from_previous_turn` and `_handle_dynamic_rename` with `logger.debug` calls, surfacing non-fatal file read/parsing errors.
- `cli_helpers.py`: Added module-level `logger` and replaced 4 silent failure points (`# nosec` and `pass`) in `echo_and_copy`, `create_failure_report`, and `handle_validation_failure` with `logger.debug` diagnostics. Verified that adding `logging` to this foundational utility did not regress CLI performance or stability.
- `console_interactor_helpers.py`: Initialized module-level `logger` and replaced the silent `except Exception: # nosec B110 \n pass` in `restore_terminal_mode` with a `logger.debug` call. This ensures that platform-specific terminal restoration failures are visible in debug logs without crashing the application during cleanup.
