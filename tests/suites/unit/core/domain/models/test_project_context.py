from teddy_executor.core.domain.models.project_context import (
    ProjectContext,
    ContextItem,
)


def test_context_item_creation():
    """
    Verify that the ContextItem DTO can be instantiated correctly.
    """
    item = ContextItem(
        path="src/core.py",
        token_count=1200,
        git_status="M",
        scope="Session",
        selected=True,
        auto_prune_reason="Pruned to fit context budget",
    )

    assert item.path == "src/core.py"
    assert item.token_count == 1200
    assert item.git_status == "M"
    assert item.scope == "Session"
    assert item.selected is True
    assert item.auto_prune_reason == "Pruned to fit context budget"


def test_context_item_defaults():
    """
    Verify default values for ContextItem.
    """
    item = ContextItem(path="p", token_count=1, git_status="", scope="Turn")
    assert item.selected is True
    assert item.auto_prune_reason is None


def test_project_context_expansion():
    """
    Verify the expanded fields in ProjectContext.
    """
    item = ContextItem(path="p", token_count=1, git_status="", scope="Turn")
    project_context = ProjectContext(
        header="H",
        content="C",
        items=[item],
        agent_name="Architect",
        system_prompt_tokens=2500,
        total_window=128000,
    )

    assert project_context.items == [item]
    assert project_context.agent_name == "Architect"
    assert project_context.system_prompt_tokens == 2500
    assert project_context.total_window == 128000


def test_project_context_expansion_defaults():
    """
    Verify defaults for the expanded fields in ProjectContext.
    """
    project_context = ProjectContext(header="H", content="C")
    assert project_context.items == []
    assert project_context.agent_name == "Unknown"
    assert project_context.system_prompt_tokens == 0
    assert project_context.total_window == 0


def test_project_context_creation():
    """
    Verify that the ProjectContext dataclass can be instantiated correctly
    and that its attributes are properly assigned.
    """
    header = "Test Header"
    content = "Test Content"
    project_context = ProjectContext(header=header, content=content)

    assert project_context.header == header
    assert project_context.content == content


def test_project_context_supports_optional_git_status():
    """
    Verify that ProjectContext can be initialized with an optional git_status.
    """
    git_status = " M file.py\n?? new.txt"
    project_context = ProjectContext(header="H", content="C", git_status=git_status)

    assert project_context.git_status == git_status


def test_project_context_git_status_defaults_to_none():
    """
    Verify that git_status defaults to None if not provided.
    """
    project_context = ProjectContext(header="H", content="C")
    assert project_context.git_status is None
