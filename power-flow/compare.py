#!/usr/bin/env python3
"""
Compare power-flow.html (standalone) vs HA Lovelace card.

First-time setup — save your HA browser session:
  python3 compare.py --save-session

  A browser window opens. Log in to HA, wait for the dashboard to load,
  then press ENTER in this terminal. The session is saved to ha_session.json.

Normal use (headless, no interaction needed):
  python3 compare.py

Output files in ~/myapp/tmp/power-flow/:
  standalone.png   our page
  ha.png           HA Lovelace card
  compare.png      side-by-side + pixel diff
"""

import argparse
import io
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from PIL import Image, ImageChops, ImageDraw

OUT          = Path(__file__).parent
SESSION_FILE = OUT / "ha_session.json"

STANDALONE_URL = "http://witw31.myqnapcloud.com:52581/local/views/power-flow/"
HA_URL         = "http://witw31.myqnapcloud.com:52581/lovelace-test/11"


# ── helpers ───────────────────────────────────────────────────────────────────

def wait_for_card(page, timeout=25000):
    try:
        page.wait_for_selector("power-flow-card-plus", state="visible", timeout=timeout)
        page.wait_for_timeout(3000)
    except Exception as e:
        print(f"  wait_for_card: {e}")


def crop_card(page, selector="power-flow-card-plus"):
    el = page.query_selector(selector)
    if el is None:
        el = page.query_selector(f"hui-card {selector}")
    if el is None:
        print(f"  WARNING: '{selector}' not found — full-page screenshot")
        return page.screenshot(full_page=False)
    box = el.bounding_box()
    if not box:
        return page.screenshot(full_page=False)
    pad = 12
    return page.screenshot(clip={
        "x":      max(0, box["x"] - pad),
        "y":      max(0, box["y"] - pad),
        "width":  box["width"]  + pad * 2,
        "height": box["height"] + pad * 2,
    })


def compare_images(img_a, img_b, label_a="standalone", label_b="HA Lovelace"):
    h = max(img_a.height, img_b.height)

    def fit_h(img, h):
        r = h / img.height
        return img.resize((int(img.width * r), h), Image.LANCZOS)

    a    = fit_h(img_a, h)
    b    = fit_h(img_b, h)
    diff = ImageChops.difference(
        a.convert("RGB"),
        b.resize((a.width, h), Image.LANCZOS).convert("RGB")
    )

    gap, hdr = 6, 24
    canvas = Image.new("RGB", (a.width + gap + b.width + gap + a.width, h + hdr), (30, 30, 30))
    canvas.paste(a, (0, hdr))
    canvas.paste(b, (a.width + gap, hdr))
    canvas.paste(diff, (a.width + gap + b.width + gap, hdr))

    draw = ImageDraw.Draw(canvas)
    draw.text((4, 4),                              label_a,      fill=(180, 210, 255))
    draw.text((a.width + gap + 4, 4),              label_b,      fill=(180, 255, 180))
    draw.text((a.width + gap + b.width + gap + 4, 4), "diff",    fill=(255, 180, 180))
    return canvas


# ── save-session mode ─────────────────────────────────────────────────────────

def save_session(pw):
    print("Opening browser — log in to HA, wait for the dashboard, then press ENTER here.")
    browser = pw.chromium.launch(headless=False, args=["--start-maximized"])
    ctx = browser.new_context(viewport=None, no_viewport=True)
    page = ctx.new_page()
    page.goto(HA_URL)

    input("\n>>> Dashboard loaded? Press ENTER to save session and close browser: ")

    ctx.storage_state(path=str(SESSION_FILE))
    print(f"Session saved to {SESSION_FILE}")
    browser.close()


# ── screenshot mode ───────────────────────────────────────────────────────────

def take_screenshots(pw):
    if not SESSION_FILE.exists():
        print(f"No session file found. Run:  python3 compare.py --save-session")
        sys.exit(1)

    browser = pw.chromium.launch(headless=True)

    # standalone — no auth needed
    print("Loading standalone page …")
    ctx1  = browser.new_context(viewport={"width": 1280, "height": 800})
    page1 = ctx1.new_page()
    page1.goto(STANDALONE_URL, wait_until="networkidle", timeout=30000)
    wait_for_card(page1)
    shot_s = crop_card(page1)
    print("  done")
    ctx1.close()

    # HA — restore saved session
    print("Loading HA Lovelace page …")
    ctx2  = browser.new_context(viewport={"width": 1280, "height": 800},
                                 storage_state=str(SESSION_FILE))
    page2 = ctx2.new_page()

    # Log any console errors to help debug
    page2.on("console", lambda m: print(f"  [browser] {m.type}: {m.text}") if m.type == "error" else None)

    page2.goto(HA_URL, wait_until="networkidle", timeout=40000)
    wait_for_card(page2)
    shot_ha = crop_card(page2)
    # Refresh session so it doesn't expire
    ctx2.storage_state(path=str(SESSION_FILE))
    print("  done")
    ctx2.close()

    browser.close()
    return shot_s, shot_ha


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save-session", action="store_true",
                    help="Open browser, log in to HA, save session for headless use")
    args = ap.parse_args()

    with sync_playwright() as pw:
        if args.save_session:
            save_session(pw)
            return

        shot_s, shot_ha = take_screenshots(pw)

    img_s  = Image.open(io.BytesIO(shot_s))
    img_ha = Image.open(io.BytesIO(shot_ha))

    p_s   = OUT / "standalone.png"
    p_ha  = OUT / "ha.png"
    p_cmp = OUT / "compare.png"

    img_s.save(p_s)
    img_ha.save(p_ha)
    print(f"Saved {p_s}  ({img_s.width}×{img_s.height})")
    print(f"Saved {p_ha}  ({img_ha.width}×{img_ha.height})")

    cmp = compare_images(img_s, img_ha)
    cmp.save(p_cmp)
    print(f"Saved {p_cmp}  ({cmp.width}×{cmp.height})")


if __name__ == "__main__":
    main()
