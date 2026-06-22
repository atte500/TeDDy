"""
Regression test for Bug #07: `teddy update` reports network error despite working network.

The root cause was that `fetch_latest_version` used `urllib.request.urlopen` without an
explicit SSL context, causing CERTIFICATE_VERIFY_FAILED on Python 3.14 macOS framework builds.
Additionally, `perform_upgrade` always used pip install, breaking for uv-installed packages.

This test verifies:
1. fetch_latest_version passes an SSL context to urlopen.
2. _create_ssl_context returns a valid SSLContext object using certifi when available.
3. _is_uv_installed detects uv-installed packages.
4. perform_upgrade uses `uv tool upgrade` when uv is detected.
5. perform_upgrade falls back to pip when uv is not detected.
"""

import ssl
import subprocess
import urllib.request


class TestFetchLatestVersionUsesSSLContext:
    """Verifies that fetch_latest_version passes an SSL context to urlopen."""

    def test_urlopen_called_with_context(self, monkeypatch):
        """fetch_latest_version must pass context= to urlopen."""
        from teddy_executor.core.services.update_checker import (
            fetch_latest_version,
        )

        # Track the context object passed to urlopen
        captured_kwargs = {}

        def mock_urlopen(req, **kwargs):
            captured_kwargs.update(kwargs)

            # Return a context manager that yields a fake response
            class FakeResponse:
                def read(self):
                    return b'{"info": {"version": "1.0.0"} }'

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    pass

            return FakeResponse()

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        result = fetch_latest_version()

        assert result == "1.0.0"
        assert "context" in captured_kwargs, (
            "urlopen must be called with context= argument"
        )
        assert isinstance(captured_kwargs["context"], ssl.SSLContext)


class TestCreateSSLContext:
    """Verifies that _create_ssl_context returns a proper SSL context."""

    def test_returns_ssl_context_object(self):
        """_create_ssl_context should return an SSLContext."""
        from teddy_executor.core.services.update_checker import _create_ssl_context

        context = _create_ssl_context()
        assert isinstance(context, ssl.SSLContext)


class TestIsUvInstalled:
    """Verifies uv detection logic."""

    def test_detects_uv_installation(self, monkeypatch):
        """When `uv tool list` contains teddy-cli, return True."""
        from teddy_executor.core.services.update_checker import _is_uv_installed

        def mock_run(cmd, *args, **kwargs):
            return subprocess.CompletedProcess(
                cmd, 0, stdout="teddy-cli v0.1.4\n- teddy\n", stderr=""
            )

        monkeypatch.setattr(subprocess, "run", mock_run)

        assert _is_uv_installed() is True

    def test_returns_false_when_not_uv(self, monkeypatch):
        """When `uv tool list` does not contain teddy-cli, return False."""
        from teddy_executor.core.services.update_checker import _is_uv_installed

        def mock_run(cmd, *args, **kwargs):
            return subprocess.CompletedProcess(
                cmd, 0, stdout="some-other-tool v1.0.0\n", stderr=""
            )

        monkeypatch.setattr(subprocess, "run", mock_run)

        assert _is_uv_installed() is False

    def test_returns_false_when_uv_not_available(self, monkeypatch):
        """When `uv` command is not found, return False."""
        from teddy_executor.core.services.update_checker import _is_uv_installed

        def mock_run(cmd, *args, **kwargs):
            raise FileNotFoundError("uv not found")

        monkeypatch.setattr(subprocess, "run", mock_run)

        assert _is_uv_installed() is False


class TestGetInstallMethod:
    """Verifies install method detection."""

    def test_returns_uv_when_uv_installed(self, monkeypatch):
        from teddy_executor.core.services.update_checker import (
            _get_install_method,
        )

        monkeypatch.setattr(
            "teddy_executor.core.services.update_checker._is_uv_installed",
            lambda: True,
        )
        assert _get_install_method() == "uv"

    def test_returns_pip_when_not_uv(self, monkeypatch):
        from teddy_executor.core.services.update_checker import (
            _get_install_method,
        )

        monkeypatch.setattr(
            "teddy_executor.core.services.update_checker._is_uv_installed",
            lambda: False,
        )
        assert _get_install_method() == "pip"


class TestPerformUpgrade:
    """Verifies that perform_upgrade uses the correct tool based on install method."""

    def test_uses_uv_tool_upgrade_when_uv_installed(self, monkeypatch):
        """When installed via uv, use `uv tool upgrade teddy-cli`."""
        from teddy_executor.core.services.update_checker import perform_upgrade

        monkeypatch.setattr(
            "teddy_executor.core.services.update_checker._get_install_method",
            lambda: "uv",
        )

        captured_cmd = []

        def mock_run(cmd, *args, **kwargs):
            captured_cmd.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)

        result = perform_upgrade("1.0.0")

        assert result is True
        assert len(captured_cmd) == 1
        assert captured_cmd[0] == ["uv", "tool", "upgrade", "teddy-cli"]

    def test_uv_upgrade_failure_returns_false(self, monkeypatch):
        """When uv upgrade fails, return False."""
        from teddy_executor.core.services.update_checker import perform_upgrade

        monkeypatch.setattr(
            "teddy_executor.core.services.update_checker._get_install_method",
            lambda: "uv",
        )

        def mock_run(cmd, *args, **kwargs):
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="error")

        monkeypatch.setattr(subprocess, "run", mock_run)

        result = perform_upgrade("1.0.0")
        assert result is False

    def test_uses_pip_when_not_uv(self, monkeypatch):
        """When not installed via uv, use pip install --upgrade."""
        from teddy_executor.core.services.update_checker import perform_upgrade

        monkeypatch.setattr(
            "teddy_executor.core.services.update_checker._get_install_method",
            lambda: "pip",
        )

        captured_cmd = []

        def mock_run(cmd, *args, **kwargs):
            captured_cmd.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)

        result = perform_upgrade("1.0.0")

        assert result is True
        assert len(captured_cmd) == 1
        cmd = captured_cmd[0]
        assert cmd[-1] == "teddy-cli"
        assert "pip" in cmd
        assert "install" in cmd
        assert "--upgrade" in cmd

    def test_pip_uses_test_pypi_flag(self, monkeypatch):
        """When index_url is TestPyPI, pip should use --index-url."""
        from teddy_executor.core.services.update_checker import (
            perform_upgrade,
            TEST_PYPI_URL,
        )

        monkeypatch.setattr(
            "teddy_executor.core.services.update_checker._get_install_method",
            lambda: "pip",
        )

        captured_cmd = []

        def mock_run(cmd, *args, **kwargs):
            captured_cmd.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)

        result = perform_upgrade("1.0.0", index_url=TEST_PYPI_URL)

        assert result is True
        assert len(captured_cmd) == 1
        cmd = captured_cmd[0]
        assert "--index-url" in cmd
        assert TEST_PYPI_URL in cmd
