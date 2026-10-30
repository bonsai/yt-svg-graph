#!/usr/bin/env python3
"""Render the HTML/SVG scene source to frames and assemble a narrated MP4."""
from pathlib import Path
import argparse
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

def run(cmd):
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run([str(x) for x in cmd], check=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", type=Path, default=ROOT / "index.html")
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "mixue.mp4")
    ap.add_argument("--fps", type=int, default=1, help="rendered still frames per second")
    ap.add_argument("--duration", type=int, default=120)
    a = ap.parse_args()
    frames = a.out.parent / "frames"
    a.out.parent.mkdir(parents=True, exist_ok=True)
    run([sys.executable, str(ROOT / "divide-img.py"), "--html", str(a.html),
         "--out", str(frames), "--fps", str(a.fps), "--duration", str(a.duration)])
    run([sys.executable, str(ROOT / "mux.py"), "--frames", str(frames),
         "--audio", str(a.out.parent / "narration.mp3"), "--out", str(a.out),
         "--fps", str(a.fps), "--duration", str(a.duration)])

if __name__ == "__main__":
    main()
