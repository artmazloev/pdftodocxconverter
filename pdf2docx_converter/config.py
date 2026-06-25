"""Conversion settings.

The defaults aim at the "hybrid" fidelity target: keep text in a normal,
editable flow where possible, and fall back to absolutely-positioned frames
only for layout that cannot be expressed as plain paragraphs.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path

# Project-relative I/O folders (the script reads from INPUT_DIR, writes OUTPUT_DIR).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = PROJECT_ROOT / "inputs"
OUTPUT_DIR = PROJECT_ROOT / "outputs"


@dataclass
class ConvertSettings:
    """Tunable knobs passed down to the conversion engine.

    These map onto pdf2docx parsing options. They are deliberately conservative
    so the output stays editable; bump them per-document if fidelity suffers.
    """

    # Page range (0-based, end exclusive). None = whole document.
    start: int | None = None
    end: int | None = None

    # Multi-processing: number of CPU workers (0 = run in the main process,
    # which is the most stable choice when debugging in an IDE).
    cpu_count: int = 0

    # --- Layout reconstruction tuning (pdf2docx parse options) ---
    # Treat lines closer than this (relative to line height) as the same row.
    connected_border_tolerance: float = 0.5
    # Snap near-identical font sizes together to avoid noisy style churn.
    line_overlap_threshold: float = 0.9
    line_break_width_ratio: float = 0.5
    # When True, pdf2docx keeps blank lines to preserve vertical spacing.
    delete_end_line_hyphen: bool = False

    # Extra pdf2docx options merged verbatim into the parse() call.
    extra: dict = field(default_factory=dict)

    def to_pdf2docx_kwargs(self) -> dict:
        """Build the keyword args dict accepted by Converter.convert()."""
        kwargs: dict = {
            "multi_processing": self.cpu_count > 0,
            "cpu_count": self.cpu_count if self.cpu_count > 0 else None,
        }
        if self.start is not None:
            kwargs["start"] = self.start
        if self.end is not None:
            kwargs["end"] = self.end

        # pdf2docx accepts these as **kwargs forwarded to its layout parser.
        kwargs.update(
            {
                "connected_border_tolerance": self.connected_border_tolerance,
                "line_overlap_threshold": self.line_overlap_threshold,
                "line_break_width_ratio": self.line_break_width_ratio,
                "delete_end_line_hyphen": self.delete_end_line_hyphen,
            }
        )
        kwargs.update(self.extra)
        # Drop None values so pdf2docx uses its own defaults for them.
        return {k: v for k, v in kwargs.items() if v is not None}

    def as_dict(self) -> dict:
        return asdict(self)
