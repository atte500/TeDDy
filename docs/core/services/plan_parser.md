# Service: YamlPlanParser

- **Implements Port:** [IPlanParser](../ports/inbound/plan_parser.md)

## 1. Purpose

The `YamlPlanParser` service is the concrete implementation of `IPlanParser` responsible for parsing a plan from a YAML string into a structured `Plan` domain object. It acts as the primary validation and translation layer between the raw YAML input from the AI and the core application's domain model.

## 2. Design Principles

-   **Single Responsibility:** This service only deals with parsing YAML. It does not execute actions or interact with the user.
-   **Error Handling:** It is responsible for gracefully handling parsing errors (e.g., invalid YAML, missing required fields) by raising a specific `InvalidPlanError` exception.
-   **Decoupling:** The service is fully decoupled from the file system and other I/O. It operates purely on in-memory string data, making it highly portable and easy to test.

## 3. Dependencies

-   **Outbound Ports:** None.

## 4. Public Interface

The `YamlPlanParser` service implements the `parse` method from the `IPlanParser` port.

### `parse`
Parses a YAML plan string into a `Plan` domain object.

**Status:** Implemented

```python
from teddy_executor.core.domain.models import Plan
from teddy_executor.core.ports.inbound import IPlanParser

class YamlPlanParser(IPlanParser):
    def parse(self, plan_content: str) -> Plan:
        """
        Reads and parses the specified YAML plan string.

        Before parsing, this method pre-processes the raw string to find any
        key-value line where the value is a single line, contains a colon (:),
        and is not already quoted. It wraps the value in double quotes to
        prevent YAML scanning errors that occur in unquoted string values.

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

## 5. Domain Models (Input/Output)

### `Plan` (Output)
The `YamlPlanParser` produces a `Plan` domain object. This model is defined in the [Domain Model documentation](../domain_model.md).
