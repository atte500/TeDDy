import difflib


def generate_unified_diff(
    before: str, after: str, filename: str, from_label: str = "a", to_label: str = "b"
) -> str:
    """
    Generates a unified diff between two strings.
    """
    diff_generator = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"{from_label}/{filename}",
        tofile=f"{to_label}/{filename}",
    )

    diff_lines = []
    for line in diff_generator:
        diff_lines.append(line)
        if not line.endswith("\n"):
            diff_lines.append("\n")

    return "".join(diff_lines).rstrip()
