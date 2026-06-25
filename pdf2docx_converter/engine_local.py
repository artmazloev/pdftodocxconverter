"""Local conversion engine: wraps pdf2docx (layout analysis -> editable DOCX).

This is the default, fully offline engine. It reconstructs the document as a
real Word flow (paragraphs, tables, images, styles) and only falls back to
positioned frames for layout that cannot be expressed otherwise — the "hybrid"
fidelity target.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pdf2docx import Converter

from .config import ConvertSettings

logger = logging.getLogger(__name__)


class ConversionError(RuntimeError):
    """Raised when pdf2docx fails to produce a DOCX."""


def convert_file(
    pdf_path: str | Path,
    docx_path: str | Path,
    settings: ConvertSettings | None = None,
) -> Path:
    """Convert a single PDF to DOCX. Returns the output path on success."""
    settings = settings or ConvertSettings()
    pdf_path = Path(pdf_path)
    docx_path = Path(docx_path)
    docx_path.parent.mkdir(parents=True, exist_ok=True)

    kwargs = settings.to_pdf2docx_kwargs()
    logger.info("Converting %s -> %s", pdf_path.name, docx_path.name)
    logger.debug("pdf2docx kwargs: %s", kwargs)

    cv = Converter(str(pdf_path))
    try:
        cv.convert(str(docx_path), **kwargs)
    except Exception as exc:  # pdf2docx raises a variety of low-level errors
        raise ConversionError(f"Failed to convert {pdf_path.name}: {exc}") from exc
    finally:
        cv.close()

    if not docx_path.exists() or docx_path.stat().st_size == 0:
        raise ConversionError(
            f"Conversion produced no output for {pdf_path.name}"
        )
    return docx_path
