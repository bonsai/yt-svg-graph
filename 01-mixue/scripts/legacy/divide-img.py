#!/usr/bin/env python3
"""Capture a 16:9 HTML scene preview at fixed time intervals using Playwright."""
from pathlib import Path
import argparse, json
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--html', type=Path, default=ROOT / 'index.html')
    ap.add_argument('--out', type=Path, default=ROOT / 'build' / 'frames')
    ap.add_argument('--fps', type=int, default=1, help='capture frames per second')
    ap.add_argument('--duration', type=int, default=120)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width":1280,"height":720}, device_scale_factor=1)
        page.goto(args.html.resolve().as_uri(), wait_until='load')
        for frame in range(args.duration * args.fps):
            seconds = frame / args.fps
            page.evaluate('(t) => { window.__setVideoTime ? window.__setVideoTime(t) : null; const r=document.getElementById("scrub"); r.value=t; r.dispatchEvent(new Event("input")); }', seconds)
            page.screenshot(path=str(args.out / f'frame_{frame:06d}.png'))
        browser.close()
    print(f'Wrote frames to {args.out}')

if __name__ == '__main__': main()
