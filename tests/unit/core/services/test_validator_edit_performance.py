import time
from teddy_executor.core.services.validation_rules.edit import EditActionValidator
from teddy_executor.core.domain.models.plan import ActionData


def test_edit_validator_performance_large_file(mock_fs):
    """
    Inner Loop RED: Assert that EditActionValidator.validate() handles large files
    in under 100ms when a match is not found.
    """
    # 1. Setup large content (500 lines) with repeating patterns
    # Using repeating lines forces the anchor heuristic to find multiple candidates.
    lines = [
        f"Line {i % 10:03}: This line repeats every 10 lines to stress the matcher. Content...\n"
        for i in range(500)
    ]
    file_content = "".join(lines)

    # 2. Setup large FIND block (100 lines) that is ALMOST a match
    # We take a slice and modify the content of one line.
    # Since the file lines contain "This line repeats", we modify it in the FIND block.
    target_lines = list(lines[200:300])
    target_lines[50] = target_lines[50].replace("repeats", "REPEATS_MODIFIED")
    find_block = "".join(target_lines)

    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = file_content

    validator = EditActionValidator(mock_fs)

    action = ActionData(
        type="EDIT",
        description="Performance check",
        params={
            "path": "large_file.txt",
            "edits": [{"find": find_block, "replace": "Optimized!"}],
        },
        node=None,
    )

    # 3. Benchmark the validation
    start_time = time.perf_counter()
    errors = validator.validate(action)
    duration = time.perf_counter() - start_time

    # 4. Assertions
    assert len(errors) == 1
    # Large repeating patterns in the setup trigger ambiguity at 0.96
    assert "ambiguous" in errors[0].message.lower()

    # 100ms is a generous budget for the optimized version (RCA says 10ms)
    # but the current logic takes ~15-20s.
    performance_budget_seconds = 0.1
    assert duration < performance_budget_seconds, (
        f"Validation took {duration:.4f}s, exceeding {performance_budget_seconds}s budget."
    )
