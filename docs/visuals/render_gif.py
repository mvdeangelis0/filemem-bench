#!/usr/bin/env python3
"""Capture a seamless-loop GIF from a docs/visuals/*.html board."""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOOP_S = 22.0
FPS = 4
VIEWPORT = {"width": 1020, "height": 980}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "board",
        nargs="?",
        default="fs-vs-rag",
        help="HTML basename without extension (default: fs-vs-rag)",
    )
    args = ap.parse_args()
    html = HERE / f"{args.board}.html"
    out = HERE / f"{args.board}.gif"

    try:
        from playwright.sync_api import sync_playwright
        from PIL import Image
    except ImportError as e:
        print("Need playwright + Pillow in the venv:", e, file=sys.stderr)
        return 1

    if not html.exists():
        print(f"missing {html}", file=sys.stderr)
        return 1

    n_frames = int(LOOP_S * FPS)
    delay_ms = int(1000 / FPS)
    frames: list[Image.Image] = []
    url = html.resolve().as_uri()
    print(f"capturing {n_frames} frames @ {FPS}fps from {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=1)
        page.goto(url, wait_until="load")
        page.wait_for_timeout(1400)
        page.reload(wait_until="load")
        page.wait_for_timeout(250)
        for i in range(n_frames):
            png = page.screenshot(type="png", full_page=True)
            im = Image.open(io.BytesIO(png)).convert("RGBA")
            frames.append(im.convert("P", palette=Image.ADAPTIVE, colors=96))
            page.wait_for_timeout(delay_ms)
            if (i + 1) % 8 == 0:
                print(f"  frame {i + 1}/{n_frames}")
        browser.close()

    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        duration=delay_ms,
        loop=0,
        optimize=True,
        disposal=2,
    )
    mb = out.stat().st_size / (1024 * 1024)
    print(f"wrote {out} ({mb:.2f} MiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
