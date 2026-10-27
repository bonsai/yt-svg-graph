#!/usr/bin/env python3
"""Inspect storyboard panel extraction by eye.

Writes two crop sets so the split can be checked:

  inspect/uniform/   - naive cols x rows equal split (previous behaviour)
  inspect/detected/  - split at detected white gutters (per-row column gutters)

Plus contact sheets and a self-contained HTML gallery with the crop rectangles
overlaid on the source image.
"""
from pathlib import Path
import argparse
import json

from PIL import Image, ImageDraw, ImageFont

import panel_grid as pg

ROOT = Path(__file__).resolve().parent.parent.parent  # 01-mixue root


def label_font(size=18):
    for name in ("YuGothM.ttc", "meiryo.ttc", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def contact_sheet(im, boxes, out, title, cols, cell_w=560, cell_h=380):
    rows = (len(boxes) + cols - 1) // cols
    pad, header = 16, 44
    sheet = Image.new("RGB", (cols * (cell_w + pad) + pad, header + rows * (cell_h + pad) + pad), "white")
    d = ImageDraw.Draw(sheet)
    font = label_font(16)
    small = label_font(13)
    d.text((pad, 12), title, fill="black", font=label_font(20))
    for i, box in enumerate(boxes):
        r, c = divmod(i, cols)
        x, y = pad + c * (cell_w + pad), header + r * (cell_h + pad)
        crop = im.crop(box)
        crop.thumbnail((cell_w, cell_h - 24), Image.Resampling.LANCZOS)
        sheet.paste(crop, (x + (cell_w - crop.width) // 2, y))
        d.rectangle([x, y, x + cell_w, y + cell_h], outline=(200, 200, 200))
        d.text((x + 4, y + cell_h - 20), f"panel_{i:03d}  box={box}", fill=(20, 20, 20), font=font)
        d.text((x + 4, y + cell_h - 4), f"crop {crop.width}x{crop.height}", fill=(110, 110, 110), font=small)
    sheet.save(out)
    return out


def overlay(im, boxes, color, width=4, labels=True):
    out = im.copy()
    d = ImageDraw.Draw(out)
    font = label_font(22)
    for i, (x0, y0, x1, y1) in enumerate(boxes):
        d.rectangle([x0, y0, x1 - 1, y1 - 1], outline=color, width=width)
        if labels:
            d.rectangle([x0, y0, x0 + 86, y0 + 26], fill=color)
            d.text((x0 + 4, y0 + 2), f"{i:02d}", fill="white", font=font)
    return out


def cells(boxes, prefix, cols):
    parts = []
    for i, box in enumerate(boxes):
        w, h = box[2] - box[0], box[3] - box[1]
        parts.append(
            f'<figure><a href="{prefix}/panel_{i:03d}.png" target="_blank">'
            f'<img src="{prefix}/panel_{i:03d}.png" alt="panel_{i:03d}"></a>'
            f'<figcaption>panel_{i:03d}<br><code>{box}</code><br>{w}x{h} '
            f'({w / h:.2f}:1)</figcaption></figure>'
        )
    return "\n".join(parts)


def write_gallery(im, uniform, grid, out_dir, cols):
    src_overlay = out_dir / "source-overlay.png"
    side = im.copy()
    d = ImageDraw.Draw(side)
    for g0, g1 in grid["row_gaps"]:
        d.rectangle([0, g0, im.width - 1, g1], fill=(255, 240, 240))
    for strip in grid["strips"]:
        for g0, g1 in strip["col_gaps"]:
            d.rectangle([g0, strip["y"][0], g1, strip["y"][1] - 1], fill=(240, 255, 240))
    side = Image.blend(im, side, 0.35)
    side = overlay(side, uniform, (220, 40, 40), 3, labels=False)
    side = overlay(side, grid["boxes"], (20, 150, 60), 3, labels=False)
    side.save(src_overlay)

    detected = grid["boxes"]
    detected_block = (
        f'<h2>detected（境界検出）</h2><div class="grid">{cells(detected, "detected", cols)}</div>'
        if grid["ok"] else
        f'<p class="note">境界検出に失敗: {grid["reasons"]}。等分割のみ表示。</p>'
    )
    html = f"""<!doctype html>
<html lang="ja"><meta charset="utf-8">
<title>Panel split inspection</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; color: #111; }}
h1 {{ font-size: 20px; }} h2 {{ font-size: 16px; margin-top: 32px; }}
.grid {{ display: grid; grid-template-columns: repeat({cols}, minmax(0,1fr)); gap: 12px; }}
figure {{ margin: 0; border: 1px solid #ddd; padding: 8px; background: #fafafa; }}
figure img {{ width: 100%; height: auto; display: block; background: #fff; }}
figcaption {{ font-size: 11px; color: #444; margin-top: 6px; line-height: 1.5; }}
code {{ font-size: 10px; }}
.legend span {{ display: inline-block; margin-right: 18px; }}
.sw {{ display: inline-block; width: 12px; height: 12px; vertical-align: middle; margin-right: 4px; }}
.note {{ background: #fff8e6; border-left: 4px solid #e0a000; padding: 10px 14px; font-size: 13px; }}
</style>
<h1>Panel split inspection</h1>
<p class="legend">
  <span><span class="sw" style="background:#dc2828"></span>uniform {cols}×{cols}</span>
  <span><span class="sw" style="background:#14963c"></span>detected gutters</span>
</p>
<p><a href="source-overlay.png" target="_blank"><img src="source-overlay.png" style="max-width:100%;border:1px solid #ddd"></a></p>
<p class="note">赤 = 等分割、緑 = 白ガター検出。重なっていない場合、等分割はコマ境界と一致していません。<br>
row gaps: {grid['row_gaps']}<br>
col gaps per row: {[s['col_gaps'] for s in grid['strips']]}</p>
<h2>uniform {cols}×{cols}（旧 png2mov.py 相当）</h2>
<div class="grid">{cells(uniform, 'uniform', cols)}</div>
{detected_block}
</html>"""
    (out_dir / "index.html").write_text(html, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", type=Path, default=pg.DEFAULT_SOURCE)
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "inspect")
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--rows", type=int, default=3)
    a = ap.parse_args()
    if not a.image.exists():
        raise SystemExit(f"image not found: {a.image}")

    im = Image.open(a.image).convert("RGB")
    w, h = im.size
    a.out.mkdir(parents=True, exist_ok=True)

    uniform = pg.uniform_boxes(w, h, a.cols, a.rows)
    grid = pg.detect_boxes(im, a.cols, a.rows)

    sets = {"uniform": uniform}
    if grid["ok"]:
        sets["detected"] = grid["boxes"]
    for name, boxes in sets.items():
        d = a.out / name
        d.mkdir(parents=True, exist_ok=True)
        for i, box in enumerate(boxes):
            im.crop(box).save(d / f"panel_{i:03d}.png")

    contact_sheet(im, uniform, a.out / "uniform-contact-sheet.png",
                  f"uniform {a.cols}x{a.rows}", a.cols)
    if grid["ok"]:
        contact_sheet(im, grid["boxes"], a.out / "detected-contact-sheet.png",
                      "detected gutters", a.cols)

    write_gallery(im, uniform, grid, a.out, a.cols)

    report = {
        "schema_version": "1.0",
        "source": str(a.image),
        "source_size": {"width": w, "height": h},
        "grid": {
            "ok": grid["ok"],
            "reasons": grid["reasons"],
            "row_gaps": grid["row_gaps"],
            "strips": [{"y": s["y"], "col_gaps": s["col_gaps"]} for s in grid["strips"]],
        },
        "grids": {
            name: [{"panel_id": f"panel_{i:03d}", "index": i, "row": i // a.cols,
                    "col": i % a.cols, **pg.box_meta(box)}
                   for i, box in enumerate(boxes)]
            for name, boxes in sets.items()
        },
        "uniform_matches_detected": (
            all(u == d for u, d in zip(uniform, grid["boxes"])) if grid["ok"] else None
        ),
        "uniform_delta": [
            [d - u for u, d in zip(ub, db)]
            for ub, db in zip(uniform, grid["boxes"])
        ] if grid["ok"] else [],
    }
    (a.out / "inspect.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"source: {a.image.name} {w}x{h}")
    print(f"row gaps={grid['row_gaps']}")
    for strip in grid["strips"]:
        print(f"  y={strip['y']} col_gaps={strip['col_gaps']} -> {len(strip['x'])} columns")
    print("detected grid:", "ok" if grid["ok"] else f"failed: {grid['reasons']}")
    if grid["ok"]:
        for i, (u, d) in enumerate(zip(uniform, grid["boxes"])):
            if u != d:
                print(f"  panel_{i:03d}: uniform={u} detected={d}")
    print(f"gallery: {a.out / 'index.html'}")


if __name__ == "__main__":
    main()
