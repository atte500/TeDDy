<!--
Destination: docs/project/debugging/NN-{bug-slug}.md
Naming: NN = Sequential Bug Number (e.g. 01, 02).
-->

# Bug: {{Bug Title}}
- **Status:** Unresolved
- **Milestone:** [link]
- **Vertical Slice:** [link]
- **Specs:** [links]

## Symptoms
Expected vs. actual behavior and minimal reproduction steps.

## Context & Scope
### Regressing Delta
Git commit hash, file paths, and line numbers of the regressing change.

### Environmental Triggers
OS, runtime version, environment variables, or specific configurations required to reproduce.

### Ruled Out
Components, modules, or hypotheses definitively eliminated during investigation.

## Diagnostic Analysis
### Causal Model
Concise description of how the faulty system operates based strictly on verified observations.

### Discrepancies
- [ ] Discrepancy between expected and observed behavior.
- [x] Discrepancy between expected and observed behavior (Resolved: explanation of root cause).

### Investigation History
Continuously log diagnostic attempts and findings in chronological order:
1. Investigated whether [hypothesis] by [action/probe]; observed [outcome], which [conclusion].
2. Investigated whether [hypothesis] by [action/probe]; observed [outcome], which [conclusion].

## Solution
### Root Cause
Summary of the verified root cause and whether the fix was directly applied to production code or proven in the sandbox replica.

### Affected Components
Direct upstream callers, downstream dependencies, or shared contracts affected by the fix:
- `ComponentName`: Description of changes required or completed.
