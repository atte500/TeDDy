"""Build a minimal one-page PDF whose header reproduces the crash offset.

The reported failure used a real-world download, but the reproduction depends on
only two properties: the ``%PDF-1.x\\r%`` header places a binary comment marker
at byte index 10 (so a UTF-8 decode fails at exactly ``position 10``), and the
payload is a parseable document (so the extractor path can demonstrate the fix).
A hand-built fixture supplies both, keeping the MRE self-contained instead of
depending on an untracked 315 KB download.

The fixture is written to ``.tmp/debug/`` and its project-root-relative path is
returned, matching what the file system adapter resolves against.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_RELATIVE_PATH = ".tmp/debug/pdf-context-fixture.pdf"

# Same 16-byte prefix as the reported document: the comment marker starts at
# index 10, which is what makes the naive decode fail at that offset.
HEADER = b"%PDF-1.6\r%\xe2\xe3\xcf\xd3\r\n"
CONTENT_STREAM = b"BT /F1 14 Tf 72 720 Td (Context PDF fixture) Tj ET"


def _document_objects() -> list[bytes]:
    """The minimal object set for a one-page document with a text layer."""
    return [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
        b"/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
        b"<</Length %d>>stream\n%s\nendstream" % (len(CONTENT_STREAM), CONTENT_STREAM),
    ]


def build_fixture_pdf(destination: str = FIXTURE_RELATIVE_PATH) -> str:
    """Write the fixture PDF and return its project-root-relative path."""
    objects = _document_objects()
    body = bytearray(HEADER)
    offsets: list[int] = []
    for number, payload in enumerate(objects, start=1):
        offsets.append(len(body))
        body += b"%d 0 obj\n" % number + payload + b"\nendobj\n"

    xref_offset = len(body)
    body += b"xref\n0 %d\n" % (len(objects) + 1)
    body += b"0000000000 65535 f \n"
    for offset in offsets:
        body += b"%010d 00000 n \n" % offset
    body += b"trailer\n<</Size %d/Root 1 0 R>>\nstartxref\n%d\n" % (
        len(objects) + 1,
        xref_offset,
    )
    body += b"%%EOF\n"

    target = PROJECT_ROOT / destination
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(bytes(body))
    return destination
