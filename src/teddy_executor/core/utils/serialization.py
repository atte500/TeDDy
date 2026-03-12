from typing import Any, Dict


def scrub_dict_for_serialization(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensures all values in a dictionary are primitive types (str, int, float, bool)
    to prevent serialization libraries (like PyYAML) from hanging or crashing
    when encountering complex objects or MagicMocks during testing.
    """
    serializable = {}
    for k, v in data.items():
        # Specifically check for MagicMock objects via the _mock_return_value attribute
        # which is common across unittest.mock.
        if isinstance(v, (str, int, float, bool)) and not hasattr(
            v, "_mock_return_value"
        ):
            serializable[k] = v
        else:
            serializable[k] = str(v)
    return serializable
