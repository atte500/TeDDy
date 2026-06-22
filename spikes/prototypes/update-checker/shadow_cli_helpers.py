"""
Shadow Module: CLI Helpers (Prewarm Extraction)
=================================================
Demonstrates extraction of prewarm_imports() from __main__.py into cli_helpers.py.
The function is identical to the inline block in __main__.py init() command.
"""


def prewarm_imports() -> None:
    """
    Pre-warm heavy imports to reduce first-run latency.
    Extracted from __main__.py init command for reuse by update command.

    Originally inline at __main__.py L172-L183:
        try:
            import litellm  # noqa: F401
            import trafilatura  # noqa: F401
            import pyperclip  # noqa: F401
            from bs4 import BeautifulSoup  # noqa: F401
            from ddgs import DDGS  # noqa: F401
        except ImportError:
            pass  # Some optional dependencies may not be installed
    """
    try:
        import litellm  # noqa: F401
        import trafilatura  # noqa: F401
        import pyperclip  # noqa: F401
        from bs4 import BeautifulSoup  # noqa: F401
        from ddgs import DDGS  # noqa: F401
    except ImportError:
        pass  # Some optional dependencies may not be installed