from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter


def test_execute_respects_timeout(mocker):
    """
    Asserts that the timeout parameter is passed correctly to subprocess.run.
    We don't test actual subprocess timeouts here (Scenario 2),
    just that the parameter is accepted and propagated.
    """
    mock_run = mocker.patch("subprocess.run")
    # Setup mock_run to return a successful CompletedProcess
    mock_run.return_value = mocker.Mock(returncode=0, stdout="", stderr="")

    adapter = ShellAdapter()

    # Act
    timeout_threshold = 10
    adapter.execute("echo test", timeout=timeout_threshold)

    # Assert
    # We check the arguments passed to subprocess.run
    args, kwargs = mock_run.call_args
    assert kwargs.get("timeout") == timeout_threshold


def test_execute_works_without_timeout(mocker):
    """
    Asserts that the adapter still works without a timeout (defaults to None).
    """
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = mocker.Mock(returncode=0, stdout="", stderr="")

    adapter = ShellAdapter()
    adapter.execute("echo test")

    args, kwargs = mock_run.call_args
    assert kwargs.get("timeout") is None
