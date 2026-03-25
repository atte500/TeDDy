from teddy_executor.core.domain.models.project_context import ProjectContext


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
