"""Prepare HTML for clean PDF rendering — make embedded variable fonts static.

Root cause this addresses
-------------------------
Headless Chrome's `Page.pdf()` embeds *variable* fonts as **Type3** glyph
programs with no font name. Every downstream PDF→DOCX converter (Adobe included)
then guesses a font per glyph → font patchwork + glued-together words.

This module rewrites an HTML document's embedded `@font-face` rules: any rule
whose `src: url(data:font/...;base64,…)` is a *variable* font is replaced by
several *static-instance* `@font-face` rules (same family, one per used weight).
Chrome then embeds named subset TrueType (Type0) fonts and the text stays clean.

Static (non-variable) embedded fonts and external/URL fonts are left untouched.
"""

from __future__ import annotations

import base64
import binascii
import io
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# A whole @font-face block. base64 data URIs contain no '}', so [^}]* is safe.
_FONT_FACE_RE = re.compile(r"@font-face\s*\{[^}]*\}", re.IGNORECASE)
_FAMILY_RE = re.compile(r"font-family\s*:\s*['\"]?([^;'\"}]+)", re.IGNORECASE)
_DATA_URI_RE = re.compile(
    r"url\(\s*['\"]?data:[^;,]*;base64,([A-Za-z0-9+/=\s]+?)['\"]?\s*\)",
    re.IGNORECASE,
)
# font-weight values used across the document (numeric or keyword).
_WEIGHT_USE_RE = re.compile(
    r"font-weight\s*:\s*(\d{2,3}|bold|bolder|normal|lighter)", re.IGNORECASE
)
_KEYWORD_WEIGHTS = {"normal": 400, "bold": 700, "bolder": 700, "lighter": 300}

# Fallback weights if none can be detected in the document.
_DEFAULT_WEIGHTS = [400, 700]


@dataclass
class PrepReport:
    faces_seen: int = 0
    variable_faces: int = 0
    static_rules_emitted: int = 0
    families: list[str] = field(default_factory=list)
    weights: list[int] = field(default_factory=list)

    def summary(self) -> str:
        if not self.variable_faces:
            return "no variable fonts found (HTML unchanged)"
        fams = ", ".join(self.families) or "?"
        return (
            f"{self.variable_faces} variable face(s) → "
            f"{self.static_rules_emitted} static @font-face "
            f"[{fams} @ {self.weights}]"
        )


def _used_weights(html: str) -> list[int]:
    """Collect font-weights actually used in the document."""
    found: set[int] = set()
    for raw in _WEIGHT_USE_RE.findall(html):
        token = raw.lower()
        if token.isdigit():
            found.add(int(token))
        elif token in _KEYWORD_WEIGHTS:
            found.add(_KEYWORD_WEIGHTS[token])
    # Drop weights that only appear inside @font-face range declarations is not
    # needed — instancing a couple of extra weights is harmless.
    return sorted(found) or list(_DEFAULT_WEIGHTS)


def _is_variable(font_bytes: bytes) -> bool:
    from fontTools.ttLib import TTFont

    try:
        font = TTFont(io.BytesIO(font_bytes), lazy=True)
        return "fvar" in font
    except Exception:  # noqa: BLE001 — not a parseable font; treat as static
        return False


def _instance_b64(font_bytes: bytes, weight: int) -> str | None:
    """Return base64 of a static instance at `weight`, clamped to the axis."""
    from fontTools import ttLib
    from fontTools.varLib import instancer

    try:
        font = ttLib.TTFont(io.BytesIO(font_bytes))
        axes = {a.axisTag: (a.minValue, a.maxValue) for a in font["fvar"].axes}
        w = weight
        if "wght" in axes:
            lo, hi = axes["wght"]
            w = max(lo, min(hi, weight))
        # updateFontNames=True renames the instance properly (e.g. "Manrope
        # ExtraBold"), so converters like Adobe recognise a single coherent
        # family instead of substituting different fonts per script.
        instancer.instantiateVariableFont(
            font, {"wght": w}, inplace=True, updateFontNames=True
        )
        buf = io.BytesIO()
        font.save(buf)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not instance variable font at %s: %s", weight, exc)
        return None


def _static_block(family: str, weight: int, b64: str) -> str:
    return (
        "@font-face {"
        f"font-family:'{family}';"
        f"src:url(data:font/ttf;base64,{b64}) format('truetype');"
        f"font-weight:{weight};font-style:normal;font-display:swap;"
        "}"
    )


def make_fonts_static(html: str, weights: list[int] | None = None) -> tuple[str, PrepReport]:
    """Replace variable @font-face rules with static-instance rules.

    Returns (new_html, report).
    """
    report = PrepReport()
    weights = weights or _used_weights(html)

    def repl(match: re.Match) -> str:
        block = match.group(0)
        report.faces_seen += 1
        data = _DATA_URI_RE.search(block)
        if not data:
            return block  # external/URL font — leave as is
        try:
            font_bytes = base64.b64decode("".join(data.group(1).split()))
        except (binascii.Error, ValueError):
            return block
        if not _is_variable(font_bytes):
            return block  # already static

        fam_m = _FAMILY_RE.search(block)
        family = fam_m.group(1).strip() if fam_m else "EmbeddedFont"

        blocks = []
        for w in weights:
            b64 = _instance_b64(font_bytes, w)
            if b64:
                blocks.append(_static_block(family, w, b64))
        if not blocks:
            return block  # instancing failed entirely — keep original

        report.variable_faces += 1
        report.static_rules_emitted += len(blocks)
        if family not in report.families:
            report.families.append(family)
        report.weights = weights
        return "\n".join(blocks)

    new_html = _FONT_FACE_RE.sub(repl, html)
    return new_html, report
