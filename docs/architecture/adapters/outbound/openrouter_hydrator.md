# Component Design: OpenRouterMetadataHydrator
- **Status:** Implemented
- **Classification:** Outbound Adapter
- **Source:** [`src/teddy_executor/adapters/outbound/openrouter_hydrator.py`](/src/teddy_executor/adapters/outbound/openrouter_hydrator.py)

## Purpose
Implements the adapter-layer `IOpenRouterHydrator` port, resolving live model metadata (context window and per-token pricing) from the OpenRouter catalog for models absent from the `litellm` registry. A persistent catalog cache with a configurable TTL keeps the network traffic to one fetch per TTL window.

## Consumers
- [`LiteLLMAdapter`](./litellm_adapter.md): Calls `get_metadata` while hydrating an unmapped model — pre-emptively from `get_context_window` and reactively from `_hydrate_all_candidates` on a not-found error and on a cost recompute failure.
- [Composition Root](/src/teddy_executor/registries/infrastructure.py): Registers the adapter against `IOpenRouterHydrator` as a singleton and injects it into `LiteLLMAdapter`.

## Dependencies
- [`IConfigService`](../../core/ports/outbound/config_service.md): Read for the `llm.registry_cache_ttl_days` setting. Optional; without it the TTL falls back to seven days.
- **`requests`** (external): Performs the catalog GET with a 10-second timeout.
- **`IOpenRouterHydrator`** (`teddy_executor.adapters.outbound.litellm_adapter`): The adapter-layer protocol this component implements.

## Class Invariants
- `catalog_memoized_per_instance`: The first successful catalog load stores the list in `_cached_models`; later calls return it without reading the cache file or the network.
- `cache_disabled_by_default`: A `None` `cache_path` keeps the network-only behaviour, so zero-argument construction neither reads nor writes a cache file.
- `cache_never_fatal`: An unreadable cache is treated as a miss and a persist failure logs a warning; neither propagates.
- `empty_catalog_never_persisted`: Persistence returns early on an empty catalog, so a failed fetch cannot replace a usable cache with an empty list.
- `ttl_boundary_expired`: An entry is expired when `now - fetched_at_epoch >= ttl`, so a cache sitting exactly on the TTL boundary refetches.
- `positive_cache_rates_only`: The cache-cost pricing keys appear only for rates strictly greater than zero, because a `0.0` rate would bill cached tokens at zero.

## Inbound Ports
- **`IOpenRouterHydrator`**: `get_metadata(model_id: str) -> Optional[Dict[str, Any]]`, the only operation the adapter layer consumes.

## Outbound Ports
- **`IConfigService`**: `get_setting(key, default)`, read only for `llm.registry_cache_ttl_days`.

## Data Contracts
- **Model metadata** (`Dict[str, Any]`): The `get_metadata` return value. `context_window` is the catalog `context_length` passed through verbatim, defaulting to `0`; `pricing` always carries `input_cost_per_token` and `output_cost_per_token` as floats and optionally `cache_read_input_token_cost` and `cache_creation_input_token_cost`.
- **Registry cache payload**: JSON at `.teddy/.model_registry_cache.json` (`CACHE_PATH`) shaped `{"version": 1, "fetched_at_epoch": <int>, "models": [...]}`, where `models` is the catalog list verbatim.
- **Downstream registry entry**: [`LiteLLMAdapter`](./litellm_adapter.md) maps the returned metadata to `{"max_input_tokens": context_window, **pricing}` and writes it into `litellm.model_cost` for every candidate model ID.
- **Exceptions**: None raised. Every failure degrades to a `None` result or to the default TTL.

## Operations

### `__init__(cache_path: Optional[Path] = None, config_service: Optional[IConfigService] = None) -> None`
- **Postconditions:** Both dependencies are stored verbatim on the public `cache_path` and `config_service` attributes, with no implicit default, so the composition root supplies the real values.
- **Postconditions:** `_cached_models` starts as `None`, meaning the catalog has not been loaded.

### `get_metadata(model_id: str) -> Optional[Dict[str, Any]]`
- **Preconditions:** `model_id` names a model and may carry an `openrouter/` prefix or a trailing colon routing suffix.
- **Postconditions:** Returns the metadata of the matching catalog entry, or `None` when the catalog is empty, no ID matches, or a pricing value cannot be converted to `float`.
- **Exceptions:** None raised.

## Model ID resolution
Two decorations are removed before the lookup: the `openrouter/` provider prefix and a trailing colon routing suffix (`:nitro`, `:floor`, or any other shortcut OpenRouter appends). A miss on the cleaned ID triggers one retry with a trailing eight-to-twelve digit date suffix removed, so a pinned snapshot such as `deepseek/deepseek-v4-flash-20260423` resolves to its catalog base ID.

## Catalog cache lifecycle
Catalog resolution walks three sources in order: the in-memory list, then the persistent cache when the entry is within TTL, then a network fetch whose result is persisted. `_resolve_ttl_seconds` reads `llm.registry_cache_ttl_days` through `IConfigService` and falls back to `DEFAULT_TTL_DAYS` when the setting is unset or not an integer. Persistence writes a sibling `.tmp` file and installs it with `os.replace`, so a concurrent reader never observes a partial write.

## Failure handling
An unreadable cache — missing, unparseable, or missing a required key — is debug-logged with its traceback and treated as a cache miss followed by a refetch. A network or payload failure during the fetch collapses to an empty catalog without a log line, so the adapter above observes the failure only as `None`. Persistence failures log a warning and leave the previous cache untouched.
