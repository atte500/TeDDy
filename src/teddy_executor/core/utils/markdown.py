import re


def get_fence_for_content(content: str) -> str:
    """
    Returns a markdown code fence string (e.g., "```") that is safe to use
    for enclosing the given content.

    The length of the fence will be at least 3, and strictly greater than
    the longest sequence of backticks found in the content.
    """
    if not content:
        return "```"

    # Find all sequences of backticks
    backtick_sequences = re.findall(r"`+", content)

    max_backticks = 0
    if backtick_sequences:
        max_backticks = max(len(seq) for seq in backtick_sequences)

    # Ensure fence is at least 3, and at least one longer than max found
    fence_length = max(3, max_backticks + 1)

    return "`" * fence_length
