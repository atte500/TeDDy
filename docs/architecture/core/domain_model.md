# Component Design: Domain Model
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/domain/models/__init__.py`](/src/teddy_executor/core/domain/models/__init__.py)

## Purpose
Defines the core domain entities, value objects, and ubiquitous language of TeDDy. Every service, port, and adapter exchanges these types, so this package is the shared vocabulary that keeps the core independent of any infrastructure.

## Consumers
- [`ExecutionOrchestrator`](../services/execution_orchestrator.md): Exchanges `Plan`, `ExecutionReport`, and `ReportAssemblyData`.
- [`ActionFactory`](../services/action_factory.md): Builds handlers from `ActionData` and reads `ActionPorts`.
- [`ActionDispatcher`](../services/action_dispatcher.md): Produces `ActionLog` records and reads `ShellOutput`.
- [`ContextService`](../services/context_service.md): Builds `ProjectContext` and `ContextItem` instances.
- [`PlanningService`](../services/planning_service.md): Consumes `ProjectContext` and `Plan`.
- [`PlanValidator`](../services/plan_validator.md): Accumulates `ValidationError` records.
- [`SessionService`](../services/session_service.md): Persists the `ExecutionReport` and reads `SessionOptions`.
- [ShellAdapter](../../adapters/outbound/shell_adapter.md): Populates `ShellOutput`.
- [TextualPlanReviewer](../../adapters/inbound/textual_plan_reviewer.md): Mutates `Plan` and `ActionData` during review.
- [Composition Root](/src/teddy_executor/container.py): Constructs the port bundles `ActionPorts`, `OrchestratorPorts`, `PlanningPorts`, and `SessionPorts`.

## Dependencies
None — the package imports only the Python standard library and declares no injected ports.

## Class Invariants
- `frozen_report_types`: `ActionLog`, `RunSummary`, `ExecutionReport`, `ValidationError`, `ChangeSet`, `DriftReport`, `ReportAssemblyData`, and `SessionOptions` are frozen dataclasses; instances are immutable after construction.
- `mutable_plan_types`: `Plan` and `ActionData` are standard, non-frozen dataclasses, so the interactive reviewer can edit parameters and selection state in memory before execution.
- `mutable_context_types`: `ProjectContext` and `ContextItem` are standard dataclasses, and `ContextItem.selected` is mutated by the reviewer.
- `plan_requires_actions`: `Plan.__post_init__` asserts that `actions` is non-empty.
- `optional_config_port`: `ActionPorts.config_service` defaults to `None` and is the only optional field in that bundle.
- `optional_ports_in_other_bundles`: `OrchestratorPorts` marks `plan_reviewer` and `interrupt_guard` optional, and `SessionPorts` marks `plan_parser`, `time_service`, and `report_assembler` optional.
- `typed_dict_payloads`: `ShellOutput`, `SearchResult`, `QueryResult`, and `WebSearchResults` are `TypedDict`s, so they are structurally typed mappings rather than instantiable classes.

## Inbound Ports
None — this package defines passive data structures, not use-case interfaces.

## Outbound Ports
None — this package declares no injected dependencies.

## Data Contracts

### Enumerations
- **`ActionType`** (`plan.py`, str Enum): `CREATE`, `READ`, `EDIT`, `EXECUTE`, `RESEARCH`, `MESSAGE`.
- **`ExecutionStatus`** (`plan.py`, str Enum): `PENDING`, `RUNNING`, `SUCCESS`, `FAILURE`, `SKIPPED`.
- **`RunStatus`** (`execution_report.py`, str Enum): `SUCCESS`, `FAILURE`, `VALIDATION_FAILED`, `SKIPPED`, `ABORTED`, `INTERRUPTED`.
- **`ActionStatus`** (`execution_report.py`, str Enum): `SUCCESS`, `FAILURE`, `SKIPPED`, `PENDING`, `INTERRUPTED`.

### Plan aggregate (`plan.py`)
- **`Plan`** (dataclass): `title`, `rationale`, `actions: Sequence[ActionData]`, `metadata: dict[str, str]`, `source_doc`, `is_session`, `plan_path`, `raw_content`. Exposes `is_communication_turn()`.
- **`ActionData`** (dataclass): `type`, `params`, `description`, `selected`, `modified`, `modified_fields`, `executed`, `state: ExecutionStatus`, `action_log: Optional[ActionLog]`, `user_response`, `pending_temp_file`, `node`, `similarity_score`, `similarity_scores`. Exposes the `is_terminal` property.
- **`ValidationError`** (frozen dataclass): `message`, `action_index`, `file_path`, `offending_node`.
- **`DEFAULT_SIMILARITY_THRESHOLD`**: module constant `0.95`.

### Execution report (`execution_report.py`)
- **`ActionLog`** (frozen dataclass): `status: ActionStatus`, `action_type`, `params`, `details`, `modified`, `modified_fields`, `failed_command`.
- **`RunSummary`** (frozen dataclass): `status: RunStatus`, `start_time`, `end_time`, `error`.
- **`ExecutionReport`** (frozen dataclass): `run_summary`, `plan_title`, `rationale`, `user_request`, `is_session`, `metadata`, `original_actions`, `action_logs`, `validation_result`, `validation_ast`, `failed_resources`.

### Project context (`project_context.py`)
- **`ContextItem`** (dataclass): `path`, `token_count`, `git_status`, `scope`, `selected`, `auto_prune_reason`.
- **`ProjectContext`** (dataclass): `header`, `content`, `scoped_paths`, `git_status`, `items`, `agent_name`, `system_prompt_tokens`, `content_tokens`, `total_window`.

### Port bundles
- **`ActionPorts`** (frozen dataclass, `action_ports.py`): `shell_executor`, `file_system_manager`, `user_interactor`, `web_scraper`, `web_searcher`, `config_service`.
- **`OrchestratorPorts`** (frozen dataclass, `orchestrator_ports.py`): `plan_parser`, `plan_validator`, `action_executor`, `file_system_manager`, `report_assembler`, `user_interactor`, `plan_reviewer`, `interrupt_guard`.
- **`PlanningPorts`** (frozen dataclass, `planning_ports.py`): `context`, `llm`, `fs`, `config`, `prompts`, `ui`, `session_manager`.
- **`SessionPorts`** (frozen dataclass, `planning_ports.py`): `session_service`, `file_system_manager`, `report_formatter`, `user_interactor`, `session_planner`, `replanner`, `plan_parser`, `time_service`, `report_assembler`.

### Supporting value objects
- **`ChangeSet`** (frozen dataclass, `change_set.py`): `path: Path`, `before_content`, `after_content`, `action_type`.
- **`DriftReport`** (frozen dataclass, `drift_report.py`): `edited_prompts`, `missing_prompts`, `edited_templates`, `missing_templates`. Exposes `prompts_drifted`, `templates_drifted`, and `has_drift`.
- **`ReportAssemblyData`** (frozen dataclass, `report_assembly_data.py`): `plan`, `action_logs`, `start_time`, `message`, `is_session`.
- **`SessionOptions`** (frozen dataclass, `session.py`): `name`, `agent_name`, `initial_request`, `additional_context`, `model`, `provider`, `api_key`.
- **`ShellOutput`** (TypedDict, `shell_output.py`): `stdout`, `stderr`, `return_code`, `failed_command`, `interrupted`.
- **`SearchResult`**, **`QueryResult`**, **`WebSearchResults`** (TypedDicts, `web_search_results.py`): the nested web-search payload structure.

### Domain exceptions (`exceptions.py`)
- **`SearchTextNotFoundError`** (`ValueError`): carries `content`.
- **`FileAlreadyExistsError`** (`FileExistsError`): carries `file_path`.
- **`MultipleMatchesFoundError`** (`Exception`): carries `content`.
- **`WebSearchError`** (`Exception`): carries `original_exception`.
- **`ConfigurationError`** (`Exception`): carries `message`.

## Operations
None — the package holds data only. The sole behavior is the pure helper `Plan.is_communication_turn()` and the `ActionData.is_terminal` property.
