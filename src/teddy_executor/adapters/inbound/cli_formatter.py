from teddy_executor.core.domain.models import ProjectContext


def format_project_context(context: ProjectContext) -> str:
    """
    Formats the ProjectContext DTO into a single string for display.
    The actual formatting is now done in the ContextService. This function
    simply combines the pre-formatted parts.
    """
    return f"{context.header}\n{context.content}"
