# Port: IPlanParser

## 1. Purpose

The `IPlanParser` port defines the abstract interface for any service capable of parsing a plan from a raw string into a structured `Plan` domain object. This abstraction decouples the core `ExecutionOrchestrator` from the specific format of the plan (e.g., YAML, Markdown), allowing for multiple parser implementations to be used interchangeably.

## 2. Contract

### Method: `parse`

This is the sole method required by the port. It takes a string containing the entire plan content and is responsible for validating and transforming it into a `Plan` object.

-   **Preconditions:**
    -   `plan_content` must be a non-empty string.
-   **Postconditions:**
    -   Returns a valid `Plan` domain object.
    -   If the `plan_content` is malformed or invalid according to the parser's specific format rules, an `InvalidPlanError` must be raised.

**Signature:**

```python
from abc import ABC, abstractmethod
from typing import Any, List, Optional
from teddy_executor.core.domain.models.plan import Plan

class InvalidPlanError(Exception):
    """Raised when the plan is malformed."""

    def __init__(
        self,
        message: str,
        offending_node: Optional[Any] = None,
        offending_nodes: Optional[List[Any]] = None,
        validation_errors: Optional[List[Any]] = None,
    ):
        super().__init__(message)
        self.offending_nodes = offending_nodes or []
        self.validation_errors = validation_errors or []
        if offending_node:
            self.offending_nodes.append(offending_node)

class IPlanParser(ABC):
    """
    Abstract interface for a service that parses a plan from a raw string.
    """

    @abstractmethod
    def parse(self, plan_content: str) -> Plan:
        """
        Parses a plan string into a Plan domain object.

        Args:
            plan_content: The raw string content of the plan.

        Returns:
            A Plan domain object.

        Raises:
            InvalidPlanError: If the plan content is invalid.
        """
        raise NotImplementedError
```
