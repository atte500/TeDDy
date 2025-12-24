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
1.  The factory will maintain an internal registry (e.g., a dictionary) that maps action type strings to their corresponding `Action` subclasses.

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
2.  The `create_action` method will first check if the provided `action` type exists in the registry. If not, it raises `UnknownActionError`.
3.  It will then retrieve the corresponding class from the registry.
4.  It will attempt to instantiate the class, passing the `params` dictionary as keyword arguments.
5.  The `dataclass` constructor of the concrete action class will handle the initial type validation. Any `TypeError` during instantiation should be caught and re-raised as a more specific `InvalidActionParametersError`, providing a clear error message to the user.
6.  The factory is also responsible for minor data transformations required by the YAML format. For example, it converts a multi-line string of queries for the `research` action into the list of strings required by the `ResearchAction` domain object.
