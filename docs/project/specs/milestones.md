I have updated the project specifications to reflect a major protocol shift and a series of UX/stability refinements. Your task is to partition these requirements into three distinct implementation milestones:

1. **Milestone 1: Structural Protocol & Parser:** Implement the `## Message` section logic in the `MarkdownPlanParser`, deprecate the old `INVOKE`/`RETURN`/`PROMPT` actions, and ensure the `ExecutionOrchestrator` handles "Message Turns" correctly. Then also update all prompts accordingly once handling is implemented.
2. **Milestone 2: TUI & CLI UX Polish:** Implement the Alt+Up/Down section navigation, the context node `(e)` editing logic, the model/cost display in the `ActionTree`, and the new CLI abbreviations (`-a`, `-m`, `-c`) for the `start` command.
3. **Milestone 3: Stability & Infrastructure:** Implement 403 error bypassing in `WebScraperAdapter`, recursive directory expansion in `ContextService`, and SSL retry logic for the LLM client.

## Bug fixes & stability

1. Litellm warning messages popping up in real testpypi deployement (but not showing in local dev version):
```
raphaelatteritano@Raphaels-MacBook-Pro test % teddy start
Checking configurations...
16:42:10 - LiteLLM:WARNING: common_utils.py:979 - litellm: could not pre-load bedrock-runtime response stream shape — Bedrock event-stream decoding will be unavailable. Error: No module named 'botocore'
litellm: could not pre-load bedrock-runtime response stream shape — Bedrock event-stream decoding will be unavailable. Error: No module named 'botocore'
16:42:10 - LiteLLM:WARNING: common_utils.py:24 - litellm: could not pre-load sagemaker-runtime response stream shape — SageMaker event-stream decoding will be unavailable. Error: No module named 'botocore'
litellm: could not pre-load sagemaker-runtime response stream shape — SageMaker event-stream decoding will be unavailable. Error: No module named 'botocore'

--- MESSAGE from TeDDy ---
What are we working on?
```
2. [[Bypass 403 errors]]:
### `READ`: [https://www.pnas.org/doi/10.1073/pnas.2416294121](https://www.pnas.org/doi/10.1073/pnas.2416294121)
- **Status:** FAILURE
- **Description:** Article 1
- **Details:** `403 Client Error: Forbidden for url: https://www.pnas.org/doi/10.1073/pnas.2416294121`
3. BUG - teddy context should not crash if path in context filesis a directory, instead return all files in it (recursively) also always ensure deduplication
4. [[BUG - Reading raw github links]]:
### READ: [https://raw.githubusercontent.com/lllyasviel/LayerDiffuse/main/README.md](https://www.google.com/url?sa=E&q=https%3A%2F%2Fraw.githubusercontent.com%2Flllyasviel%2FLayerDiffuse%2Fmain%2FREADME.md)

- **Status:** SUCCESS

- **Description:** Reading the official LayerDiffuse documentation to understand its layer generation and manipulation capabilities.

- **Details:** {'content': ''}
5. BUG - editor view in TUI (example pressing `e` on EDIT action) opens VScode , should select editor from config
6. [[BUG - llm completion failed (maybe should implement re-attempt logic)]]:
[10] help-refine-prompts-debugger-add | Waiting for pathfinder to respond...
• Model: openrouter/deepseek/deepseek-v4-flash
• Context: 59.0k / 1048.6k tokens
• Session Cost: $0.0599

Error: LLM Completion failed: litellm.APIError: APIError: OpenrouterException - [SSL: SSLV3_ALERT_BAD_RECORD_MAC] ssl/tls alert bad record mac (_ssl.c:2658)
7. BUG - Resource contents should not be there in report.md if in session mode (currently gets added - I've observed it in a failed READ action being added even if file was considered already in context) - we instead use input.md context gathering for getting file contents
8. If file gets modified during execution (eg EXECUTE modifies the file to EDIT) it crashes TeDDy instead of returning a FAILURE for EDIT action
9. All actions - ignore any unforeseen codeblock or thematic break after action block (like for READ action) without throwing validation error (clean up automatically in session mode)
10. ignore and clean up trailing text like this closing fence: `~~~~~~ Useful link: [src/teddy_executor/core/services/context_service.py](/src/teddy_executor/core/services/context_service.py)`


## TUI & polishing changes

1. Add model and session cost in right panel when on Context Root element (also ensure same rounding everywhere).
2. when editing long param prevent multi line breakup for long text or multiline text -> if long text or multiline is detected make it edit in editor instead of directly in TUI
3. have same padding as right panel for rationale items has for all right panel cases and also left panel as well
4. In hint appended to user request message say to also update reference documents accordingly if needed
5. RESEARCH - scrape & return full contents instead of just snippets (remove hint to read results provided)
