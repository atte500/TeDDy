from unittest.mock import MagicMock
from teddy_executor.core.utils.serialization import scrub_dict_for_serialization


def test_scrub_dict_keeps_primitives(container):
    data = {"a": 1, "b": "text", "c": 1.5, "d": True}
    result = scrub_dict_for_serialization(data)
    assert result == data


def test_scrub_dict_converts_complex_to_str(container):
    class Complex:
        def __str__(self):
            return "complex_obj"

    data = {"obj": Complex()}
    result = scrub_dict_for_serialization(data)
    assert result == {"obj": "complex_obj"}


def test_scrub_dict_converts_mock_to_str(container):
    mock_obj = MagicMock()
    data = {"mock": mock_obj}
    result = scrub_dict_for_serialization(data)
    assert result["mock"].startswith("<MagicMock")
