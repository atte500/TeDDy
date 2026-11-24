"""Deterministic, in-repo PDF builder for the test harness.

Builds a minimal single-page PDF as raw bytes with hand-computed cross-reference
offsets. The document is uncompressed, so no binary fixture is committed and the
same bytes can be parsed by pypdf (proven by the harness gate test) or fed to a
fake IPdfExtractor.
"""

from __future__ import annotations

DEFAULT_PDF_TEXT = "Hello PDF"


def build_minimal_pdf(text: str = DEFAULT_PDF_TEXT) -> bytes:
    """Return a minimal one-page PDF whose Helvetica content stream renders ``text``.

    The text layer is uncompressed and wrapped in the standard ``BT ... Tj ET``
    operators, so ``pypdf`` extracts it verbatim. ``text`` must not contain raw
    parentheses, which would terminate the PDF string literal early.
    """
    content = f"BT /F1 24 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length "
        + str(len(content)).encode("ascii")
        + b" >>\nstream\n"
        + content
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref_at = len(out)
    size = len(objects) + 1
    out += f"xref\n0 {size}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode(
        "ascii"
    )
    return bytes(out)


def build_encrypted_pdf(password: str = "secret") -> bytes:
    """Return a minimal PDF whose document stream requires ``password``.

    Built inside the function so only tests exercising the encrypted branch pay
    the pypdf import. RC4-128 is pure Python, so no optional crypto extra is
    required to build or parse the fixture.
    """
    import io

    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt(user_password=password, algorithm="RC4-128")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
