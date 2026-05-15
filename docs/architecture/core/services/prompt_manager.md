# Component: PromptManager

The `PromptManager` is responsible for resolving agent configurations, system prompts, and metadata for the session audit trail.

## Instruction Resolution (Pure Context Model)
In the "Pure Context" model, `PromptManager` does NOT provide instructions for the AI's LLM calls. Its role in message resolution is strictly metadata-focused:
- **Audit Trail Resolution:** It resolves the `user_request` (feedback or CLI message) to ensure it is accurately captured in the `ExecutionReport` and `meta.yaml`.
- **Report Seeding:** This metadata ensures the `ExecutionReportAssembler` can generate a `report.md` that correctly documents the user's intent for the turn, which the AI will then "discover" as context in the subsequent turn.
- **Goal Persistence:** It manages the retrieval of the immutable session goal (`initial_request.md`) from the session root.

## 1. Purpose / Responsibility
The `PromptManager` provides a centralized service for all prompt and metadata resolution. It abstracts the filesystem and internal resources to provide a clean API for other services to retrieve agent-specific logic and user-provided instructions.

## 2. Ports
- **Implements Outbound Port:** `IPromptManager`
- **Uses Outbound Ports:**
    - `IFileSystemManager` (to read prompt XMLs and meta YAMLs)
    - `IUserInteractor` (to prompt for instructions if missing)
