import inspect
from typing import Any, TypeVar
from unittest.mock import AsyncMock, MagicMock, _Call

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
        # Always return a UnifiedMock for children to preserve async-awareness
        return UnifiedMock(**kw)

    def __setattr__(self, name, value):
        # 1. Propagation logic for sync/async pairing
        # Use __dict__ to avoid triggering Mock's auto-attribute creation
        if name in ("return_value", "side_effect"):
            partner = self.__dict__.get("_synced_partner")
            if partner and not self.__dict__.get("_syncing", False):
                try:
                    # Set the syncing flag on the PARTNER to prevent it from calling us back
                    object.__setattr__(partner, "_syncing", True)
                    setattr(partner, name, value)
                finally:
                    object.__setattr__(partner, "_syncing", False)

        # 2. Apply to self using standard Mock setter
        super().__setattr__(name, value)

    def _normalize_args(self, args, kwargs):
        new_args = list(args)
        if new_args and isinstance(new_args[0], str):
            # Systemic normalization: replace \ with /
            new_args[0] = new_args[0].replace("\\", "/")
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


class UnifiedMock(POSIXPathMock):
    """
    A POSIX-normalizing mock that automatically promotes async methods
    to AsyncMock when a spec is provided.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        spec = kwargs.get("spec")
        if spec:
            self._promote_async_methods(spec)

    def _promote_async_methods(self, spec: Any) -> None:
        """Identifies and replaces async methods with AsyncMock instances."""
        all_methods = set(dir(spec))
        for name in all_methods:
            if name.startswith("_"):
                continue

            attr = getattr(spec, name, None)
            if name.startswith("async_") or inspect.iscoroutinefunction(attr):
                if not isinstance(getattr(self, name), AsyncMock):
                    setattr(self, name, AsyncAsyncPOSIXMock())

                sync_name = name.removeprefix("async_")
                if sync_name in all_methods and sync_name != name:
                    sync_mock = getattr(self, sync_name)
                    async_mock = getattr(self, name)

                    # Link the mocks for return_value/side_effect synchronization
                    # Use object.__setattr__ to ensure these don't become Mocks
                    object.__setattr__(sync_mock, "_synced_partner", async_mock)
                    object.__setattr__(async_mock, "_synced_partner", sync_mock)
                    object.__setattr__(sync_mock, "_syncing", False)
                    object.__setattr__(async_mock, "_syncing", False)


class AsyncAsyncPOSIXMock(POSIXPathMock, AsyncMock):
    """Bridge for async methods that need POSIX normalization."""

    pass


def register_mock(container: Any, port_type: Any) -> Any:
    """
    Creates, registers, and returns a UnifiedMock for a specific port.
    This is the preferred way to mock dependencies in tests.
    """
    mock = UnifiedMock(spec=port_type)
    container.register(port_type, instance=mock)
    return mock
