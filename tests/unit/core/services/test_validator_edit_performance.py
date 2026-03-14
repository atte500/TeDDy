import time
from teddy_executor.core.services.validation_rules.edit import EditActionValidator
from teddy_executor.core.domain.models.plan import ActionData


def test_edit_validator_performance_large_file(mock_fs):
    """
    Inner Loop RED: Assert that EditActionValidator.validate() handles large files
    in under 100ms when a match is not found.
    """
    # 1. Setup large content (500 lines)
    lines = [
        f"Line {i:03}: Standard content for performance testing. Index {i}.\n"
        for i in range(500)
    ]
    file_content = "".join(lines)

    # 2. Setup large FIND block (100 lines) that is ALMOST a match
    # This triggers the expensive fuzzy matching logic.
    find_lines = lines[200:300]
    find_block = "".join(find_lines).replace("Index 250", "Index 250 MODIFIED")

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
    assert "The `FIND` block could not be located" in errors[0].message
    assert "Closest Match Diff" in errors[0].message

    # 100ms is a generous budget for the optimized version (RCA says 10ms)
    # but the current logic takes ~15-20s.
    performance_budget_seconds = 0.1
    assert duration < performance_budget_seconds, (
        f"Validation took {duration:.4f}s, exceeding {performance_budget_seconds}s budget."
    )
