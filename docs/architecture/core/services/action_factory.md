# Application Component: `ActionFactory`

**Status:** Implemented

## 1. Purpose
The `ActionFactory` is the central component responsible for translating action data from a plan into executable `IAction` handlers. Instead of maintaining a registry of domain objects, the factory leverages a Dependency Injection (DI) container to resolve the appropriate Outbound Port adapters and dynamically binds their specific methods to a standardized `execute(**kwargs)` interface.

## 2. Public Interface

### `create_action(action_type: str, params: dict) -> IAction`
*   **Description:** Resolves and prepares an action handler for the specified action type.
*   **Parameters:**
    *   `action_type` (str): The verb representing the action (e.g., `CREATE`, `EXECUTE`).
    *   `params` (dict): The parameters extracted from the plan for this action.
*   **Returns:** An object implementing the `IAction` protocol (exposing a single `execute` method).

## 3. Implementation Strategy

### 3.1. Dependency Injection & Method Binding
The factory uses the `punq` container to resolve concrete adapters for Outbound Ports. For adapters that support multiple operations (e.g., `IFileSystemManager` handles both `CREATE` and `EDIT`), the factory performs **Method Binding**:
1.  It resolves the adapter instance from the container.
2.  It identifies the specific adapter method required for the action (e.g., `create_file` for a `CREATE` action).
3.  It wraps this method in a closure that implements the `IAction` protocol's `execute(**kwargs)` method.
4.  This closure handles parameter normalization (e.g., mapping `resource` or `path` to the adapter's expected argument names).

### 3.2. Specialized Routing for `READ`
The factory handles the polymorphic nature of the `READ` action. It inspects the target resource:
- **Remote Resource (URL):** It resolves and binds the `IWebScraper` adapter.
- **Local Resource (Path):** It resolves and binds the `IFileSystemManager.read_file` method.

### 3.3. Standalone Actions
Actions that do not require external I/O or adapter delegation (e.g., `INVOKE`, `PRUNE`, `RETURN`) are handled by simple internal classes within the factory that implement the `IAction` protocol directly.

## 4. Key Mappings

The factory maintains a mapping between the Markdown verbs used in plans and the internal Port protocols:

| Action Verb      | Internal Key     | Port Protocol           | Adapter Method |
| ---------------- | ---------------- | ----------------------- | -------------- |
| `CREATE`         | `create_file`    | `IFileSystemManager`    | `create_file`  |
| `EDIT`           | `edit`           | `IFileSystemManager`    | `edit_file`    |
| `READ` (local)   | `read_file`      | `IFileSystemManager`    | `read_file`    |
| `READ` (remote)  | `read_file`      | `IWebScraper`           | `get_content`  |
| `EXECUTE`        | `execute`        | `IShellExecutor`        | `execute`      |
| `CHAT_WITH_USER` | `chat_with_user` | `IUserInteractor`       | `ask_question` |
| `RESEARCH`       | `research`       | `IWebSearcher`          | `search`       |
| `INVOKE`         | `invoke`         | Internal `InvokeAction` | `execute`      |
| `PRUNE`          | `prune`          | Internal `PruneAction`  | `execute`      |
| `RETURN`         | `return`         | Internal `ReturnAction` | `execute`      |
