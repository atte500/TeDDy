from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.drivers.cli_adapter import CliTestAdapter


def test_edit_validation_achieves_perfect_match_with_trailing_newlines(
    env, monkeypatch
):
    """
    REGRESSION: Validates that an EDIT action achieves a 1.0 similarity score
    even if the FIND block in the plan doesn't match the file's trailing newline.
    """
    env.setup().with_real_filesystem()
    workspace = env.workspace

    # 1. ARRANGE: Create a file with a standard trailing newline
    # Using the exact content from the MRE report to ensure high fidelity
    content = (
        "    # Then the final execution MUST create bar.py with the modified content\n"
        '    assert (tmp_path / "bar.py").exists()\n'
        '    assert (tmp_path / "bar.py").read_text() == \'print("modified content")\\n\'\n'
        "\n"
        "    # And foo.py MUST NOT exist\n"
        '    assert not (tmp_path / "foo.py").exists()\n'
    )
    repro_file = workspace / "src" / "repro.py"
    repro_file.parent.mkdir(parents=True, exist_ok=True)
    repro_file.write_text(content, encoding="utf-8")

    # Use the exact FIND block from the report
    find_block = (
        "    # Then the final execution MUST create bar.py with the modified content\n"
        '    assert (tmp_path / "bar.py").exists()\n'
        '    assert (tmp_path / "bar.py").read_text() == \'print("modified content")\\n\'\n'
        "\n"
        "    # And foo.py MUST NOT exist\n"
        '    assert not (tmp_path / "foo.py").exists()'  # No trailing newline
    )

    # 2. ACT: Try to EDIT the block
    replace_block = "    # Modified content\n    pass"

    # Using the actual API from plan_builder.py
    plan = (
        MarkdownPlanBuilder("Fix Reproduction")
        .with_agent("Debugger")
        .add_edit(
            "src/repro.py",
            [(find_block, replace_block)],
            description="Update assertion.",
        )
        .build()
    )

    cli = CliTestAdapter(monkeypatch, workspace)

    # Execute (non-interactive, auto-approve)
    report = cli.execute_plan(plan)

    # 3. ASSERT:
    # In the RED phase, this will likely fail validation because Score 0.94 < 0.95.
    # The ReportParser should reflect the FAILED status.
    assert report.summary.get("Overall Status") == "SUCCESS", (
        f"Plan failed validation. Summary: {report.summary}. Action Log: {report.action_logs}"
    )

    edit_log = report.action_logs[0]
    assert edit_log.status == "SUCCESS"
    # Similarity score is stored in params in the ReportParser
    assert float(edit_log.params.get("Similarity Score", 0)) == 1.0
