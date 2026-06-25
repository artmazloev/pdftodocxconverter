"""Prepare HTML for clean, deterministic PDF rendering (fonts).

Two problems this module fixes before the HTML is printed by headless Chrome:

1. **Variable fonts → Type3.** Chrome's `Page.pdf()` embeds *variable* fonts as
   Type3 glyph programs with no font name, so every downstream PDF→DOCX converter
   guesses a font per glyph → patchwork + glued words. Embedded variable
   `@font-face` rules are replaced by *static-instance* rules (one per used
   weight, properly named).

2. **Font loaded over the network (Google Fonts) / not embedded.** Some documents
   reference a family (e.g. `Manrope`) but only pull it from Google Fonts via a
   `<link>`, or rely on it being installed. Offline / `file://` that fails → the
   page renders in a fallback font and the whole design is wrong. For known
   **bundled** fonts we inject a local static `@font-face` and strip the Google
   Fonts links, so rendering is self-contained and deterministic.
"""

from __future__ import annotations

import base64
import binascii
import io
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Fonts we ship locally (OFL) and can inject when referenced but not embedded.
_ASSETS = Path(__file__).resolve().parent / "assets"
_BUNDLED_FONTS = {
    # normalized family name -> (variable ttf path, css family name to emit)
    "manrope": (_ASSETS / "Manrope-VariableFont_wght.ttf", "Manrope"),
}

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
# <link>/<style> @import that pull fonts from Google's CDN.
_GOOGLE_LINK_RE = re.compile(
    r"<link\b[^>]*(?:fonts\.googleapis\.com|fonts\.gstatic\.com)[^>]*>",
    re.IGNORECASE,
)

# Fallback weights if none can be detected in the document.
_DEFAULT_WEIGHTS = [400, 700]


@dataclass
class PrepReport:
    faces_seen: int = 0
    variable_faces: int = 0
    static_rules_emitted: int = 0
    families: list[str] = field(default_factory=list)
    weights: list[int] = field(default_factory=list)
    injected_families: list[str] = field(default_factory=list)
    google_links_removed: int = 0

    def summary(self) -> str:
        parts = []
        if self.variable_faces:
            fams = ", ".join(self.families) or "?"
            parts.append(
                f"{self.variable_faces} variable face(s) → "
                f"{self.static_rules_emitted} static @font-face [{fams}]"
            )
        if self.injected_families:
            parts.append(
                f"injected bundled font: {', '.join(self.injected_families)} "
                f"@ {self.weights}"
            )
        if self.google_links_removed:
            parts.append(f"removed {self.google_links_removed} Google-Fonts link(s)")
        return "; ".join(parts) or "no font changes needed (HTML unchanged)"


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


def _embedded_families(html: str) -> set[str]:
    """Family names that already have an embedded (data-URI) @font-face."""
    families: set[str] = set()
    for block in _FONT_FACE_RE.findall(html):
        if _DATA_URI_RE.search(block):
            fam = _FAMILY_RE.search(block)
            if fam:
                families.add(fam.group(1).strip().strip("'\"").lower())
    return families


def _referenced_families(html: str) -> set[str]:
    """Primary family of every `font-family:` declaration (first in each list)."""
    families: set[str] = set()
    for decl in re.findall(r"font-family\s*:\s*([^;}]+)", html, re.IGNORECASE):
        first = decl.split(",")[0].strip().strip("'\"")
        if first:
            families.add(first.lower())
    return families


def _inject_bundled(html: str, weights: list[int], report: PrepReport) -> str:
    """Inject local static @font-face for bundled families that aren't embedded."""
    embedded = _embedded_families(html)
    referenced = _referenced_families(html)

    blocks: list[str] = []
    for key, (path, css_family) in _BUNDLED_FONTS.items():
        if key not in referenced or key in embedded or not path.exists():
            continue
        font_bytes = path.read_bytes()
        for w in weights:
            b64 = _instance_b64(font_bytes, w)
            if b64:
                blocks.append(_static_block(css_family, w, b64))
        if blocks:
            report.injected_families.append(css_family)
            report.weights = weights

    if not blocks:
        return html

    style = "<style data-injected-fonts>\n" + "\n".join(blocks) + "\n</style>"
    # Insert just before </head> (fallback: prepend) so it overrides CDN faces.
    if re.search(r"</head>", html, re.IGNORECASE):
        return re.sub(r"</head>", style + "\n</head>", html, count=1,
                      flags=re.IGNORECASE)
    return style + html


# Override that disables stroke/halo on SVG text. Stroked (outlined) text is
# printed by Chrome as Type3, which converters split into per-glyph spaces
# ("Г р у з и ю"). Removing the stroke makes those labels normal Type0 text.
_NOSTROKE_STYLE = (
    "<style data-flatten-stroke>svg text{stroke:none!important;"
    "paint-order:normal!important}</style>"
)


def make_fonts_static(
    html: str,
    weights: list[int] | None = None,
    flatten_text_stroke: bool = False,
) -> tuple[str, PrepReport]:
    """Make fonts self-contained for deterministic rendering.

    - embedded variable `@font-face` → static instances (fixes Type3);
    - referenced-but-not-embedded bundled fonts (e.g. Manrope from Google Fonts)
      → injected as local static `@font-face`, with the Google Fonts links removed.
    - `flatten_text_stroke`: drop stroke/halo from SVG text so outlined labels
      (e.g. on a map) don't become Type3 and get split into per-glyph spaces.

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

    # Inject bundled fonts for families that are referenced but not embedded.
    new_html = _inject_bundled(new_html, weights, report)

    # Drop Google Fonts links so rendering is offline & deterministic (our
    # injected faces, or the document's own embedded faces, are authoritative).
    if report.injected_families:
        new_html, n = _GOOGLE_LINK_RE.subn("", new_html)
        report.google_links_removed = n

    if flatten_text_stroke:
        if re.search(r"</head>", new_html, re.IGNORECASE):
            new_html = re.sub(r"</head>", _NOSTROKE_STYLE + "</head>", new_html,
                              count=1, flags=re.IGNORECASE)
        else:
            new_html = _NOSTROKE_STYLE + new_html

    return new_html, report
