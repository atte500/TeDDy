"""Unit coverage: the local-endpoint host classifier.

The key gate skips the interactive prompt when ``llm.api_base`` names the
developer machine. This module pins that decision across loopback literals,
private and link-local ranges, container aliases, ``.local`` names, a
scheme-less value, a malformed value, and a public host. Host classification
performs no DNS lookup, so an unresolvable name never blocks startup.
"""

from typing import Any, Optional

import pytest

from teddy_executor.adapters.inbound.session_cli_handlers import (
    _api_base_host,
    _is_local_endpoint,
)
from teddy_executor.core.ports.outbound.config_service import IConfigService


class _ApiBaseConfigService(IConfigService):
    """In-memory ``IConfigService`` double exposing only ``llm.api_base``.

    The classifier reads a single setting, so this focused fake keeps the host
    matrix free of mock poisoning without duplicating the wider key-gate fake.
    """

    def __init__(self, api_base: Optional[str]) -> None:
        self._api_base = api_base

    def get_config_path(self) -> str:
        return ".teddy/config.yaml"

    def get_setting(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        if key == "llm.api_base":
            return self._api_base
        return default

    def set_setting(self, key: str, value: Any) -> None:
        pass

    def set_env_variable(self, name: str, value: str) -> None:
        pass


LOCAL_API_BASES = [
    "http://localhost:8080/v1",
    "http://127.0.0.1:8080/v1",
    "http://[::1]:8080/v1",
    "http://10.0.0.5:8080/v1",
    "http://172.16.4.1:8080/v1",
    "http://192.168.1.10:8080/v1",
    "http://169.254.10.20:8080/v1",
    "http://[fd00::1]:8080/v1",
    "http://[fe80::1]:8080/v1",
    "http://[::ffff:127.0.0.1]:8080/v1",
    "http://host.docker.internal:8080/v1",
    "http://mybox.local:8080/v1",
    "localhost:11434",
]

REMOTE_API_BASES = [
    "https://api.openai.com/v1",
    "https://8.8.8.8/v1",
    "http://example.com:8080",
]


@pytest.mark.parametrize("api_base", LOCAL_API_BASES)
def test_is_local_endpoint_true_for_local_hosts(api_base):
    """Each local host form counts as local, because only this machine answers it."""
    config = _ApiBaseConfigService(api_base)

    assert _is_local_endpoint(config) is True


@pytest.mark.parametrize("api_base", REMOTE_API_BASES)
def test_is_local_endpoint_false_for_public_hosts(api_base):
    """A public host stays remote, because a real credential can be required."""
    config = _ApiBaseConfigService(api_base)

    assert _is_local_endpoint(config) is False


@pytest.mark.parametrize("api_base", [None, "", "   "])
def test_is_local_endpoint_false_when_api_base_absent(api_base):
    """An absent or blank endpoint is remote, so the prompt stays eligible."""
    config = _ApiBaseConfigService(api_base)

    assert _is_local_endpoint(config) is False


@pytest.mark.parametrize("api_base", ["http://", "http://:8080", "::::"])
def test_is_local_endpoint_false_for_malformed_host(api_base):
    """An unparseable host stays remote, because a silent placeholder hides a requirement."""
    config = _ApiBaseConfigService(api_base)

    assert _is_local_endpoint(config) is False


@pytest.mark.parametrize(
    "api_base, expected_host",
    [
        ("http://localhost:8080/v1", "localhost"),
        ("localhost:11434", "localhost"),
        ("http://[::1]:8080/v1", "::1"),
    ],
)
def test_api_base_host_extracts_the_host(api_base, expected_host):
    """The host extraction tolerates a missing scheme and bracketed IPv6 literals."""
    assert _api_base_host(api_base) == expected_host
