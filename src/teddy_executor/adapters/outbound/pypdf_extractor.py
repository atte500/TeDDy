"""Concrete IPdfExtractor backed by a lazily imported pypdf."""

import io

from teddy_executor.core.domain.models.exceptions import PdfExtractionError
from teddy_executor.core.ports.outbound.pdf_extractor import IPdfExtractor
from teddy_executor.core.utils.pdf import require_pdf_magic


class PypdfExtractor(IPdfExtractor):
    """Extracts the text layer from raw PDF bytes using pypdf."""

    def _get_pypdf(self):
        """Lazy-load pypdf to keep CLI startup fast."""
        import pypdf

        return pypdf

    def extract_text(self, data: bytes, source: str) -> str:
        """Extract the text layer from ``data``, naming ``source`` on failure."""
        require_pdf_magic(data, source)
        pypdf = self._get_pypdf()

        try:
            reader = pypdf.PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise PdfExtractionError(
                    f"PDF '{source}' is encrypted and requires a password",
                    source=source,
                )
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except PdfExtractionError:
            raise
        except pypdf.errors.PyPdfError as error:
            raise PdfExtractionError(
                f"Failed to parse PDF '{source}': {error}", source=source
            ) from error

        if not text.strip():
            raise PdfExtractionError(
                f"PDF '{source}' contains no extractable text layer", source=source
            )
        return text
