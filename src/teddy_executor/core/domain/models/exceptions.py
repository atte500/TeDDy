from typing import Optional


class TeddyError(Exception):
    """Root base exception for every project domain and boundary failure."""


class PdfExtractionError(TeddyError):
    """Raised when a PDF payload cannot be parsed into its text layer."""

    def __init__(self, message: str, source: str):
        super().__init__(message)
        self.source = source


class SearchTextNotFoundError(ValueError):
    """Exception for when search text is not found during an edit operation."""

    def __init__(self, message: str, content: str):
        super().__init__(message)
        self.content = content


class FileAlreadyExistsError(FileExistsError):
    """Custom exception raised when trying to create a file that already exists."""

    def __init__(self, message: str, file_path: str):
        super().__init__(message)
        self.file_path = file_path


class MultipleMatchesFoundError(Exception):
    """Custom exception for when an edit operation finds multiple matches."""

    def __init__(self, message: str, content: str):
        super().__init__(message)
        self.content = content


class WebSearchError(Exception):
    """Custom exception raised when a web search operation fails."""

    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        super().__init__(message)
        self.original_exception = original_exception


class ConfigurationError(Exception):
    """Custom exception raised when system configuration is invalid or missing."""

    def __init__(self, message: str):
        super().__init__(message)
