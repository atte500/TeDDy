**Status:** Planned

## 1. Purpose / Responsibility
Implements the `IPlanReviewer` port using the `Textual` TUI framework. It provides a rich, interactive terminal experience for reviewing and modifying plans.

## 2. Ports
- **Implements Inbound Port:** `IPlanReviewer`
- **Uses Outbound Ports:**
  - `ISystemEnvironment`: For launching external editors for "Context-Aware Editing".

## 3. Implementation Details / Logic
1. **App Structure:** A `textual.app.App` containing a `TreeView` (or `ListView`) of actions.
2. **Tiered Interaction:**
   - **Tier 1:** Summary view (Header/Footer).
   - **Tier 2:** Detail view/Checklist (Tree).
3. **Modification Logic:**
   - When a user selects "Modify/Preview" (key `p`), the adapter uses the `ISystemEnvironment` to open a temporary file in the user's editor.
   - Upon editor close, the adapter parses the temporary file (or uses the returned path) to update the `ActionData` in-memory.
4. **Return Path:** The `app.run()` call returns the final `Plan` object.

## 4. Data Contracts / Methods
Refer to the [IPlanReviewer](/docs/architecture/core/ports/inbound/plan_reviewer.md) port for method signatures.

### Implementation Notes:
- **Refactoring Requirement:** The `Plan` and `ActionData` models must be unfrozen to support direct in-memory updates by the TUI.
