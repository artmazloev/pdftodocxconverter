#!/usr/bin/env python3
"""Batch PDF -> DOCX converter.

Run from your IDE (Cursor) or the terminal. By default it converts every
PDF in ./inputs and writes the matching .docx into ./outputs.

    python convert.py                 # convert all PDFs in inputs/
    python convert.py report.pdf      # convert a single file from inputs/
    python convert.py --pages 0:5     # only the first 5 pages
    python convert.py --overwrite     # re-convert even if output exists

Only *digital* PDFs (with a real text layer) are supported for now; scanned
documents are detected and skipped with a warning.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from pdf2docx_converter.analyzer import analyze
from pdf2docx_converter.config import INPUT_DIR, OUTPUT_DIR, ConvertSettings
from pdf2docx_converter.engine_local import ConversionError, convert_file


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)-7s %(message)s",
    )


def _parse_pages(value: str | None) -> tuple[int | None, int | None]:
    """Parse a 'start:end' (0-based, end-exclusive) page spec."""
    if not value:
        return None, None
    if ":" not in value:
        raise argparse.ArgumentTypeError("--pages must look like START:END, e.g. 0:5")
    start_s, end_s = value.split(":", 1)
    start = int(start_s) if start_s else None
    end = int(end_s) if end_s else None
    return start, end


def _collect_inputs(name: str | None) -> list[Path]:
    """Return the list of PDFs to process."""
    if name:
        candidate = Path(name)
        if not candidate.is_absolute() and not candidate.exists():
            candidate = INPUT_DIR / name
        if not candidate.exists():
            raise FileNotFoundError(f"PDF not found: {name}")
        return [candidate]
    return sorted(INPUT_DIR.glob("*.pdf"))


def _convert_one(
    pdf: Path,
    settings: ConvertSettings,
    overwrite: bool,
    engine: str,
    postprocess: bool,
    font: str,
) -> bool:
    """Convert a single PDF. Returns True on success, False if skipped/failed."""
    log = logging.getLogger("convert")
    out_path = OUTPUT_DIR / f"{pdf.stem}.docx"

    if out_path.exists() and not overwrite:
        log.info("• skip %s (output exists, use --overwrite)", pdf.name)
        return False

    # Pre-flight: make sure this is a digital PDF we can handle.
    try:
        report = analyze(pdf)
    except Exception as exc:
        log.error("✗ %s — could not read PDF: %s", pdf.name, exc)
        return False

    # The cloud engine can handle scanned/low-text files (it has its own OCR);
    # the local engine cannot, so we only gate on these for the local path.
    if engine == "local":
        if report.likely_scanned:
            log.warning(
                "• skip %s — looks scanned (text on %d/%d pages). OCR is out of scope.",
                pdf.name, report.pages_with_text, report.page_count,
            )
            return False
        if not report.is_digital:
            log.warning(
                "• skip %s — little extractable text (%d chars). Likely not a digital PDF.",
                pdf.name, report.total_chars,
            )
            return False

    started = time.perf_counter()
    try:
        if engine == "adobe":
            from pdf2docx_converter.engine_adobe import (
                AdobeConfigError,
                AdobeConversionError,
                convert_file as adobe_convert,
            )
            try:
                adobe_convert(pdf, out_path)
            except (AdobeConfigError, AdobeConversionError) as exc:
                log.error("✗ %s — %s", pdf.name, exc)
                return False
        else:
            convert_file(pdf, out_path, settings)
    except ConversionError as exc:
        log.error("✗ %s — %s", pdf.name, exc)
        return False

    # Tidy fonts/whitespace. Never fail the conversion on a post-process error.
    if postprocess:
        try:
            from pdf2docx_converter.postprocess import normalize_docx
            stats = normalize_docx(out_path, target_font=font)
            log.info("  ↳ post-process: %s", stats.summary())
        except Exception as exc:  # noqa: BLE001 — best-effort cleanup
            log.warning("  ↳ post-process skipped for %s: %s", out_path.name, exc)

    elapsed = time.perf_counter() - started
    log.info("✓ %s -> outputs/%s  (%d pages, %.1fs)",
             pdf.name, out_path.name, report.page_count, elapsed)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert digital PDFs to editable DOCX (inputs/ -> outputs/).",
    )
    parser.add_argument("file", nargs="?", help="Single PDF (name in inputs/ or a path).")
    parser.add_argument("--pages", help="Page range START:END, 0-based, end-exclusive.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing DOCX.")
    parser.add_argument("--workers", type=int, default=0,
                        help="CPU workers (0 = single process, best for debugging).")
    parser.add_argument(
        "--engine", choices=["local", "adobe"], default="local",
        help="Conversion engine: 'local' (offline, pdf2docx) or 'adobe' "
             "(cloud, higher fidelity — UPLOADS the file to Adobe).",
    )
    parser.add_argument(
        "--font", default="Arial",
        help="Target font for post-processing (unifies guessed/junk fonts). "
             "Default: Arial.",
    )
    parser.add_argument(
        "--no-postprocess", action="store_true",
        help="Skip font/whitespace cleanup of the produced DOCX.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging.")
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)
    log = logging.getLogger("convert")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    INPUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        start, end = _parse_pages(args.pages)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))

    try:
        pdfs = _collect_inputs(args.file)
    except FileNotFoundError as exc:
        log.error("%s", exc)
        return 1

    if not pdfs:
        log.warning("No PDFs found in %s — drop some files there and re-run.", INPUT_DIR)
        return 0

    settings = ConvertSettings(start=start, end=end, cpu_count=args.workers)

    if args.engine == "adobe":
        log.warning("Engine: ADOBE — files will be uploaded to Adobe's cloud.")
    log.info("Found %d PDF(s) to process.", len(pdfs))
    succeeded = sum(
        _convert_one(
            pdf, settings, args.overwrite, args.engine,
            not args.no_postprocess, args.font,
        )
        for pdf in pdfs
    )
    log.info("Done: %d/%d converted.", succeeded, len(pdfs))

    # Non-zero exit if nothing succeeded while there was work to do.
    return 0 if succeeded or not pdfs else 1


if __name__ == "__main__":
    sys.exit(main())
