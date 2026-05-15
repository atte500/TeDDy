from typing import Any, TypeVar
from unittest.mock import MagicMock, _Call  # noqa: TID251

T = TypeVar("T")

# Type alias to satisfy Mypy when accessing return_value/side_effect on mocked ports
Mocked = Any  # fallback for complex proxying, but we'll try to cast specifically


class POSIXPathMock(MagicMock):
    """
    A specialized mock that normalizes the first string argument of any call
    AND any assertion to POSIX format. This ensures that unit tests are
    cross-platform and consistent with the core's Internal POSIX convention.
    """

    def _get_child_mock(self, /, **kw):
        # Revert to standard POSIXPathMock for children
        return POSIXPathMock(**kw)

    def _normalize_args(self, args, kwargs):
        new_args = list(args)
        if new_args and isinstance(new_args[0], str):
            val = new_args[0]
            # Systemic normalization: only replace \ with / for path-like strings.
            # Large strings (file contents) or multi-line strings are skipped for performance.
            if len(val) < 1024 and "\n" not in val:
                new_args[0] = val.replace("\\", "/")
        return tuple(new_args), kwargs

    def __call__(self, /, *args, **kwargs):
        new_args, new_kwargs = self._normalize_args(args, kwargs)
        return super().__call__(*new_args, **new_kwargs)

    def assert_called_with(self, /, *args, **kwargs):
        new_args, new_kwargs = self._normalize_args(args, kwargs)
        return super().assert_called_with(*new_args, **new_kwargs)

    def assert_any_call(self, /, *args, **kwargs):
        new_args, new_kwargs = self._normalize_args(args, kwargs)
        return super().assert_any_call(*new_args, **new_kwargs)

    def assert_called_once_with(self, /, *args, **kwargs):
        new_args, new_kwargs = self._normalize_args(args, kwargs)
        return super().assert_called_once_with(*new_args, **new_kwargs)

    def assert_has_calls(self, calls, any_order=False):
        normalized_calls = []
        for call in calls:
            # call is a _Call object (tuple-like: (args, kwargs))
            args, kwargs = call[1], call[2]
            new_args, new_kwargs = self._normalize_args(args, kwargs)
            normalized_calls.append(_Call((new_args, new_kwargs), two=True))
        return super().assert_has_calls(normalized_calls, any_order=any_order)


def register_mock(container: Any, port_type: Any) -> Any:
    """
    Creates, registers, and returns a POSIXPathMock for a specific port.
    This is the preferred way to mock dependencies in tests.
    """
    mock = POSIXPathMock(spec=port_type)
    container.register(port_type, instance=mock)
    return mock
