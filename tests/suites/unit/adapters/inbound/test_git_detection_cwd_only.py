"""Regression test: git detection should check CWD only, not parent directories.

When running `teddy start` from a new subfolder inside an existing
git repo, the function incorrectly reports "Git repository detected" because
`git rev-parse --git-dir` walks up the directory tree. Fixed to check only
(Path.cwd() / ".git").exists().
"""


def test_check_git_not_detected_in_parent_repo_subfolder(monkeypatch):
    """When CWD is a subfolder of a git repo but has no local .git,
    _check_git_initialized should NOT print 'Git repository detected'.
    It should fall through to git init and print 'Git repository initialized'."""
    import typer

    messages = []

    def fake_secho(msg, fg=None, err=None):
        messages.append((msg, fg, err))

    monkeypatch.setattr("typer.secho", fake_secho)
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/git")

    # Pretend .git does NOT exist in CWD (as in a fresh empty subfolder)
    def controlled_exists(self):
        if self.name == ".git":
            return False
        return True

    monkeypatch.setattr("pathlib.Path.exists", controlled_exists)

    # Mock git init to succeed
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers.subprocess.run",
        lambda *args, **kwargs: type("FakeResult", (), {"returncode": 0})(),
    )

    from teddy_executor.adapters.inbound.session_cli_handlers import (
        _check_git_initialized,
    )

    _check_git_initialized()

    # Must NOT print "detected"; must print "initialized" instead
    assert len(messages) == 1, f"Expected 1 secho call, got {len(messages)}"
    msg, fg, err = messages[0]
    assert "Git repository initialized" in msg, (
        f"Expected 'Git repository initialized', got '{msg}'"
    )
    assert fg == typer.colors.GREEN
    assert err is True
