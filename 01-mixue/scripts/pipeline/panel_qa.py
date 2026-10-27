#!/usr/bin/env python3
"""Deterministic crop QA for storyboard panels.

Pixel-level boundary accuracy cannot be proven by a VLM, so this step checks the
things a machine can prove:

- all expected panels exist, are unique and match their declared size
- every crop stays inside the source image
- no crop straddles a detected white gutter (neighbour bleed / missing strip)
- crops do not overlap and stay adjacent to their gutters
- the video frame only pads (contain), never silently crops content
- the manifest still describes the current source image (sha256)

The VLM step (qa_vlm.py) judges content on top of this. A `fail` here stops the
render; `review` is allowed only when the caller opts in.
"""
from pathlib import Path
import argparse
import json
from datetime import datetime, timezone

from PIL import Image

import panel_grid as pg

ROOT = Path(__file__).resolve().parent.parent.parent  # 01-mixue root
BUILD = ROOT / "build"


def white_fraction(im, box):
    crop = im.crop(box)
    mask = pg.white_mask(crop)
    return float(mask.mean()) if mask.size else 1.0


def ring_white_fraction(im, box, px=2):
    """White fraction just *outside* the crop, ignoring sides on the image border.

    A correct box sits next to the white gutter, so the pixels immediately
    outside it are white. Panels on the outer edge of the sheet legitimately
    touch the source edge, so those sides say nothing about crop accuracy.
    """
    x0, y0, x1, y1 = box
    w, h = im.size
    sides = []
    if y0 > 0:
        sides.append((x0, max(0, y0 - px), x1, y0))
    if y1 < h:
        sides.append((x0, y1, x1, min(h, y1 + px)))
    if x0 > 0:
        sides.append((max(0, x0 - px), y0, x0, y1))
    if x1 < w:
        sides.append((x1, y0, min(w, x1 + px), y1))
    if not sides:
        return white_fraction(im, box)
    white = total = 0
    for rect in sides:
        mask = pg.white_mask(im.crop(rect))
        white += int(mask.sum())
        total += mask.size
    return white / total if total else 1.0


