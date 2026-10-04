from typing import Any, TypeVar
from unittest.mock import MagicMock, _Call  # noqa: TID251

T = TypeVar("T")

# Type alias to satisfy Mypy when accessing return_value/side_effect on mocked ports
Mocked = Any  # fallback for complex proxying, but we'll try to cast specifically


def to_posix_path(value: str) -> str:
    """Normalize path separators to the harness' internal POSIX convention.

    This is the single source of the harness' cross-platform path
    normalization. Windows backslashes are rewritten to forward slashes so a
    path compared on POSIX and Windows yields the same string. It is consumed
    by ``POSIXPathMock``'s mock-call argument normalizer (``_normalize_args``),
    the ``find_call_by_path`` assertion helper, and every path-matching
    ``side_effect`` (e.g. a mocked ``which``) that must compare an incoming,
    already-normalized argument against a resolved baseline.
    """
    return value.replace("\\", "/")


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
                new_args[0] = to_posix_path(val)
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

    def find_call_by_path(self, method_name: str, path: str) -> Any:
        """
        Systemically finds a call to the specified method where the first
        argument matches the path. Handles cross-platform slash normalization.
        """
        norm_target = to_posix_path(path)
        method = getattr(self, method_name)
        for call in method.call_args_list:
            if call.args and isinstance(call.args[0], str):
                norm_actual = to_posix_path(call.args[0])
                if norm_actual == norm_target:
                    return call

        # Provide a helpful error if not found
        available = [
            c.args[0]
            for c in method.call_args_list
            if c.args and isinstance(c.args[0], str)
        ]
        raise AssertionError(
            f"No {method_name} call found for path: {norm_target}\n"
            f"Available paths: {available}"
        )


def register_mock(container: Any, port_type: Any) -> Any:
    """
    Creates, registers, and returns a POSIXPathMock for a specific port.
    This is the preferred way to mock dependencies in tests.
    """
    mock = POSIXPathMock(spec=port_type)
    container.register(port_type, instance=mock)
    return mock
