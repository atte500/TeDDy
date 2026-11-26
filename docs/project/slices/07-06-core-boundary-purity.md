# Slice: Core Boundary Purity
- **Status:** Planned
- **Milestone:** [Milestone 7: Runtime Reliability & Boundary Purity](/docs/project/milestones/07-runtime-reliability.md)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [ConfigSchema](/docs/architecture/core/domain/config_schema.md), [YamlConfigAdapter](/docs/architecture/adapters/outbound/yaml_config_adapter.md), [InitService](/docs/architecture/core/services/init_service.md), [PromptManager](/docs/architecture/core/services/prompt_manager.md), [SessionOrchestrator](/docs/architecture/core/services/session_orchestrator.md), [ISessionManager](/docs/architecture/core/ports/outbound/session_manager.md)
- **Scope Slug:** `core-boundary-purity`

## Goal
Take every third-party library import out of `core` by naming the concern it serves as a port, so the Hexagonal boundary the architecture document already asserts becomes the boundary the code actually holds and the existing structural check can enforce.

## Context
- Six sites, measured: `import yaml` in `core/services/init_service.py:8`, `core/services/prompt_manager.py:6`, `core/services/session_lifecycle_manager.py:5`, and `core/services/session_repository.py:3`; `import typer` in `core/services/session_orchestrator.py:30` and `core/utils/terminal.py:13`.
- `.githooks/check_architecture_boundaries.py` already fails on these six and currently runs non-blocking in CI, so the law and the code have disagreed for as long as the job has been advisory. The milestone's sequencing constraint is therefore not a preference: once [05-04](./05-04-ci-gate-split.md) flips that job to blocking, these imports break the build. This slice must land before or with that flip.
- The four `yaml` sites are one concern, not four: reading or writing a structured document. Two write it (`session_repository.py` dumping metadata, `session_lifecycle_manager.py` composing a turn record) and two read it (`init_service.py` a manifest, `prompt_manager.py` prompt front-matter). Naming that concern once as a codec port and implementing it in one YAML adapter removes all four and gives the boundary an abstraction worth having rather than four call-site workarounds.
- The two `typer` sites are different concerns and must not be conflated. `session_orchestrator.py` uses it for termination semantics — an exit signal that core reasons about — which belongs behind a domain exception the CLI adapter translates. `core/utils/terminal.py` uses it for console presentation, which belongs in an adapter entirely, because a core util that styles output is a rendering concern wearing a util's name.
- Ordering against [06-05](./06-05-domain-exception-hierarchy.md): the termination path gains a domain exception that slice's hierarchy must already contain, so the two either land in sequence or share one commit contract. Ordering against [07-01](./07-01-durable-session-metadata.md): the repository's YAML write moves to the codec, and 07-01 changes how that write reaches disk, so the two touch the same function and need a rebase.
- Enforcement is the existing hook, so this slice's `Env` deliverable is deliberately narrow: confirm the hook's scan root includes `core/utils/`, because a services-only scan would miss `terminal.py` and leave the law half-enforced after the work is done.

## Scenarios

> As a maintainer, I want the boundary law and the code to agree.

```gherkin
Given the completed slice
When the architecture-boundary hook runs
Then it exits zero over core
And no core module imports a third-party parsing or CLI library
```

> As a maintainer, I want the structured-document concern named once.

```gherkin
Given a core service that must read or write a structured document
When it needs the serialized form
Then it calls the codec port
And it does not import a parser
```

> As a user, I want a termination signal to still end the session cleanly.

```gherkin
Given a core service that decides the session must stop
When it signals termination
Then it raises a domain exception from the hierarchy
And the CLI adapter translates it into the exit behaviour the user sees
```

