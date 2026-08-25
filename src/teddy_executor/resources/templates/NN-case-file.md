# Bug: {{bug_title}}
- **Status:** Unresolved
- **Milestone:** [link or N/A]
- **Vertical Slice:** [link or N/A]
- **Specs:** [links or N/A]

## Symptoms

**Format:** Describe what should happen vs. what actually happens. Include concrete, reproducible steps to trigger the bug.
Expected vs. Actual behavior and minimal reproduction steps.

## Context & Scope
### Regressing Delta

**Format:** Git commit hash, file paths, and line numbers of the changes that introduced the bug.
[Identify the exact changes responsible for the regression to narrow the search space.]

### Environmental Triggers

**Format:** OS, Python version, config values, environment variables, or any other necessary conditions.
[Describe the specific OS, configurations, or state conditions required to reproduce the issue.]

### Ruled Out

**Format:** Bulleted list of investigated and ruled-out items.
[List any components, layers, or files definitively proven to be unrelated to the bug.]

## Diagnostic Analysis
### Causal Model

**Format:** 1-3 paragraphs explaining the chain of events leading to the bug. Continuously updated as investigation progresses.
A concise, causal description of how the faulty SUT operates.

### Discrepancies

**Format:** `- Observation. Conflict. (Resolved: Explanation)` — keep resolved items with their resolution.
A concise list of observations that contradict the current Causal Model.
- Observation. Conflict. (Resolved: Explanation)

### Investigation History

**Format:** `N. Hypothesis. Observation. Conclusion.`
A concise, numbered log of investigation attempts.
N. Hypothesis. Observation. Conclusion.

## Solution

**Format:** 1-2 paragraphs explaining the root cause, the specific fix applied, and any systemic changes needed to prevent this class of bug.
A high-level explanation of the root cause, the proven fix, and the systemic preventative measures to prevent this class of issue globally.
