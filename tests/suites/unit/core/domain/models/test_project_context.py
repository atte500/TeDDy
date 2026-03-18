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
