#!/usr/bin/env python3
"""Internal source router: storyboard PNG -> png2mov.py; HTML/SVG -> svg2mov.py."""
from pathlib import Path
import argparse
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
STORYBOARD = ROOT / "MIXUE世界展開ストーリーボード展開.png"
HTML_SOURCE = ROOT / "index.html"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=("auto", "png", "svg"), default="auto")
    ap.add_argument("--fps", type=int, default=1)
    ap.add_argument("--duration", type=int, default=120)
    a = ap.parse_args()
    source = a.source
    if source == "auto":
        source = "png" if STORYBOARD.exists() else "svg"
    if source == "png":
        if not STORYBOARD.exists():
            raise SystemExit(f"PNG source selected but not found: {STORYBOARD}")
        cmd = [sys.executable, str(ROOT / "png2mov.py")]
    else:
        if not HTML_SOURCE.exists():
            raise SystemExit(f"SVG/HTML source selected but not found: {HTML_SOURCE}")
        cmd = [sys.executable, str(ROOT / "svg2mov.py"), "--fps", str(a.fps), "--duration", str(a.duration)]
    print(f"Source route: {source}", flush=True)
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    main()
