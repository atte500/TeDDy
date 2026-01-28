# Application Component: Action Factory

**Status:** Implemented
**Related Slice:** [Slice 03: Refactor Action Dispatching](../../slices/03-refactor-action-dispatching.md)

## 1. Purpose
The `ActionFactory` is a core component responsible for taking raw action data (typically deserialized from a YAML plan) and converting it into a validated, concrete `Action` domain object (e.g., `ExecuteAction`, `CreateFileAction`, `ReadAction`). It encapsulates the creation and validation logic, decoupling the `PlanService` from the specific details of each action type.

## 2. Public Interface

### `create_action(action_data: dict) -> Action`
**Status:** Implemented

*   **Description:** The primary factory method. It inspects the `action` key in the input dictionary to determine which type of action object to create, validates the associated `params`, and returns an initialized instance of the appropriate `Action` subclass.
*   **Parameters:**
    *   `action_data` (dict): A dictionary representing a single action from the plan (e.g., `{'action': 'execute', 'params': {'command': 'ls'}}`).
*   **Returns:** An instance of a concrete class that inherits from `Action`.
*   **Raises:**
    *   `ValueError`: If the `action` key is missing, invalid, or does not map to a known action type.
    *   `TypeError`: If the `params` dictionary is missing required keys for the specified action.

## 3. Implementation Strategy
1.  The factory will maintain an internal registry (e.g., a dictionary) that maps action type strings to their corresponding `Action` handler classes.

2.  **Dependency Injection:** The factory will be injected with all necessary outbound ports (e.g., `IFileSystemManager`, `IWebScraper`, etc.) at creation time. It will then inject the required dependencies into the constructor of each action handler it creates.

3.  **URL Handling in `ReadAction`:**
    *   The handler for the `read` action will be injected with both `IFileSystemManager` and `IWebScraper`.
    *   Its `execute` method will inspect the `path` parameter. If the path starts with `http://` or `https://`, it will delegate the call to the web scraper. Otherwise, it will delegate to the file system manager.

4.  **Backwards Compatibility:** For the `execute` action, it checks if `params` is a simple string. If so, it converts it to a dictionary (`{"command": "..."}`) to support the legacy plan format.

5.  The factory is also responsible for minor data transformations. For example, it converts a multi-line string of queries for the `research` action into the list of strings required by the `ResearchAction` domain object.

**Conceptual Registry:**
```python
# Conceptual registry
self.action_registry = {
    "execute": ExecuteAction,
    "create_file": CreateFileAction,
    "read": ReadAction, # Added in Slice 04
    "edit": EditAction, # Added in Slice 06
    "chat_with_user": ChatWithUserAction, # Added in Slice 10
    "research": ResearchAction, # Added in Slice 11
}
```

    ```python
    # Conceptual registry
    self.action_registry = {
        "execute": ExecuteAction,
        "create_file": CreateFileAction,
        "read": ReadAction, # Added in Slice 04
        "edit": EditAction, # Added in Slice 06
        "chat_with_user": ChatWithUserAction, # Added in Slice 10
        "research": ResearchAction, # Added in Slice 11
    }
    ```
2.  The `create_action` method checks if the `action` type exists in the registry. If not, it raises a `ValueError`.
3.  **Backwards Compatibility:** For the `execute` action, it checks if `params` is a simple string. If so, it converts it to a dictionary (`{"command": "..."}`) to support the legacy plan format.
4.  It retrieves the corresponding class from the registry and attempts to instantiate it, passing the `params` dictionary as keyword arguments.
5.  The `dataclass` constructor of the concrete action class handles the validation, raising `ValueError` or `TypeError` if parameters are invalid. These exceptions are propagated up to the `PlanService`.
6.  The factory is also responsible for minor data transformations. For example, it converts a multi-line string of queries for the `research` action into the list of strings required by the `ResearchAction` domain object.
