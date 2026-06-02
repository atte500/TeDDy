- **Status:** Implemented

## Purpose / Responsibility
Reduces context size by deselecting irrelevant or failed turns from `turn.context`.

## Implementation Details / Logic
### Successful Message-Turn Exception
1. When scanning turns for pruning:
2. Read the `plan.md` for each turn.
3. If the plan contains a `## Message` section AND the `status` is Green (no 🔴/🟡 in status line):
4. **EXCEPTION**: This turn is immune to pruning based on retention limits or context budget. This preserves conversational thread continuity.

## Data Contracts / Methods
### `prune(context: ProjectContext, current_status: Optional[str]) -> ProjectContext`
Applies heuristics to deselect items.
