from tests.harness.setup.mocking import register_mock
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase
from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager


def setup_session_workspace(tmp_path, session_name="test-session"):
    session_dir = tmp_path / ".teddy" / "sessions" / session_name
    turn_01_dir = session_dir / "01"
    turn_01_dir.mkdir(parents=True)

    (tmp_path / "file_a.txt").write_text("content a", encoding="utf-8")
    (tmp_path / "file_b.txt").write_text(
        "content b" * 10, encoding="utf-8"
    )  # Larger file

    (session_dir / "session.context").write_text("file_a.txt", encoding="utf-8")
    (turn_01_dir / "turn.context").write_text("file_b.txt", encoding="utf-8")
    (turn_01_dir / "meta.yaml").write_text("turn_id: '01'\n", encoding="utf-8")
    (turn_01_dir / "pathfinder.xml").write_text("<p>S</p>", encoding="utf-8")

    return session_dir, turn_01_dir


def test_pruning_persistence_in_interactive_execution(container, tmp_path):
    """
    Scenario: Pruned files in interactive mode are removed from next turn's manifest.
    """
    # Arrange
    container.register(
        IFileSystemManager, LocalFileSystemAdapter, root_dir=str(tmp_path)
    )

    mock_config = register_mock(container, IConfigService)
    # Pruning service uses config_service for thresholds
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "auto_pruning.enabled": True,
        "auto_pruning.global_context_threshold": 5,
    }.get(key, default)

    mock_prompts = register_mock(container, IPromptManager)
    mock_prompts.fetch_system_prompt.return_value = ""
    mock_prompts.resolve_agent_metadata.return_value = ("pf", {}, "meta.yaml")

    mock_reviewer = register_mock(container, IPlanReviewer)
    # review returns the plan (approved); review_action returns (True, "") (approved, no message)
    mock_reviewer.review.side_effect = lambda plan, **kwargs: plan
    mock_reviewer.review_action.return_value = (True, "")

    mock_llm = register_mock(container, ILlmClient)
    mock_llm.validate_config.return_value = []
    # 'content a' ~ 2 tokens, 'content b' * 10 ~ 20 tokens.
    mock_llm.get_text_token_count.side_effect = lambda x: len(x.split())
    mock_llm.get_context_window.return_value = (
        1000  # Large window, we rely on threshold
    )

    # Mock Planning
    mock_planning = register_mock(container, IPlanningUseCase)
    mock_planning.generate_plan.return_value = ("Corrected Plan", 0.0)
    container.register(IPlanningUseCase, instance=mock_planning)

    orchestrator = container.resolve(IRunPlanUseCase)
    session_dir, turn_01_dir = setup_session_workspace(tmp_path)

    builder = MarkdownPlanBuilder("Test Plan").with_agent("Pathfinder")
    builder.add_execute("ls")
    plan_path = turn_01_dir / "plan.md"
    plan_path.write_text(builder.build(), encoding="utf-8")

    # Act
    orchestrator.execute(plan_path=str(plan_path), interactive=True)

    # Assert
    next_turn_context = (session_dir / "02" / "turn.context").read_text()
    assert "file_a.txt" not in next_turn_context  # file_a is in session.context
    assert "file_b.txt" not in next_turn_context  # file_b was pruned
    assert ".teddy/sessions/test-session/01/plan.md" in next_turn_context
    assert ".teddy/sessions/test-session/01/report.md" in next_turn_context


