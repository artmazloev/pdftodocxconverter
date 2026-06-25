#!/usr/bin/env python3
"""Render an HTML file to PDF with headless Chrome (Playwright).

Why this matters for this project
---------------------------------
Design documents are often built as HTML with web fonts (e.g. Manrope embedded
via @font-face) and then printed to PDF. Old engines like **wkhtmltopdf** turn
those web fonts into **Type3** glyph programs with no font name — which makes
every downstream PDF→DOCX converter (Adobe included) guess fonts per glyph,
producing font patchwork and glued-together words.

Headless **Chrome** instead embeds fonts as named, subset TrueType (Type0), and
keeps the text layer clean. So rendering the HTML here first gives a PDF that
converts to DOCX cleanly:

    python scripts/html_to_pdf.py design.html design.pdf
    python convert.py design.pdf --engine adobe      # clean DOCX

Local Mac setup:  pip install playwright && playwright install chromium
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# CSS @page rules in the source control real page size/margins, so we don't
# impose margins here; we only enable background graphics.
_PRINT_BACKGROUND = True


def _find_chrome() -> str | None:
    """Locate a Chromium/Chrome executable without forcing a download."""
    # 1) Explicit override.
    env = os.environ.get("CHROME_PATH")
    if env and Path(env).exists():
        return env

    # 2) Playwright browser cache (PLAYWRIGHT_BROWSERS_PATH or default).
    roots = []
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        roots.append(Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"]))
    roots.append(Path.home() / ".cache" / "ms-playwright")
    for root in roots:
        if root.exists():
            for pattern in ("chromium-*/chrome-linux/chrome",
                            "chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
                            "chromium-*/chrome-win/chrome.exe"):
                hits = sorted(root.glob(pattern))
                if hits:
                    return str(hits[-1])

    # 3) Common system installs (macOS / Linux).
    for cand in (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ):
        if Path(cand).exists():
            return cand
    return None


def render(html_path: str | Path, pdf_path: str | Path,
           chrome: str | None = None) -> Path:
    """Render `html_path` to `pdf_path` with headless Chrome."""
    from playwright.sync_api import sync_playwright

    html_path = Path(html_path).resolve()
    pdf_path = Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    if not html_path.exists():
        raise FileNotFoundError(f"HTML not found: {html_path}")

    chrome = chrome or _find_chrome()
    launch_kwargs = {"executable_path": chrome} if chrome else {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(**launch_kwargs)
        page = browser.new_page()
        page.goto(html_path.as_uri(), wait_until="networkidle")
        page.pdf(path=str(pdf_path), print_background=_PRINT_BACKGROUND,
                 prefer_css_page_size=True)
        browser.close()
    return pdf_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HTML -> PDF via headless Chrome.")
    parser.add_argument("html", help="Input HTML file.")
    parser.add_argument("pdf", nargs="?", help="Output PDF (default: same name).")
    parser.add_argument("--chrome", help="Path to a Chrome/Chromium executable.")
    args = parser.parse_args(argv)

    out = args.pdf or str(Path(args.html).with_suffix(".pdf"))
    try:
        result = render(args.html, out, args.chrome)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        if "executable" in str(exc).lower() or "playwright" in str(exc).lower():
            print("Hint: pip install playwright && playwright install chromium",
                  file=sys.stderr)
        return 1
    print(f"OK: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
