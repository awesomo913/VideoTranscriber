"""Render docs/assets/social-preview.svg to docs/assets/social-preview.png (1280x640).

One-off tool, not part of the app. Needs Playwright and Google Chrome:

    uv run --no-project --with playwright python scripts/render_social_preview.py
"""
from __future__ import annotations

import os

from playwright.sync_api import sync_playwright

ASSETS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "assets"))
SVG = os.path.join(ASSETS, "social-preview.svg")
PNG = os.path.join(ASSETS, "social-preview.png")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 640})
        page.goto("file:///" + SVG.replace("\\", "/"))
        page.screenshot(path=PNG)
        browser.close()
    print(f"[render_social_preview] wrote {PNG}")


if __name__ == "__main__":
    main()
