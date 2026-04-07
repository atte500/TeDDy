# Experiment: Isolation Rule Enforcement for INVOKE, PROMPT, and RETURN

- **Related Artifacts:** [src/teddy_executor/core/services/action_executor.py](/src/teddy_executor/core/services/action_executor.py)
- **Status:** Validating Assumption

## Objective & Requirements
The goal is to ensure that `INVOKE`, `PROMPT`, and `RETURN` actions are soft-isolated (automatically skipped in -y mode and deselected in --tui mode) if they are not the only action in the plan. If they are `SKIPPED` the execution report should always show a reason saying: `"This action must be performed in isolation."`.

## Experiment Log
### Baseline Establishment
- *Hypothesis:* Current `ActionExecutor` uses a different skip reason and may not cover all three terminal actions (`INVOKE`, `PROMPT`, `RETURN`) under the same isolation logic.
- *Experiment:* Create `spikes/test_isolation_rules.py` to verify current behavior when multiple actions include a terminal action.
- *Observation:* `INVOKE`, `PROMPT`, and `RETURN` were skipped, but with the reason: `"Action skipped to ensure state isolation; must be executed as a single-action plan."`.
- *Conclusion:* `ActionExecutor` needs a specific update to its skip reason to match the requirements.

### Hypothesis Implementation (Non-Interactive)
- *Hypothesis:* Updating the skip reason in `ActionExecutor._check_action_isolation` to `"This action must be performed in isolation."` will fulfill the soft-isolation requirement for non-interactive modes.
- *Experiment:* Create `prototypes/isolation_logic.py` overriding the isolation check and run `spikes/test_isolation_rules.py` against it.
- *Observation:* The `PrototypeActionExecutor` correctly identified all terminal types (`INVOKE`, `PROMPT`, `RETURN`) and returned the required skip reason `"This action must be performed in isolation."` when `total_actions > 1` in non-interactive mode.
- *Conclusion:* The implementation effectively enforces soft-isolation. The required skip reason is now consistently applied across all terminal actions.
