from packaging.version import Version

from teddy_executor.adapters.inbound.cli_helpers import (
    find_project_root,
    prewarm_imports,
)


def test_cli_helpers_is_importable():
    # Simple check to ensure the module can be imported and logic runs
    # This acts as our scaffolding verification.
    assert find_project_root() is not None


def test_prewarm_imports_executes_without_error():
    """Contract test: prewarm_imports() signature exists and is callable."""
    prewarm_imports()


def test_packaging_transitive_dependency():
    """Harness test: confirm `packaging` is available as a transitive dependency
    (via pip-audit) for version comparison in update_checker."""
    v1 = Version("1.0.0")
    v2 = Version("2.0.0")
    assert v2 > v1
    assert not (v1 > v2)
    assert v1 == Version("1.0.0")


def test_init_command_calls_prewarm_imports(monkeypatch):
    """Logic: `teddy init` should call `prewarm_imports()` from cli_helpers.

    Red phase: before the fix, this test will fail because __main__.py's
    init command uses inline imports instead of the extracted helper.
    After the fix, the test passes, confirming the seam is consumed.
    """
    from typer.testing import CliRunner

    call_tracker = []

    def tracking_prewarm():
        call_tracker.append(True)

    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.cli_helpers.prewarm_imports",
        tracking_prewarm,
    )

    # We monkeypatch _ensure_project_initialized to a no-op so the test
    # doesn't require a .teddy directory or container wiring.
    monkeypatch.setattr(
        "teddy_executor.__main__._ensure_project_initialized",
        lambda container: None,
    )

    import teddy_executor.__main__ as main_app

    runner = CliRunner()
    result = runner.invoke(main_app.app, ["init"])

    assert result.exit_code == 0
    assert len(call_tracker) == 1, (
        f"Expected prewarm_imports to be called exactly 1 time, "
        f"got {len(call_tracker)}. Before the fix, the init command "
        f"uses inline imports instead of calling prewarm_imports()."
    )
