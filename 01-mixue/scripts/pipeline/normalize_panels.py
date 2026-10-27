#!/usr/bin/env python3
"""Build an equal-width / equal-height preview set of panels.

This is a *preview* normalization: every panel is forced into the same pixel box
so the grid can be compared at a glance. The raw crops and the video frames are
left untouched (the video keeps the contain fit so nothing is distorted).

Modes:
  fill     squeeze the panel into the box (equal width and height, distortion)
  cover    fill the box and crop the overflow (no distortion, content loss)
  contain  fit inside the box and pad (no distortion, no loss)
"""
from pathlib import Path
import argparse
import json

from PIL import Image, ImageDraw, ImageFont

import panel_grid as pg

ROOT = Path(__file__).resolve().parent.parent.parent  # 01-mixue root
BUILD = ROOT / "build"


def font(size=16):
    for name in ("YuGothM.ttc", "meiryo.ttc", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def normalize(im, size, mode, bg=(255, 255, 255)):
    w, h = size
    if mode == "fill":
        return im.resize((w, h), Image.Resampling.LANCZOS)
    if mode == "cover":
        scale = max(w / im.width, h / im.height)
        rw, rh = max(1, round(im.width * scale)), max(1, round(im.height * scale))
        resized = im.resize((rw, rh), Image.Resampling.LANCZOS)
        left, top = (rw - w) // 2, (rh - h) // 2
        return resized.crop((left, top, left + w, top + h))
    canvas = Image.new("RGB", (w, h), bg)
    thumb = im.copy()
    thumb.thumbnail((w, h), Image.Resampling.LANCZOS)
    canvas.paste(thumb, ((w - thumb.width) // 2, (h - thumb.height) // 2))
    return canvas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=BUILD / "manifest.json")
    ap.add_argument("--panels-dir", type=Path, default=None,
                    help="use panel_*.png from this directory instead of a manifest")
    ap.add_argument("--out", type=Path, default=BUILD / "normalized")
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=360)
    ap.add_argument("--mode", choices=("fill", "cover", "contain"), default="fill")
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--title", default="normalized preview")
    a = ap.parse_args()

    if a.panels_dir:
        files = sorted(a.panels_dir.glob("panel_*.png"))
        labels = [f.stem for f in files]
        source = a.panels_dir.name
    else:
        if not a.manifest.exists():
            raise SystemExit(f"manifest not found: {a.manifest}")
        manifest = json.loads(a.manifest.read_text(encoding="utf-8"))
        # raw_path in manifest is relative to build/
        files = [BUILD / p["raw_path"] for p in manifest["panels"]]
        labels = [p["panel_id"] for p in manifest["panels"]]
        source = manifest.get("source_image", a.manifest.name)
        a.cols = int(manifest.get("grid", {}).get("cols", a.cols))
    if not files:
        raise SystemExit("no panels found")

    a.out.mkdir(parents=True, exist_ok=True)
    norm_dir = a.out / "panels"
    norm_dir.mkdir(parents=True, exist_ok=True)
    size = (a.width, a.height)
    for f, label in zip(files, labels):
        with Image.open(f) as im:
            out = normalize(im.convert("RGB"), size, a.mode)
            out.save(norm_dir / f"{label}.png")

    # Contact sheet: identical cells, so rows line up exactly.
    cols = a.cols
    rows = (len(files) + cols - 1) // cols
    pad, header, caption = 12, 46, 26
    cell_w, cell_h = a.width, a.height
    sheet = Image.new("RGB", (cols * cell_w + (cols + 1) * pad,
                              header + rows * (cell_h + caption + pad) + pad), "white")
    d = ImageDraw.Draw(sheet)
    d.text((pad, 14), f"{a.title}  {a.width}x{a.height}  mode={a.mode}", fill="black", font=font(20))
    for i, (f, label) in enumerate(zip(files, labels)):
        r, c = divmod(i, cols)
        x = pad + c * (cell_w + pad)
        y = header + r * (cell_h + caption + pad)
        with Image.open(norm_dir / f"{label}.png") as cell:
            sheet.paste(cell, (x, y))
        d.rectangle([x, y, x + cell_w - 1, y + cell_h - 1], outline=(180, 180, 180))
        d.text((x + 2, y + cell_h + 4), f"{label}  {a.width}x{a.height}", fill=(40, 40, 40), font=font(15))
    sheet_path = a.out / "contact-sheet.png"
    sheet.save(sheet_path)

    html = f"""<!doctype html>
<html lang="ja"><meta charset="utf-8"><title>{a.title}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 20px; }}
h1 {{ font-size: 18px; }} .note {{ font-size: 12px; color: #555; }}
.grid {{ display: grid; grid-template-columns: repeat({cols}, {a.width}px); gap: 10px; }}
figure {{ margin: 0; }}
img {{ width: {a.width}px; height: {a.height}px; display: block; border: 1px solid #ccc; }}
figcaption {{ font-size: 11px; color: #444; }}
</style>
<h1>{a.title} — {a.width}x{a.height} / mode={a.mode}</h1>
<p class="note">全コマを同じ幅・同じ高さに揃えたプレビュー。元の切り出しPNGと動画フレームは変更していません（mode=fill は縦横比を圧縮します）。<br>
source: {source}</p>
<p><a href="contact-sheet.png" target="_blank">contact sheet</a></p>
<div class="grid">
{''.join(f'<figure><a href="panels/{label}.png" target="_blank"><img src="panels/{label}.png"></a><figcaption>{label}</figcaption></figure>' for label in labels)}
</div>
</html>"""
    (a.out / "index.html").write_text(html, encoding="utf-8")

    print(f"normalized {len(files)} panels -> {a.out / 'index.html'} ({a.width}x{a.height}, {a.mode})")


if __name__ == "__main__":
    main()
