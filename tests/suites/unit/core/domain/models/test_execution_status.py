from teddy_executor.core.domain.models.plan import ExecutionStatus


def test_execution_status_includes_running_and_skipped():
    assert "RUNNING" in ExecutionStatus.__members__
    assert "SKIPPED" in ExecutionStatus.__members__
    assert ExecutionStatus.RUNNING == "RUNNING"
    assert ExecutionStatus.SKIPPED == "SKIPPED"
