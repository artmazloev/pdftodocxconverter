#!/usr/bin/env python3
"""Turn a VARIABLE font into static-instance @font-face CSS (base64-embedded).

Why
---
Headless Chrome's `Page.pdf()` embeds *variable* fonts as **Type3** glyph
programs with no font name. Downstream PDF→DOCX converters (Adobe included) then
guess a font per glyph → font patchwork + words glued together.

Using *static* instances instead makes Chrome embed named, subset TrueType
(Type0) fonts, and the text layer stays clean. This script instances a variable
font at the weights you actually use and prints a drop-in @font-face block
(same family name, one rule per weight) to paste into your HTML builder.

    python scripts/make_static_fontface.py Manrope[wght].ttf \
        --family Manrope --weights 400 500 600 700 800 > fontface.css
"""

from __future__ import annotations

import argparse
import base64
import io
import sys
from pathlib import Path


def _instance_b64(var_path: Path, weight: int) -> str:
    from fontTools import ttLib
    from fontTools.varLib import instancer

    font = ttLib.TTFont(var_path)
    # updateFontNames=True names the instance properly (e.g. "Manrope ExtraBold")
    # so PDF→DOCX converters recognise one coherent family per script.
    instancer.instantiateVariableFont(
        font, {"wght": weight}, inplace=True, updateFontNames=True
    )
    buf = io.BytesIO()
    font.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


def build_css(var_path: Path, family: str, weights: list[int]) -> str:
    blocks = []
    for w in weights:
        b64 = _instance_b64(var_path, w)
        blocks.append(
            f"@font-face {{\n"
            f"  font-family: '{family}';\n"
            f"  src: url(data:font/ttf;base64,{b64}) format('truetype');\n"
            f"  font-weight: {w}; font-style: normal; font-display: swap;\n"
            f"}}"
        )
    return "\n".join(blocks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Variable font -> static-instance @font-face CSS (base64)."
    )
    parser.add_argument("font", help="Path to the variable .ttf (with a wght axis).")
    parser.add_argument("--family", default="Manrope", help="CSS font-family name.")
    parser.add_argument("--weights", nargs="+", type=int,
                        default=[400, 500, 600, 700, 800],
                        help="Weights to instance (default: 400 500 600 700 800).")
    parser.add_argument("-o", "--out", help="Write CSS here (default: stdout).")
    args = parser.parse_args(argv)

    css = build_css(Path(args.font), args.family, args.weights)
    if args.out:
        Path(args.out).write_text(css, encoding="utf-8")
        print(f"OK: wrote {args.out} ({len(args.weights)} weights)", file=sys.stderr)
    else:
        print(css)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