## Edge Cases
- **Codec round-trip fidelity**: If the codec adapter replaces direct `yaml.dump`, then the emitted document must stay byte-compatible with what the repository writes today, because the metadata file is an on-disk contract other tooling reads.
- **Comments in user config**: If the codec is used for the user's `config.yaml`, then comment preservation is a separate concern already excluded by Milestone 7's constraints; the codec is for metadata and manifests, and the config adapter keeps its own path.
- **Front-matter edge**: If a prompt file has no front-matter, then the codec reports an absent document rather than an empty mapping, because "no metadata" and "empty metadata" lead to different defaults.
- **Domain termination type**: If the orchestrator's termination becomes a domain exception, then it must not be a `TeddyError` if the CLI already catches that root for user-facing reporting, or the stop would print as a failure; the exception carries a distinct type that the adapter translates without an error line.
- **Styling removal**: If `core/utils/terminal.py` moves presentation into an adapter, then any core caller that used it for width or capability queries keeps an injected capability instead, because capability is composition-root knowledge, not core knowledge.
- **Import of the removed util**: If a test imports the util directly, then it migrates to the injected capability or to the adapter, because a test that keeps a removed boundary alive defeats the slice.
- **Hook scan root**: If the hook only scans `core/services/`, then `core/utils/terminal.py` passes and the enforcement is incomplete; the scan root is verified and extended if needed.
- **Lazy imports stay lazy**: If the codec adapter imports a parser, then that import is at module scope in the adapter, because adapters are allowed heavy libraries and the laziness law exists for startup cost — the codec must be constructed at the composition root, not per call.

## Key Unknowns
- [ ] [Technical] Whether a codec port is justified for all four `yaml` sites or whether one of them is better served by an existing port. Design Sensitivity: if all four are genuinely structured-document reads and writes → one codec port and one adapter close them together; if `prompt_manager.py`'s front-matter reading is better expressed as part of prompt resolution → that site moves behind the prompt source port instead, and the codec covers three — either way the count of core imports goes to zero, which is the invariant that matters.

## Impact
1. `[NEW]` A structured-document codec port in `core/ports/outbound/` — decode to a mapping, encode from a mapping, and an explicit absent-document result.
2. `[NEW]` A YAML codec adapter implementing it, constructed at the composition root.
3. `[MIGRATE]` `init_service.py`, `prompt_manager.py`, `session_lifecycle_manager.py`, `session_repository.py` — consume the codec instead of importing a parser.
4. `[NEW]` A domain termination type in the exception hierarchy, raised by `session_orchestrator.py` and translated by the CLI adapter.
5. `[MIGRATE]` `core/utils/terminal.py` — presentation moves to an adapter; capability queries become an injected capability.
6. `[MIGRATE]` `.githooks/check_architecture_boundaries.py` — scan root verified to include `core/utils/`, with a unit case proving it bites there.
7. `[MIGRATE]` The six component pages above plus `docs/architecture/ARCHITECTURE.md` — record the codec port, the termination type, and that the boundary hook is now the enforcing gate rather than an advisory one.

## Deliverables
- [ ] **Env** — Verify and, if needed, extend the architecture-boundary hook's scan root to cover `core/utils/`, with a regression case proving it fails there.
- [ ] **Interface** — Land the codec port and the domain termination type with their contracts documented.
- [ ] **Harness** — Add a boundary test asserting no third-party parsing or CLI import exists under `core`, so the suite catches a regression even without the hook.
- [ ] **Adapter** — Implement the YAML codec adapter and move terminal presentation out of core.
- [ ] **Core** — Convert the four parser sites and both `typer` sites, keeping the metadata document byte-identical.
- [ ] **Cleanup** — Update the six component pages and `ARCHITECTURE.md`, and remove the util if nothing legitimate remains in it.

## Implementation Notes

## Verification
1. **Boundary holds:**
   Run `uv run python .githooks/check_architecture_boundaries.py`.
   Verify it exits zero over `core` and still fails when a scratch module re-adds an import.
2. **Document fidelity:**
   Compare a metadata file written before and after the change for the same session.
   Verify the bytes are identical.
3. **Termination still clean:**
   Drive a session to a core-decided stop.
   Verify the session ends with the expected exit behaviour and no error line.
