import re

# Exhaustive English stopwords to strip from session names for conciseness
STOPWORDS = {
    "a",
    "about",
    "actually",
    "above",
    "after",
    "again",
    "all",
    "also",
    "am",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "doing",
    "down",
    "during",
    "each",
    "few",
    "for",
    "from",
    "further",
    "get",
    "had",
    "has",
    "have",
    "having",
    "he",
    "hello",
    "help",
    "hey",
    "hi",
    "her",
    "here",
    "hers",
    "herself",
    "him",
    "himself",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "itself",
    "just",
    "kindly",
    "like",
    "me",
    "more",
    "most",
    "my",
    "myself",
    "no",
    "nor",
    "now",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "please",
    "our",
    "ours",
    "ourselves",
    "out",
    "over",
    "own",
    "s",
    "same",
    "she",
    "should",
    "so",
    "some",
    "such",
    "t",
    "than",
    "thank",
    "thanks",
    "that",
    "the",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "want",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "whom",
    "why",
    "will",
    "with",
    "would",
    "you",
    "your",
    "yours",
    "yourself",
    "yourselves",
    "using",
    "basically",
    "simply",
    "really",
    "dont",
    "arent",
    "yet",
    "cant",
    "wont",
    "shouldnt",
    "couldnt",
    "didnt",
    "hasnt",
    "havent",
    "isnt",
    "wasnt",
    "werent",
    "im",
    "youre",
    "hes",
    "shes",
    "theyre",
    "ive",
    "youve",
    "weve",
    "theyve",
    "ill",
    "youll",
    "hell",
    "shell",
    "well",
    "theyll",
    "id",
    "youd",
    "hed",
    "shed",
    "wed",
    "theyd",
    "going",
    "gonna",
    "wanna",
    "gotta",
    "ok",
    "okay",
    "sure",
    "surely",
    "maybe",
    "perhaps",
    "already",
}


def slugify(text: str, max_length: int = 40) -> str:
    """
    Converts a string into a URL-friendly slug.

    1. Lowercase and strip apostrophes (e.g., don't -> dont).
    2. Split into words and remove aggressive stopwords.
    3. Join words with hyphens until max_length is reached (whole-word truncation).
    """
    # 1. Lowercase and strip apostrophes
    s = text.lower().replace("'", "")

    # 2. Split and filter stopwords
    all_words = [w for w in re.split(r"[^a-z0-9]+", s) if w and w not in STOPWORDS]

    # 3. Build slug word by word to respect max_length
    slug_words: list[str] = []
    current_length = 0
    for word in all_words:
        # Word length + hyphen (if not first word)
        added_length = len(word) + (1 if slug_words else 0)
        if current_length + added_length > max_length:
            break
        slug_words.append(word)
        current_length += added_length

    return "-".join(slug_words)


def truncate_lines(
    content: str,
    max_lines: int,
    direction: str = "tail",
    hint: str = "",
    action_type: str | None = None,
) -> str:
    """
    Truncates a string to a maximum number of lines.

    Args:
        content: The text to truncate.
        max_lines: Maximum number of lines to preserve.
        direction: "head" (preserve first X) or "tail" (preserve last X).
        hint: An optional message to include when truncation occurs.
        action_type: Optional "execute" or "read" to generate a dynamic hint.
    """
    if not content or max_lines <= 0:
        return content

    lines = content.splitlines()
    total_lines = len(lines)
    if total_lines <= max_lines:
        return content

    # Generate dynamic hint if action_type is provided
    if action_type:
        hint = get_truncation_hint(action_type, max_lines, total_lines)

    if direction == "tail":
        truncated = "\n".join(lines[-max_lines:])
        return f"{hint}\n{truncated}" if hint else truncated
    elif direction == "head":
        truncated = "\n".join(lines[:max_lines])
        return f"{truncated}\n{hint}" if hint else truncated
    else:
        raise ValueError(f"Invalid truncation direction: {direction}")


def get_truncation_hint(action_type: str, max_lines: int, total_lines: int) -> str:
    """
    Returns a context-specific hint for truncated output based on the action type.
    """
    action_type = action_type.lower()
    if action_type == "execute":
        return (
            f"[Output truncated: Showing last {max_lines} of {total_lines} lines. "
            "Pipe output to a file or use grep/sed to filter results.]"
        )
    if action_type == "read":
        return (
            f"[Content truncated: Showing first {max_lines} of {total_lines} lines. "
            "Use grep or sed via EXECUTE to read specific sections.]"
        )

    return f"[Content truncated: Showing {max_lines} of {total_lines} lines.]"


# double_newlines has been removed. It was a band-aid that became harmful:
# blind \n → \n\n replacement broke tables, lists, and code blocks.
# The correct fix is raw text extraction in parse_message_action, which preserves
# the LLM's original formatting exactly. See action_parser_complex.py.
