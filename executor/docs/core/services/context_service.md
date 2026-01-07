# Application Service: `ContextService`

**Status:** Implemented
**Introduced in:** [Slice 13: Implement `context` Command](../../slices/13-context-command.md)

## 1. Purpose

The `ContextService` is the application service responsible for orchestrating the gathering of project context. It implements the `IGetContextUseCase` inbound port and acts as the central coordinator, using various outbound ports to collect information and assemble it into a `ContextResult` domain object.

## 2. Used Outbound Ports

*   [`IFileSystemManager`](../ports/outbound/file_system_manager.md): To read `.gitignore` and other context files, and to ensure the `.teddy` configuration directory exists.
*   [`IRepoTreeGenerator`](../ports/outbound/repo_tree_generator.md): To generate the repository's file tree.
*   [`IEnvironmentInspector`](../ports/outbound/environment_inspector.md): To gather information about the operating system and environment.

## 3. Implemented Inbound Ports

*   [`IGetContextUseCase`](../ports/inbound/get_context_use_case.md)

## 4. Orchestration Logic

When the `get_context` method is called, the `ContextService` performs the following steps:
1.  It ensures the local context directory (`.teddy/`) and its required files exist, creating them if necessary.
2.  It invokes the `IRepoTreeGenerator` to get the file tree.
3.  It invokes the `IEnvironmentInspector` to get system information.
4.  It reads the main `.gitignore` file.
5.  It reads the lists of files from the context configuration files.
6.  It iterates through the file lists, reading each one and noting any that are not found.
7.  It aggregates all collected data into a `ContextResult` object and returns it.
