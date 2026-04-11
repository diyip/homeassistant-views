#!/usr/bin/env python3
"""
Playwright-based visual comparison utilities for standalone HA view pages.

Purpose:
    Capture screenshots of the standalone page and the live HA reference card,
    then produce a side-by-side comparison image with a pixel diff column.

Responsibilities:
    - Launch headless Chromium to screenshot both the standalone and HA pages
    - Crop screenshots to the target card element
    - Compose a labelled side-by-side comparison with pixel diff
    - Save and restore the HA browser session to avoid repeated logins
    - Expose a single run() entry point consumed by each view's compare.py

Key assumptions:
    - playwright and pillow must be installed locally (not in the HA container)
    - Standalone pages are accessible without authentication
    - HA pages require a saved browser session (run --save-session once to create it)
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright
from PIL import Image, ImageChops, ImageDraw

_VIEWPORT        = {"width": 1280, "height": 800}
_WAIT_TIMEOUT_MS = 25_000
_LOAD_TIMEOUT_MS = 40_000
_SETTLE_MS       = 3_000


def _wait_for_card(page: Page, selector: str) -> None:
    try:
        page.wait_for_selector(selector, state="visible", timeout=_WAIT_TIMEOUT_MS)
        page.wait_for_timeout(_SETTLE_MS)
    except Exception as exc:
        print(f"  wait_for_card '{selector}': {exc}")


def _crop_card(page: Page, selector: str, pad: int = 12) -> bytes:
    el = page.query_selector(selector) or page.query_selector(f"hui-card {selector}")
    if el is None:
        print(f"  WARNING: '{selector}' not found — using full-page screenshot")
        return page.screenshot(full_page=False)
    box = el.bounding_box()
    if not box:
        return page.screenshot(full_page=False)
    return page.screenshot(clip={
        "x":      max(0, box["x"] - pad),
        "y":      max(0, box["y"] - pad),
        "width":  box["width"]  + pad * 2,
        "height": box["height"] + pad * 2,
    })


def _make_comparison(img_a: Image.Image, img_b: Image.Image,
                     label_a: str, label_b: str) -> Image.Image:
    h = max(img_a.height, img_b.height)

    def scale(img: Image.Image) -> Image.Image:
        r = h / img.height
        return img.resize((int(img.width * r), h), Image.LANCZOS)

    a    = scale(img_a)
    b    = scale(img_b)
    diff = ImageChops.difference(
        a.convert("RGB"),
        b.resize((a.width, h), Image.LANCZOS).convert("RGB"),
    )
    gap, hdr = 6, 24
    canvas = Image.new("RGB", (a.width + gap + b.width + gap + a.width, h + hdr), (30, 30, 30))
    canvas.paste(a,    (0, hdr))
    canvas.paste(b,    (a.width + gap, hdr))
    canvas.paste(diff, (a.width + gap + b.width + gap, hdr))

    draw = ImageDraw.Draw(canvas)
    draw.text((4, 4),                                   label_a, fill=(180, 210, 255))
    draw.text((a.width + gap + 4, 4),                   label_b, fill=(180, 255, 180))
    draw.text((a.width + gap + b.width + gap + 4, 4), "diff",    fill=(255, 180, 180))
    return canvas


def _save_session(pw, ha_url: str, session_file: Path) -> None:
    print("Opening browser — log in to HA, wait for the dashboard, then press ENTER here.")
    browser = pw.chromium.launch(headless=False, args=["--start-maximized"])
    ctx  = browser.new_context(viewport=None, no_viewport=True)
    ctx.new_page().goto(ha_url)
    input("\n>>> Dashboard loaded? Press ENTER to save session and close browser: ")
    ctx.storage_state(path=str(session_file))
    print(f"Session saved to {session_file}")
    browser.close()


def _take_screenshots(pw, standalone_url: str, ha_url: str, session_file: Path,
                      standalone_selector: str | None,
                      ha_selector: str) -> tuple[bytes, bytes]:
    browser = pw.chromium.launch(headless=True)

    print("Loading standalone page …")
    ctx1  = browser.new_context(viewport=_VIEWPORT)
    page1 = ctx1.new_page()
    page1.goto(standalone_url, wait_until="networkidle", timeout=_LOAD_TIMEOUT_MS)
    page1.wait_for_timeout(_SETTLE_MS)
    shot_s = _crop_card(page1, standalone_selector) if standalone_selector else page1.screenshot()
    print("  done")
    ctx1.close()

    print("Loading HA page …")
    ctx2  = browser.new_context(viewport=_VIEWPORT, storage_state=str(session_file))
    page2 = ctx2.new_page()
    page2.on("console", lambda m: print(f"  [browser] {m.text}") if m.type == "error" else None)
    page2.goto(ha_url, wait_until="networkidle", timeout=_LOAD_TIMEOUT_MS)
    _wait_for_card(page2, ha_selector)
    shot_ha = _crop_card(page2, ha_selector)
    ctx2.storage_state(path=str(session_file))
    print("  done")
    ctx2.close()

    browser.close()
    return shot_s, shot_ha


def run(
    *,
    standalone_url: str,
    ha_url: str,
    session_file: Path,
    ha_selector: str,
    ha_label: str = "HA",
    standalone_selector: str | None = None,
    out_dir: Path | None = None,
) -> None:
    """Entry point for view-specific compare scripts.

    Args:
        standalone_url:      URL of the standalone view (no auth required)
        ha_url:              URL of the HA page containing the reference card
        session_file:        Path to the saved Playwright browser session file
        ha_selector:         CSS selector for the HA card element to crop
        ha_label:            Label for the HA screenshot in the comparison image
        standalone_selector: CSS selector to crop on the standalone page;
                             None captures the full viewport
        out_dir:             Directory for output images; defaults to session_file.parent
    """
    if out_dir is None:
        out_dir = session_file.parent

    ap = argparse.ArgumentParser()
    ap.add_argument("--save-session", action="store_true",
                    help="Open browser, log in to HA, and save session for headless use")
    args = ap.parse_args()

    with sync_playwright() as pw:
        if args.save_session:
            _save_session(pw, ha_url, session_file)
            return

        if not session_file.exists():
            print("No session file found. Run:  python3 compare.py --save-session")
            sys.exit(1)

        shot_s, shot_ha = _take_screenshots(
            pw, standalone_url, ha_url, session_file, standalone_selector, ha_selector
        )

    img_s  = Image.open(io.BytesIO(shot_s))
    img_ha = Image.open(io.BytesIO(shot_ha))

    p_s   = out_dir / "standalone.png"
    p_ha  = out_dir / "ha.png"
    p_cmp = out_dir / "compare.png"

    img_s.save(p_s)
    img_ha.save(p_ha)
    print(f"Saved {p_s}  ({img_s.width}×{img_s.height})")
    print(f"Saved {p_ha}  ({img_ha.width}×{img_ha.height})")

    cmp = _make_comparison(img_s, img_ha, label_a="standalone", label_b=ha_label)
    cmp.save(p_cmp)
    print(f"Saved {p_cmp}  ({cmp.width}×{cmp.height})")
