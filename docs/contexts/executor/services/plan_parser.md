# Application Service: PlanParser

The `PlanParser` is a single-responsibility service within the hexagonal core. Its sole purpose is to parse a plan string, validate its structure, and convert it into a structured `Plan` domain object.

## 1. Design Principles

-   **Single Responsibility:** This service only deals with parsing. It does not execute actions or interact with the user.
-   **Error Handling:** It is responsible for gracefully handling parsing errors (e.g., invalid YAML, missing required fields) by raising a specific `InvalidPlanError` exception.
-   **Decoupling:** The service is fully decoupled from the file system and other I/O. It operates purely on in-memory string data, making it highly portable and easy to test.

## 2. Dependencies

-   **Outbound Ports:** None.

## 3. Public Interface

The `PlanParser` service exposes a single method.

### `parse`
Parses a plan string into a `Plan` domain object.

**Status:** Implemented

```python
from teddy_executor.core.domain.models import Plan

class PlanParser:
    def parse(self, plan_content: str) -> Plan:
        """
        Reads and parses the specified YAML plan string.

        Args:
            plan_content: A string containing the YAML plan.

        Returns:
            A Plan domain object representing the validated plan.

        Raises:
            InvalidPlanError: If the string content is not valid YAML or
                              if it does not conform to the expected plan structure.
        """
        pass
```

## 4. Domain Models (Input/Output)

### `Plan` (Output)
The `PlanParser` produces a `Plan` domain object, which is a strongly-typed dataclass representation of the plan. This model is defined in the [Domain Model documentation](../domain_model.md).
