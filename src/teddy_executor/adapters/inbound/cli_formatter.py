import os


from teddy_executor.core.domain.models import ContextResult
from teddy_executor.core.utils.markdown import get_fence_for_content


def _get_file_extension(file_path: str) -> str:
    """Extracts the file extension for code block formatting."""
    ext_map = {
        ".py": "python",
        ".md": "markdown",
        ".js": "javascript",
        ".html": "html",
        ".css": "css",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".sh": "shell",
    }
    ext = os.path.splitext(file_path)[1]
    return ext_map.get(ext, "")


def format_project_context(context: ContextResult) -> str:
    """Formats the ContextResult DTO into a structured string for display."""
    output_parts = []
    output_parts.append("# System Information")
    for key, value in sorted(context.system_info.items()):
        if key != "python_version":
            output_parts.append(f"{key}: {value}")
    output_parts.append("\n# Repository Tree")
    output_parts.append(context.repo_tree)
    output_parts.append("\n# Context Vault")
    output_parts.extend(sorted(context.context_vault_paths))
    output_parts.append("\n# File Contents")
    for path in sorted(context.file_contents.keys()):
        content = context.file_contents[path]
        if content is None:
            output_parts.append(f"## {path} (Not Found)")
        else:
            extension = _get_file_extension(path)
            fence = get_fence_for_content(content)
            if path.startswith("http:") or path.startswith("https:"):
                link_path = path
            else:
                link_path = f"/{path}" if not path.startswith("/") else path
            output_parts.append(f"## [{path}]({link_path})")
            output_parts.append(f"{fence}{extension}\n{content}\n{fence}")
    return "\n".join(output_parts)
