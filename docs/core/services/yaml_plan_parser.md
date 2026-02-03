# Component: YamlPlanParser

**Status:** Implemented

## 1. Responsibilities
- Parses a raw YAML string into a `Plan` domain object.
- Validates the YAML structure (must be a list of actions or a dict with `actions` key).
- Normalizes action keys and parameters to match the internal `ActionData` structure.
- Handles legacy git command formatting quirks (unquoted colons).

## 2. Collaborators
- **Implements:** `IPlanParser` (Port)
- **Uses:** `ruamel.yaml` or `PyYAML` (Library)
- **Creates:** `Plan`, `ActionData` (Domain Models)

## 3. Public Interface
```python
class YamlPlanParser(IPlanParser):
    def parse(self, plan_content: str) -> Plan:
        """
        Parses a YAML string.
        Raises InvalidPlanError on malformed YAML or missing required fields.
        """
```
