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
- [ ] Logic - Refactor `src/teddy_executor/core/services/action_executor.py`: Replace `except Exception:` in `_enrich_failed_log` with logging.
- [ ] Logic - Refactor `src/teddy_executor/core/services/execution_orchestrator.py`: Replace silent `pass` with `# nosec` in temp file cleanup with `logger.debug`.
- [ ] Logic - Refactor `src/teddy_executor/core/services/session_planner.py`: Replace silent `pass` blocks in message/name resolution with diagnostic logging.
- [ ] Logic - Refactor `src/teddy_executor/adapters/inbound/cli_helpers.py`: Clean up 4+ `nosec` blocks to ensure report formatting errors are visible.
- [ ] Logic - TUI Sweep: Update `textual_plan_reviewer_*.py` and `console_interactor_helpers.py` to replace broad catches and `nosec` tags with specific error-state messages for the user.
- [ ] Cleanup - Final validation: Execute `grep -rn "# nosec B110" src/` to ensure all "intentional" silent failures are converted to "transparent" failures.

## Delta Analysis
- **action_executor.py**: `except Exception` in log enrichment hides filesystem errors.
- **session_planner.py**: Silent `pass` in turn resolution can lead to disconnected conversation history.
- **nosec B110 Audit**: 15+ instances found where security linters were bypassed to allow silent failures. These MUST be replaced with either logging or a detailed comment justifying the no-op.

## Guidelines for Implementation
- Follow the "Context-First" strategy: add informative messages (e.g., `raise RuntimeError(f"Action {name} failed") from e`).
- Ensure every `try/except` block being modified has a clear justification for its existence or is removed if redundant.
- Use the project's `logging` system to record errors that are caught for UI stability.
