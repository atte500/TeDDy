# Component Design: Configuration Schema
- **Status:** Implemented
- **Classification:** Core Domain
- **Source:** [`src/teddy_executor/core/domain/models/config_schema.py`](/src/teddy_executor/core/domain/models/config_schema.py)

## Purpose
Declares the typed view of every fixed configuration key, builds that view from the merged YAML mapping, and owns the two pure resolvers that turn the `agents` block into a per-persona LLM overlay and the effective model. It is the internal typing layer behind `IConfigService`; the end-user `config.yaml` shape is unchanged.

## Consumers
- [`YamlConfigAdapter`](../../adapters/outbound/yaml_config_adapter.md): Builds the typed `app_config` view through `construct_app_config` and reads declared keys through `is_declared_key` / `read_declared_value`.
- [`PlanningService`](../services/planning_service.md): Resolves the persona overlay and the effective model with `resolve_agent_llm_overrides` and `resolve_effective_model`.
- [`SessionOrchestrator`](../services/session_orchestrator.md): Resolves the effective model in the fallback context path with the same two resolvers.
- [CLI Adapter](../../adapters/inbound/cli.md): Resolves the effective model for the startup identity banner.

## Dependencies
- **`ConfigurationError`** (`teddy_executor.core.domain.models.exceptions`): Raised for an uncoercible value, an out-of-range value, or a malformed `agents` block.

## Class Invariants
- `canonical_defaults`: Every declared key has exactly one canonical default, held in `DEFAULT_APP_CONFIG`.
- `exact_flat_first`: A flat dotted key outranks the nested path, mirroring `get_setting`.
- `typed_coercion`: A declared value coerces to its declared type, and an uncoercible value raises `ConfigurationError` naming the key.
- `forward_compatible_unknowns`: An undeclared top-level group is ignored so future keys stay valid.
- `raising_agents_seam`: `construct_app_config` shape-validates the `agents` block at load, where an empty persona entry counts as a declared persona with no overrides; the two resolvers stay total at runtime and never raise.

## Inbound Ports
None — this is an internal domain module, not a port.

## Outbound Ports
None — the module is pure and declares no injected dependencies.

## Data Contracts
- **`AppConfig`** (frozen dataclass): The typed root, composed of the per-group config dataclasses (`ExecuteConfig`, `EditConfig`, `WorkspaceConfig`, `ReadConfig`, `PlanConfig`, `ContextConfig`, `ResearchConfig`, `ChecksConfig`, `AutoPruningConfig`, `GuardrailsConfig`) plus the top-level `editor` and `yolo_default` scalars.
- **`AutoPruningConfig`**: Carries the retention ceiling `max_turns_retention` (int, default `10`) and `retention_batch` (int, default `5`, inclusive minimum `1`), the number of oldest turns dropped together once that ceiling is exceeded, alongside the existing auto-pruning flags and limits.
- **`ConfigurationError`**: Raised for a bad declared value or a malformed `agents` block.

## Operations

### `construct_app_config(merged) -> AppConfig`
- **Preconditions:** `merged` is the merged bundled-plus-user configuration mapping.
- **Postconditions:** Returns the typed view. Each declared key resolves exact-flat-first then nested, coerces to its declared type, falls back to its default when absent or empty, and rejects an out-of-range value. A valid `agents` block is validated and leaves the typed view at its defaults.
- **Exceptions:**
  - `ConfigurationError`: An uncoercible value, an out-of-range value, a non-mapping `agents` block, a non-empty non-mapping persona entry, or two persona keys differing only in case.

### `resolve_agent_llm_overrides(agents_block, persona) -> dict`
- **Preconditions:** None; the input may be malformed.
- **Postconditions:** Returns a copy of the matching persona's entry with a blank `model` removed, or an empty mapping when no persona matches. Persona matching is case-insensitive.
- **Exceptions:** None — the resolver is total and never raises.

### `resolve_effective_model(override, persona_model, global_model) -> str`
- **Preconditions:** None.
- **Postconditions:** Returns the first non-blank string among the override, the persona model, and the global model; returns an empty string when every candidate is blank.
- **Exceptions:** None.
