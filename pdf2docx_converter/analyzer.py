"""Pre-flight analysis of a PDF before conversion.

Goal: decide whether the file is a *digital* PDF (has a real text layer) so we
can warn early instead of producing an empty/garbage DOCX. Scanned PDFs (no
text layer) are out of scope for now and require OCR.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF


@dataclass
class PdfReport:
    path: Path
    page_count: int
    pages_with_text: int
    total_chars: int
    has_images: bool
    is_encrypted: bool

    @property
    def text_coverage(self) -> float:
        """Share of pages that contain extractable text (0.0 - 1.0)."""
        if self.page_count == 0:
            return 0.0
        return self.pages_with_text / self.page_count

    @property
    def is_digital(self) -> bool:
        """Heuristic: most pages carry real text -> safe to convert locally."""
        return self.total_chars > 0 and self.text_coverage >= 0.5

    @property
    def likely_scanned(self) -> bool:
        """Pages render images but expose little/no text -> needs OCR."""
        return self.has_images and self.total_chars < 20


def analyze(pdf_path: str | Path) -> PdfReport:
    """Inspect a PDF and return a lightweight report (does not convert)."""
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    doc = fitz.open(path)
    try:
        is_encrypted = doc.is_encrypted
        # An empty password unlocks many "owner-only" encrypted PDFs.
        if is_encrypted:
            doc.authenticate("")

        pages_with_text = 0
        total_chars = 0
        has_images = False

        for page in doc:
            text = page.get_text("text").strip()
            if text:
                pages_with_text += 1
                total_chars += len(text)
            if not has_images and page.get_images(full=True):
                has_images = True

        return PdfReport(
            path=path,
            page_count=doc.page_count,
            pages_with_text=pages_with_text,
            total_chars=total_chars,
            has_images=has_images,
            is_encrypted=is_encrypted,
        )
    finally:
        doc.close()