def intersects(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def gutter_rects(grid, width, height):
    rects = []
    cursor = 0
    for g0, g1 in grid["row_gaps"]:
        rects.append((0, g0, width, g1 + 1))
    for strip in grid["strips"]:
        y0, y1 = strip["y"]
        for g0, g1 in strip["col_gaps"]:
            rects.append((g0, y0, g1 + 1, y1))
    return rects


def area(box):
    return max(0, box[2] - box[0]) * max(0, box[3] - box[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", type=Path, default=pg.DEFAULT_SOURCE)
    ap.add_argument("--manifest", type=Path, default=BUILD / "manifest.json")
    ap.add_argument("--out", type=Path, default=BUILD / "qa.json")
    ap.add_argument("--max-aspect-spread", type=float, default=0.25,
                    help="review when max/min panel aspect exceeds this spread")
    ap.add_argument("--max-gutter-ratio", type=float, default=0.035,
                    help="review when a gap between neighbours is wider than this fraction of the source")
    a = ap.parse_args()

    if not a.image.exists():
        raise SystemExit(f"source image not found: {a.image}")
    if not a.manifest.exists():
        raise SystemExit(f"manifest not found: {a.manifest} (run png2mov.py --prepare-only)")

    im = Image.open(a.image).convert("RGB")
    src_w, src_h = im.size
    manifest = json.loads(a.manifest.read_text(encoding="utf-8"))
    panels = manifest.get("panels", [])
    cols = int(manifest.get("grid", {}).get("cols", 3))
    rows = int(manifest.get("grid", {}).get("rows", 3))
    expected = cols * rows

    checks, issues = [], []
    counts = {"pass": 0, "review": 0, "fail": 0}

    def add(level, code, message, panel_id=None):
        issue = {"level": level, "code": code, "message": message}
        if panel_id:
            issue["panel_id"] = panel_id
        issues.append(issue)

    # --- manifest level -----------------------------------------------------
    ids = [p.get("panel_id") for p in panels]
    expected_ids = {f"panel_{i:03d}" for i in range(expected)}
    if len(panels) != expected:
        add("fail", "panel_count", f"expected {expected} panels, manifest has {len(panels)}")
    if set(ids) != expected_ids or len(set(ids)) != len(ids):
        add("fail", "panel_ids", f"panel ids are not exactly {sorted(expected_ids)}")
    source_sha = pg.file_sha256(a.image)
    if manifest.get("source_sha256") and manifest["source_sha256"] != source_sha:
        add("fail", "stale_manifest", "manifest source_sha256 does not match the image")
    elif not manifest.get("source_sha256"):
        add("review", "missing_source_hash", "manifest has no source_sha256; staleness cannot be checked")

    # --- grid level ---------------------------------------------------------
    grid = pg.detect_boxes(im, cols, rows)
    gutters = gutter_rects(grid, src_w, src_h) if grid["ok"] else []
    method = manifest.get("grid", {}).get("method", "uniform")
    if not grid["ok"]:
        add("review", "grid_detect_failed",
            f"white-gutter detection failed: {'; '.join(grid['reasons'])}")
    if method == "detected" and not grid["ok"]:
        add("review", "declared_detected_but_failed",
            "manifest says detected grid but detection no longer succeeds")
    if method == "uniform" and grid["ok"]:
        add("review", "uniform_grid", "uniform split is used even though boundaries were detectable")

    # --- per panel ----------------------------------------------------------
    panel_boxes = [tuple(p.get("source_box", (0, 0, 0, 0))) for p in panels]
    aspects = []
    for p in panels:
        panel_id = p.get("panel_id", "?")
        box = tuple(p.get("source_box", (0, 0, 0, 0)))
        p_issues = []

        def fail(code, msg):
            p_issues.append({"level": "fail", "code": code, "message": msg})

        def review(code, msg):
            p_issues.append({"level": "review", "code": code, "message": msg})

        def ok(code, msg):
            p_issues.append({"level": "pass", "code": code, "message": msg})

        if len(box) != 4 or box[2] <= box[0] or box[3] <= box[1]:
            fail("invalid_box", f"invalid source_box {box}")
        else:
            if box[0] < 0 or box[1] < 0 or box[2] > src_w or box[3] > src_h:
                fail("out_of_bounds", f"box {box} exceeds source {src_w}x{src_h}")
            decl = p.get("source_size")
            if decl and list(decl) != [box[2] - box[0], box[3] - box[1]]:
                fail("size_mismatch", f"manifest size {decl} != box size {[box[2]-box[0], box[3]-box[1]]}")

            raw = p.get("raw_path")
            # raw_path in manifest is relative to build/
            raw_path = BUILD / raw if raw else None
            if not raw_path or not raw_path.exists():
                fail("missing_raw", f"raw panel missing: {raw}")
            else:
                with Image.open(raw_path) as raw_im:
                    if raw_im.size != (box[2] - box[0], box[3] - box[1]):
                        fail("raw_size", f"raw {raw_im.size} != box {box}")
                    elif pg.file_sha256(raw_path) != p.get("raw_sha256"):
                        review("raw_hash", "raw panel hash differs from manifest")

            for rect in gutters:
                if intersects(box, rect):
                    fail("gutter_crossing", f"crop {box} overlaps a white gutter {rect}")

            ring = ring_white_fraction(im, box)
            if ring < 0.35:
                review("edge_not_clean",
                       f"only {ring:.0%} of the 2px edge ring is white; content may be cut or bleed in")
            else:
                ok("edge_ring", f"{ring:.0%} white edge ring")

            aspect = (box[2] - box[0]) / (box[3] - box[1])
            aspects.append(aspect)

        display = p.get("display")
        if not display:
            review("missing_display", "display info missing (old manifest)")
        else:
            if display.get("cropped_px", 0) > 0:
                fail("content_cropped", f"{display['cropped_px']} px cropped from the panel")
            if display.get("distortion"):
                fail("distortion", "frame fit stretches the panel")
            frame = manifest.get("frame", {})
            if display.get("frame_size") and frame and display["frame_size"] != [frame.get("width"), frame.get("height")]:
                fail("frame_size", f"display frame {display['frame_size']} != manifest frame")

        level = "fail" if any(i["level"] == "fail" for i in p_issues) else (
            "review" if any(i["level"] == "review" for i in p_issues) else "pass")
        counts[level] += 1
        for i in p_issues:
            if i["level"] != "pass":
                add(i["level"], i["code"], i["message"], panel_id)
        checks.append({"panel_id": panel_id, "box": list(box), "verdict": level,
                       "checks": p_issues})

    # --- overlap / adjacency ------------------------------------------------
    for i in range(len(panel_boxes)):
        for j in range(i + 1, len(panel_boxes)):
            if intersects(panel_boxes[i], panel_boxes[j]):
                add("fail", "overlap",
                    f"{panels[i].get('panel_id')} overlaps {panels[j].get('panel_id')}")

    # --- aspect spread ------------------------------------------------------
    if aspects:
        spread = max(aspects) / min(aspects) - 1
        if spread > a.max_aspect_spread:
            add("review", "aspect_spread",
                f"panel aspect spread {spread:.0%} exceeds {a.max_aspect_spread:.0%}")

    overall = "fail" if any(i["level"] == "fail" for i in issues) else (
        "review" if any(i["level"] == "review" for i in issues) else "pass")

    # Preserve existing VLM data if present
    existing = {}
    if a.out.exists():
        try:
            existing = json.loads(a.out.read_text(encoding="utf-8"))
        except Exception:
            pass
    vlm_data = existing.get("vlm", {})

    report = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_image": a.image.name,
        "source_sha256": source_sha,
        "manifest": a.manifest.name,
        "manifest_sha256": pg.file_sha256(a.manifest),
        "grid": {"cols": cols, "rows": rows, "method": method,
                 "detected_ok": grid["ok"], "detection_reasons": grid["reasons"],
                 "row_gaps": grid["row_gaps"],
                 "strips": [{"y": s["y"], "col_gaps": s["col_gaps"]} for s in grid["strips"]]},
        "policy": {"content_trim": "forbid", "gutter_crossing": "fail",
                   "max_aspect_spread": a.max_aspect_spread},
        "counts": counts,
        "overall": overall,
        "panels": checks,
        "issues": issues,
    }
    if vlm_data:
        report["vlm"] = vlm_data
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"crop QA: {overall}  pass={counts['pass']} review={counts['review']} fail={counts['fail']}")
    for item in issues:
        if item["level"] != "pass":
            where = item.get("panel_id", "-")
            print(f"  {item['level'].upper():<6} {where:<10} {item['code']}: {item['message']}")
    print(f"-> {a.out}")
    raise SystemExit(0 if overall != "fail" else 1)


if __name__ == "__main__":
    main()