def test_pruning_persistence_in_replan_loop(container, tmp_path):
    """
    Scenario: Pruned files during a turn that fails validation are removed from the replan turn's manifest.
    """
    # Arrange
    container.register(
        IFileSystemManager, LocalFileSystemAdapter, root_dir=str(tmp_path)
    )

    mock_config = register_mock(container, IConfigService)
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "auto_pruning.enabled": True,
        "auto_pruning.global_context_threshold": 5,
    }.get(key, default)

    mock_prompts = register_mock(container, IPromptManager)
    mock_prompts.fetch_system_prompt.return_value = ""
    mock_prompts.resolve_agent_metadata.return_value = ("pf", {}, "meta.yaml")

    mock_reviewer = register_mock(container, IPlanReviewer)
    # review returns the plan (approved); review_action returns (True, "") (approved, no message)
    mock_reviewer.review.side_effect = lambda plan, **kwargs: plan
    mock_reviewer.review_action.return_value = (True, "")

    mock_llm = register_mock(container, ILlmClient)
    mock_llm.validate_config.return_value = []
    mock_llm.get_text_token_count.side_effect = lambda x: len(x.split())
    mock_llm.get_context_window.return_value = 1000

    # Mock Planning
    mock_planning = register_mock(container, IPlanningUseCase)
    mock_planning.generate_plan.return_value = ("Corrected Plan", 0.0)

    orchestrator = container.resolve(IRunPlanUseCase)
    session_dir, turn_01_dir = setup_session_workspace(tmp_path)

    # Trigger validation error: CREATE file that already exists (file_a.txt)
    builder = MarkdownPlanBuilder("Faulty Plan").with_agent("Pathfinder")
    builder.add_create(path="file_a.txt", content="content")
    plan_path = turn_01_dir / "plan.md"
    plan_path.write_text(builder.build(), encoding="utf-8")

    # Act
    orchestrator.execute(plan_path=str(plan_path))

    # Assert
    next_turn_context = (session_dir / "02" / "turn.context").read_text()
    assert "file_b.txt" not in next_turn_context  # file_b should still be pruned
    assert ".teddy/sessions/test-session/01/plan.md" in next_turn_context


def test_deduplication_prevents_aggressive_pruning(container, tmp_path):
    """
    Scenario: Overlapping files are deduplicated, preventing budget inflation.
    """
    # Arrange
    container.register(
        IFileSystemManager, LocalFileSystemAdapter, root_dir=str(tmp_path)
    )

    mock_config = register_mock(container, IConfigService)
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "auto_pruning.enabled": True,
        "auto_pruning.global_context_threshold": 20,
    }.get(key, default)

    mock_prompts = register_mock(container, IPromptManager)
    mock_prompts.fetch_system_prompt.return_value = ""
    mock_prompts.resolve_agent_metadata.return_value = ("pf", {}, "meta.yaml")

    mock_reviewer = register_mock(container, IPlanReviewer)
    # review returns the plan (approved); review_action returns (True, "") (approved, no message)
    mock_reviewer.review.side_effect = lambda plan, **kwargs: plan
    mock_reviewer.review_action.return_value = (True, "")

    mock_llm = register_mock(container, ILlmClient)
    mock_llm.validate_config.return_value = []
    # Both files are 9 tokens. Total 18 tokens.
    mock_llm.get_text_token_count.return_value = 9
    mock_llm.get_context_window.return_value = 1000

    # Mock Planning
    mock_planning = register_mock(container, IPlanningUseCase)
    mock_planning.generate_plan.return_value = ("Corrected Plan", 0.0)

    orchestrator = container.resolve(IRunPlanUseCase)
    session_dir, turn_01_dir = setup_session_workspace(tmp_path)

    # Add file_a to turn.context as well (it's already in session.context)
    (turn_01_dir / "turn.context").write_text(
        "file_a.txt\nfile_b.txt", encoding="utf-8"
    )

    builder = MarkdownPlanBuilder("Test Plan").with_agent("Pathfinder")
    builder.add_execute("ls")
    plan_path = turn_01_dir / "plan.md"
    plan_path.write_text(builder.build(), encoding="utf-8")

    # Act
    orchestrator.execute(plan_path=str(plan_path), interactive=False)

    # Assert
    next_turn_context = (session_dir / "02" / "turn.context").read_text()
    # If deduplication works, file_b should NOT be pruned
    assert "file_b.txt" in next_turn_context
