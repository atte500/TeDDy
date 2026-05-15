from typing import Any, Dict


import dataclasses
from datetime import datetime
from enum import Enum


def scrub_dict_for_serialization(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively ensures that MagicMocks and complex objects are neutralized
    for serialization while preserving the structure required by templates.
    """

    def scrub(v: Any) -> Any:
        """Neutralizes MagicMocks for serialization (PLR0911)."""
        # 1. Neutralize Mocks, Primitives, Enums
        if (
            hasattr(v, "_mock_return_value")
            or hasattr(v, "assert_called")
            or "Mock" in str(type(v))
        ):
            return str(v)
        if isinstance(v, (str, int, float, bool, type(None), datetime, Enum)):
            return v

        # 2. Handle Dataclasses
        if dataclasses.is_dataclass(v):
            return {f.name: scrub(getattr(v, f.name)) for f in dataclasses.fields(v)}

        # 3. Recursively handle collections
        if isinstance(v, dict):
            return {k: scrub(val) for k, val in v.items()}
        if isinstance(v, (list, tuple, set)):
            return [scrub(item) for item in v]

        return str(v)

    return {k: scrub(v) for k, v in data.items()}
