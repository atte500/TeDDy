# Milestone: Pruning Policy Refinement
- **Status:** Planned
- **Depends On:** None
- **Specs:** [context-payload-format](../specs/context-payload-format.md)

## Goal
Make the history an agent keeps a function of turn recency instead of file size. The global token budget deselects the largest Turn-scope files first, so a turn that spent its budget reading one large document evicts healthy history from the middle of the payload: that mechanism owns 10 of the 31 mid-history holes measured across the shipped layout, and 33 of 86 assemblies (38.4%) sit above the 50,000-token threshold where it acts at all. The user pays for that loss twice — in cache bytes, because a mid-history removal ends the shared prefix earlier than an append would, and in reasoning evidence, because a removed turn's plan and report leave the working context together with the finding they recorded.

## Requirements
1. **Recency-ordered victim selection:** When the selected Turn-scope total exceeds `auto_pruning.turn_context_threshold`, the budget must choose victims by turn age, and must never deselect a turn's own `plan.md` or `report.md` while an older turn's files remain selected.
2. **Bounded context:** The budget must still bring the Turn-scope total at or under the threshold. The policy changes which files leave, never whether the budget acts.
3. **Observable pruning cause:** A deselected turn must be named, with its cause, at the history tail, so a gap in the rendered history stays distinguishable from a rendering defect. Gated on evidence: it is built only if Requirement 1 still leaves holes that cost context.

## Constraints
- **Retention semantics unchanged:** `max_turns_retention` stays a ceiling and `retention_batch` the drop size past it; the ceiling's arithmetic is not part of this milestone.
- **Validation pruning unchanged:** a validation-failed turn is removed only once a later non-validation turn succeeds, so consecutive failures stay visible.
- **Graded, not asserted:** every policy change is graded against the replayed prefix-share metric over the shipped-layout corpus, and a policy that raises cache share by discarding history is not a win.
- **Non-goal:** payload section order. History-before-resources is measured as optimal on every corpus session and stays as shipped.
- **Non-goal:** the plan-status heuristic. Ad-hoc slice `00-56` removes it before this milestone starts, so no requirement here depends on it.

## Slices
Slice documents are written when the milestone starts; the decomposition below is the intended order.
- [ ] **Budget eviction policy** (`07-01-budget-eviction-policy`): recency-ordered victim selection with a turn's own plan and report exempt, plus the graded comparison against the current largest-first policy.
- [ ] **Pruned-turn notice** (`07-02-pruned-turn-notice`): name each deselected turn and its cause at the history tail, admitted only if the first slice leaves context-costing holes.
