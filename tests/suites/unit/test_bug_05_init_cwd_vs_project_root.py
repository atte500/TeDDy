"""Regression test for Bug #05: teddy init should create .teddy/ in CWD,
not in the nearest parent project root.

Root cause: _ensure_project_initialized() used find_project_root(), which
walks up from CWD looking for an existing .teddy/ directory. When running
inside an existing project tree, it returned the parent project root instead
of CWD, causing the adapter to target the existing .teddy/ rather than
creating a new one in the current working directory.

Fix: replaced find_project_root() with Path.cwd() in _ensure_project_initialized().
"""

from typer.testing import CliRunner

from teddy_executor.__main__ import app


def test_init_creates_teddy_in_cwd_when_parent_has_teddy(tmp_path, monkeypatch):
    """Given a parent directory with .teddy/, running 'init' from a subdirectory
    should create .teddy/ in the subdirectory (CWD), not in the parent.

    This is the exact scenario reported in Bug #05: the user ran 'teddy init'
    in testing_shit/ which is inside the TeDDy project tree (which has .teddy/
    at the root). The bug caused init to silently update the parent .teddy/
    instead of creating a new one in testing_shit/.
    """
    # Setup: parent has an existing .teddy/ directory (simulating an existing project)
    parent_teddy = tmp_path / ".teddy"
    parent_teddy.mkdir()
    (parent_teddy / "config.yaml").write_text("# Parent config", encoding="utf-8")

    # Create subdirectory (the CWD where user runs init)
    subdir = tmp_path / "subdir"
    subdir.mkdir()

    # Run init from subdirectory
    monkeypatch.chdir(str(subdir))

    # Reset container cache to simulate fresh CLI invocation
    from teddy_executor import container as container_module

    if hasattr(container_module, "_container"):
        container_module._container = None

    runner = CliRunner()
    result = runner.invoke(app, ["init"])

    # Assert init command completed successfully
    assert result.exit_code == 0
    assert "TeDDy initialized" in result.stdout

    # .teddy should be created in CWD (subdir), NOT inherited from parent
    cwd_teddy = subdir / ".teddy"
    assert cwd_teddy.is_dir(), (
        f".teddy should be created in CWD ({subdir}), not in parent.\n"
        f"Parent .teddy: {parent_teddy} (exists={parent_teddy.exists()})\n"
        f"Subdir .teddy: {cwd_teddy} (exists={cwd_teddy.exists()})\n"
        f"Bug symptom: parent .teddy/ was incorrectly targeted."
    )

    # Verify expected template files were created
    expected_found = []
    for fname in [".gitignore", "config.yaml", "init.context", "prompts"]:
        fpath = cwd_teddy / fname
        exists = fpath.exists()
        expected_found.append(f"{fname}={exists}")
        if not exists:
            print(f"WARNING: Expected file {fname} not found in {cwd_teddy}")

    # Parent .teddy/ should remain unchanged
    parent_config = parent_teddy / "config.yaml"
    assert parent_config.exists(), "Parent config.yaml should still exist"
    assert parent_config.read_text(encoding="utf-8") == "# Parent config", (
        "Parent config.yaml should remain unchanged"
    )

    # Verify at least the core files exist (config.yaml and init.context are the minimum)
    assert (cwd_teddy / "config.yaml").exists(), (
        "config.yaml should exist in new .teddy/"
    )
    assert (cwd_teddy / "init.context").exists(), (
        "init.context should exist in new .teddy/"
    )
