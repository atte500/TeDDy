from typing import Protocol, runtime_checkable


@runtime_checkable
class IPdfExtractor(Protocol):
    """
    An outbound port for turning raw PDF bytes into extractable text.
    """

    def extract_text(self, data: bytes, source: str) -> str:
        """
        Extracts the text layer from a PDF payload.

        Preconditions:
            ``data`` holds the raw bytes of a PDF document.
        Postconditions:
            Returns the extracted text. ``source`` names the local path or URL
            the payload came from so a failure can report where it originated.

        Raises:
            PdfExtractionError: When the payload is unparseable, carries no
                text layer, or requires a password.
        """
        ...
