"""Post-processing for converted DOCX files — font normalization & cleanup.

Why this exists
---------------
When a PDF is built with Type3 / heavily-subset fonts (common in design tools and
web-to-PDF exports), the converter — including Adobe — cannot recover the real
font name, so it *guesses a font per glyph*. A single word ends up split across
many fonts (Arial Black + Tahoma + Comic Sans …), and most of those guesses are
fonts that aren't installed on a normal Mac/Windows, so Word substitutes them and
the text looks distorted.

This module rewrites the DOCX to use **one consistent font** for normal text
(keeping genuine symbol/dingbat fonts), and collapses the stray double-spaces that
the same kerning quirk produces. It also merges adjacent runs that become
identical, which makes the result cleaner to edit.

Run standalone on any DOCX:

    python -m pdf2docx_converter.postprocess outputs/file.docx
    python -m pdf2docx_converter.postprocess file.docx --font "Helvetica Neue"
"""

from __future__ import annotations

import logging
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

logger = logging.getLogger(__name__)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# Symbol/dingbat fonts whose glyphs are NOT interchangeable with a text font —
# left untouched so arrows/icons/emoji keep rendering.
SYMBOL_FONTS = {
    "Wingdings", "Wingdings 2", "Wingdings 3", "Webdings", "Symbol",
    "Segoe UI Emoji", "Segoe UI Symbol", "Segoe MDL2 Assets",
    "Apple Color Emoji", "Cambria Math",
}

# WordprocessingML parts that can carry run fonts / text.
_FONT_PARTS = ("word/document.xml", "word/styles.xml")
_PREFIX_PARTS = ("word/header", "word/footer")  # header1.xml, footer2.xml, …


def _q(tag: str) -> str:
    return f"{{{W}}}{tag}"


@dataclass
class CleanupStats:
    fonts_rewritten: int = 0
    spaces_collapsed: int = 0
    runs_merged: int = 0
    fonts_before: set[str] = field(default_factory=set)
    fonts_after: set[str] = field(default_factory=set)

    def summary(self) -> str:
        return (
            f"fonts unified ({len(self.fonts_before)}→{len(self.fonts_after)}), "
            f"{self.fonts_rewritten} font refs rewritten, "
            f"{self.spaces_collapsed} space runs collapsed, "
            f"{self.runs_merged} runs merged"
        )


def _target_parts(names: list[str]) -> list[str]:
    parts = [n for n in names if n in _FONT_PARTS]
    parts += [
        n for n in names
        if n.startswith(_PREFIX_PARTS) and n.endswith(".xml")
    ]
    return parts


def _normalize_rfonts(root, target: str, keep: set[str], stats: CleanupStats) -> None:
    """Point every text-font reference at `target` (keeping symbol fonts)."""
    for rfonts in root.iter(_q("rFonts")):
        for attr in ("ascii", "hAnsi", "cs", "eastAsia"):
            key = _q(attr)
            current = rfonts.get(key)
            if current:
                stats.fonts_before.add(current)
            if current and current not in keep and current != target:
                rfonts.set(key, target)
                stats.fonts_rewritten += 1
            if current:
                stats.fonts_after.add(rfonts.get(key))
        # Drop theme-font attrs so they don't re-introduce a different font.
        for attr in ("asciiTheme", "hAnsiTheme", "cstheme", "eastAsiaTheme"):
            if rfonts.get(_q(attr)) is not None:
                del rfonts.attrib[_q(attr)]


_SPACE_RE = re.compile(r" {2,}")
_SPACE_BEFORE_PUNCT_RE = re.compile(r" +([,.;:!?»)])")


def _collapse_spaces(root, stats: CleanupStats) -> None:
    """Collapse 2+ spaces to one and drop stray spaces before punctuation."""
    for t in root.iter(_q("t")):
        if not t.text:
            continue
        original = t.text
        fixed = _SPACE_RE.sub(" ", original)
        fixed = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", fixed)
        if fixed != original:
            stats.spaces_collapsed += original.count("  ")
            t.text = fixed
            # Preserve leading/trailing spaces Word would otherwise trim.
            if fixed != fixed.strip():
                t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")


