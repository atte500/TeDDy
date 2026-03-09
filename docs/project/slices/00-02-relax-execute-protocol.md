# Slice: Relax `EXECUTE` Action Protocol

## Business Goal
To simplify the `EXECUTE` action protocol by allowing shell chaining and removing the mandatory `Setup` parameter. This shifts the responsibility for "clean" commands from the system's validation layer to the agent's prompting, adhering to the "small, sharp tools" philosophy.

## Acceptance Criteria
- **Chaining Allowed:** The `EXECUTE` action must allow shell operators (`&&`, `||`, `;`, `|`).
- **Setup Removed:** The `Setup` parameter is no longer parsed or validated. Any environment preparation (like `cd`) must be done via chaining within the command block.
- **Statelessness Maintained:** Each `EXECUTE` block still runs in its own process; changes do not persist between separate blocks.
- **Documentation Updated:** `ARCHITECTURE.md`, `plan-format.md`, and `plan-format-validation.md` must be updated to reflect this new standard.

## User Showcase
1. Create a plan with a chained `EXECUTE` action:
   ```markdown
   ### EXECUTE
   - Description: Test chaining
   `` `shell
   mkdir -p temp_test && cd temp_test && touch success.txt && ls
   `` `
   ```
2. Run `teddy execute` on the plan.
3. Verify that validation passes and the command executes successfully, showing `success.txt` in the output.
4. Verify that a subsequent `### EXECUTE: ls` does NOT see `success.txt` (confirming statelessness).

## Architectural Changes
- **Parser:** Update `src/teddy_executor/core/services/action_parser_strategies.py` to stop looking for the `Setup` parameter.
- **Validator:** Update `src/teddy_executor/core/services/validation_rules/execute.py` to remove the check for shell chaining operators and the check for `cd`/`export` directives.

## Deliverables
- [ ] Modified `MarkdownPlanParser` (via strategies) to remove `Setup` extraction.
- [ ] Modified `PlanValidator` to allow chaining and directives in `EXECUTE`.
- [ ] Updated `docs/architecture/ARCHITECTURE.md` (Key Decisions).
- [ ] Updated `docs/project/specs/plan-format.md`.
- [ ] Updated `docs/project/specs/plan-format-validation.md`.
- [ ] New integration test verifying a chained command works as expected.
