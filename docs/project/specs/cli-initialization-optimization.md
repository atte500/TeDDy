# Spec: CLI Initialization Optimization

- **Status:** Active

## Overview / Problem Statement
The `teddy` CLI currently pays a "full system tax" on every command execution. Even simple, non-interactive commands like `teddy execute -y` incur ~150-200ms of overhead due to eager DI registration, disk I/O for configuration during wiring, and heavy library imports (Textual, LiteLLM) that are not required for the specific execution path.

The goal is to move to a **"Pay for what you use"** model where initialization cost is proportional to the command's requirements.

## Guiding Principles / Core Logic
1. **Deferred I/O:** No disk access should occur during the DI registration phase (the "Wiring" phase).
2. **Path-Based Registration:** Partition the container wiring so that heavy dependencies (TUI, LLM) are only registered/imported when the command path requires them.
3. **Lazy Constructor Resolution:** Adapters should receive the `IConfigService` as a dependency and resolve specific settings lazily at runtime, rather than receiving "magic values" resolved by the container.
4. **Zero-Cost Headless Execution:** Headless commands (`execute -y`, `context`) must never import UI frameworks (Textual).

## Technical Specification

### 1. Lazy Configuration Injection
- **Current:** `register_infrastructure` calls `config_service.get_setting()` to pass values to adapter constructors.
- **Target:** Refactor adapters (e.g., `ShellAdapter`, `LocalFileSystemAdapter`) to take `IConfigService` in their `__init__`. Resolution of settings (like `max_output_lines`) should happen inside the adapter logic.

### 2. Registration Partitioning
Refactor `src/teddy_executor/container.py` and `registries/` to support tiered registration:
- **Core Registration:** Basic I/O, Config, and Execution logic.
- **UI Registration:** Textual-based reviewer components.
- **AI Registration:** LiteLLM and Planning services.

### 3. Import Guarding
- Ensure all heavy third-party imports (e.g., `textual`, `litellm`, `trafilatura`) are kept strictly within the factory lambdas or method-level scopes to prevent them from leaking into the global `execute` path.

### 4. Bootstrap Optimization
- Move the `ensure_initialized()` check from the global Typer `@app.callback()` to the specific Use Case implementations or a lazy property to avoid mandatory resolution of `IInitUseCase` on every turn.

## Guidelines
1. **Performance Target:** Total initialization time (from `main` to `use_case.execute`) should be < 80ms on standard hardware (excluding Python/Poetry startup overhead).
2. **Boundary Preservation:** Do NOT introduce DI framework dependencies into the core services.
3. **Verification:** Use the `spikes/profile_startup.py` script to verify improvements.