def _rpr_signature(run) -> str | None:
    """Serialized run-properties (<w:rPr>) used to detect mergeable runs."""
    rpr = run.find(_q("rPr"))
    return etree.tostring(rpr) if rpr is not None else ""


def _merge_adjacent_runs(root, stats: CleanupStats) -> None:
    """Merge neighbouring runs that now share identical properties & simple text."""
    for parent in root.iter(_q("p")):
        prev = None
        prev_plain = False
        for run in list(parent.findall(_q("r"))):
            # Only merge "plain text" runs: exactly one <w:t>, no drawings/breaks.
            children = [c for c in run if c.tag != _q("rPr")]
            is_plain = len(children) == 1 and children[0].tag == _q("t")
            if (
                prev is not None
                and is_plain
                and prev_plain
                and _rpr_signature(run) == _rpr_signature(prev)
            ):
                prev_t = prev.find(_q("t"))
                cur_t = run.find(_q("t"))
                prev_t.text = (prev_t.text or "") + (cur_t.text or "")
                prev_t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                parent.remove(run)
                stats.runs_merged += 1
                continue
            prev = run
            prev_plain = is_plain


def normalize_docx(
    docx_path: str | Path,
    target_font: str = "Arial",
    keep_fonts: set[str] | None = None,
    normalize_fonts: bool = True,
    collapse_spaces: bool = True,
    merge_runs: bool = True,
) -> CleanupStats:
    """Clean up a DOCX in place. Returns stats describing what changed.

    ⚠️  Font normalization changes glyph metrics. In layout-faithful output
    (e.g. Adobe's, which positions text in absolute frames) this can make
    blocks overflow / shift. Use `normalize_fonts=False` to only tidy
    whitespace and preserve such layouts. For flow-based output (the local
    engine) font normalization is safe and helpful.
    """
    docx_path = Path(docx_path)
    keep = SYMBOL_FONTS | {target_font} | (keep_fonts or set())
    stats = CleanupStats()

    # Font normalization implies run-merging; without it, leave runs/structure
    # untouched so positioned layouts don't move.
    do_merge = merge_runs and normalize_fonts

    tmp_path = docx_path.with_suffix(docx_path.suffix + ".tmp")
    with zipfile.ZipFile(docx_path) as zin:
        names = zin.namelist()
        targets = set(_target_parts(names))
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename in targets:
                    root = etree.fromstring(data)
                    if normalize_fonts:
                        _normalize_rfonts(root, target_font, keep, stats)
                    if collapse_spaces:
                        _collapse_spaces(root, stats)
                    if do_merge:
                        _merge_adjacent_runs(root, stats)
                    data = etree.tostring(
                        root, xml_declaration=True, encoding="UTF-8", standalone=True
                    )
                zout.writestr(item, data)

    shutil.move(str(tmp_path), str(docx_path))
    logger.info("Post-process %s: %s", docx_path.name, stats.summary())
    return stats


def _main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Normalize fonts & whitespace in a converted DOCX.",
    )
    parser.add_argument("docx", help="Path to the .docx to clean (modified in place).")
    parser.add_argument("--font", default="Arial",
                        help="Target font for all normal text (default: Arial).")
    parser.add_argument("--keep", nargs="*", default=[],
                        help="Extra font names to preserve.")
    parser.add_argument("--no-normalize-fonts", action="store_true",
                        help="Do not touch fonts (safe for layout-faithful DOCX; "
                             "only tidies whitespace).")
    parser.add_argument("--no-collapse-spaces", action="store_true",
                        help="Do not collapse double spaces.")
    parser.add_argument("--no-merge-runs", action="store_true",
                        help="Do not merge adjacent identical runs.")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    stats = normalize_docx(
        args.docx,
        target_font=args.font,
        keep_fonts=set(args.keep),
        normalize_fonts=not args.no_normalize_fonts,
        collapse_spaces=not args.no_collapse_spaces,
        merge_runs=not args.no_merge_runs,
    )
    print(stats.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
