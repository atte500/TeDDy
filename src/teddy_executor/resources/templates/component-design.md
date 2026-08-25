# Component Design: {{component_name}}
- **Status:** [Planned | Implemented | Refactoring]

## Purpose / Responsibility

**Format:** 1-2 sentences describing what this component does and why it exists.
The core responsibility and role of this component within the system.

## Failure Modes

**Format:** For each failure mode, describe the precondition or invariant violated and the expected exception/behavior.
Explicitly list known failure modes for this component.
- **Failure Title**: Violates the precondition/postcondition 'XYZ'. The component MUST raise a specific exception rather than returning a partial/invalid result.

## Class Invariants

**Format:** Bulleted list of invariants. For stateless components, explicitly state \"None — stateless component.\"
Document conditions that must always hold true for instances of this component. If none, state: "None — stateless component."

## Ports

**Format:** Describe the interfaces this component depends on (outbound ports) and provides (inbound ports). For each port: name, role, key methods.
Explicit inbound/outbound relationships.

## Implementation Details / Logic

**Format:** Pseudocode, algorithm descriptions, or references to external patterns. Include key decision points and rationale.
Detailed implementation strategy and algorithms.

## Data Contracts / Methods


**Format:** For each method, define Preconditions, Postconditions, Exceptions, and optional Invariants. Use the template structure provided below.
### `method_name`

**Format:** Use subheadings: Preconditions, Postconditions, Exceptions, Invariants (optional).
- **Preconditions:** What must be true before calling.
- **Postconditions:** What is guaranteed after successful return.
- **Exceptions:** What errors can be raised and under what conditions.
- **Invariants:** (optional) Class-level invariants that must hold before and after this method executes.

**Contract Enforcement:** Implementations MUST validate preconditions with explicit guard clauses. Postcondition failures MUST be surfaced as specific exceptions, never swallowed.

### Directory Conventions
Doc path: `docs/architecture/BOUNDARY/LAYER/TYPE/name.md` -> Source path: `src/{pkg}/BOUNDARY/LAYER/TYPE/name.py` -> Test path: `tests/suites/TEST_TYPE/BOUNDARY/LAYER/TYPE/test_name.py`
