"""PDF -> text using pypdf (pure Python, no system deps)."""

from __future__ import annotations

import io

from pypdf import PdfReader


def pdf_to_text(data: bytes, max_pages: int = 10) -> str:
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages[:max_pages]:
        pages.append(page.extract_text() or "")
    return "\n".join(pages).strip()
