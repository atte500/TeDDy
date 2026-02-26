from teddy_executor.adapters.inbound.cli_formatter import format_project_context
from teddy_executor.core.domain.models import ProjectContext


def test_format_project_context():
    """
    Given a ProjectContext DTO,
    When format_project_context is called,
    Then it should return a string that concatenates the header and content.
    """
    # Arrange
    header = "# System Info"
    content = "# Repo Tree"
    context = ProjectContext(header=header, content=content)

    # Act
    output = format_project_context(context)

    # Assert
    expected_output = f"{header}\n{content}"
    assert output == expected_output
