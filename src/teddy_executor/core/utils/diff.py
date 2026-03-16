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


def generate_character_diff(before: str, after: str, context: int = 2) -> str:
    """
    Generates a character-level diff using ndiff with hunk-based filtering.
    Shows changed lines, their context, and joins hunks with '...'.
    """
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    diff = list(difflib.ndiff(before_lines, after_lines))

    # Identify lines that must be included (changes)
    must_include = [i for i, line in enumerate(diff) if line[0] in ("-", "+", "?")]
    if not must_include:
        return ""

    # Expand to include context around each change
    included_indices = set()
    for idx in must_include:
        for i in range(max(0, idx - context), min(len(diff), idx + context + 1)):
            included_indices.add(i)

    # Build hunks from sorted indices
    sorted_indices = sorted(list(included_indices))
    res_lines = []
    last_idx = -1

    for idx in sorted_indices:
        if last_idx != -1 and idx > last_idx + 1:
            res_lines.append("...")
        res_lines.append(diff[idx].rstrip("\n\r"))
        last_idx = idx

    return "\n".join(res_lines)
