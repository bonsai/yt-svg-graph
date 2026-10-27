#!/usr/bin/env python3
"""Storyboard grid detection and frame fitting.

Single source of truth for:

- finding panel boundaries on a storyboard sheet (white gutters, measured per row)
- naive uniform fallback
- fitting a raw panel into a 16:9 video frame (contain = no content loss)

Used by inspect-panels.py, png2mov.py and the crop QA step so they all agree on
the same rectangles.
"""
from pathlib import Path

import numpy as np
from PIL import Image

WHITE_MIN = 248
WHITE_CHROMA = 8
GAP_MIN_RATIO = 0.90
GAP_MIN_RUN = 3


def white_mask(im):
    a = np.asarray(im.convert("RGB"))
    mn = a.min(axis=2)
    mx = a.max(axis=2)
    return (mn > WHITE_MIN) & ((mx - mn) < WHITE_CHROMA)


def white_profile(im):
    """Fraction of near-white pixels per row and per column."""
    mask = white_mask(im)
    return mask.mean(axis=1), mask.mean(axis=0)


def find_gaps(profile, threshold=GAP_MIN_RATIO, min_len=GAP_MIN_RUN):
    gaps, start = [], None
    for i, value in enumerate(profile):
        if value >= threshold and start is None:
            start = i
        elif value < threshold and start is not None:
            if i - start >= min_len:
                gaps.append((start, i - 1))
            start = None
    if start is not None and len(profile) - start >= min_len:
        gaps.append((start, len(profile) - 1))
    return gaps


def content_segments(length, gaps):
    """Content segments between gaps, dropping leading/trailing outer margins."""
    segments, cursor = [], 0
    for g0, g1 in gaps:
        if g0 > cursor:
            segments.append((cursor, g0 - 1))
        cursor = g1 + 1
    if cursor < length:
        segments.append((cursor, length - 1))
    if segments and segments[0] == (0, gaps[0][0] - 1) and gaps[0][0] == 0:
        segments.pop(0)
    if segments and segments[-1][1] == length - 1 and gaps[-1][1] == length - 1:
        segments.pop()
    return segments


def uniform_boxes(width, height, cols, rows):
    return [
        (
            round(c * width / cols),
            round(r * height / rows),
            round((c + 1) * width / cols),
            round((r + 1) * height / rows),
        )
        for r in range(rows)
        for c in range(cols)
    ]


def detect_boxes(im, cols, rows, threshold=GAP_MIN_RATIO, min_len=GAP_MIN_RUN):
    """Detect panel rectangles by white gutters.

    Column gutters are measured inside each row strip because storyboard rows are
    not always aligned. Returns a dict so callers can record why detection
    failed instead of silently falling back.
    """
    width, height = im.size
    row_profile, _ = white_profile(im)
    row_gaps = find_gaps(row_profile, threshold, min_len)
    y_segments = content_segments(height, row_gaps)
    strips, reasons = [], []
    for y0, y1 in y_segments:
        strip = im.crop((0, y0, width, y1 + 1))
        _, col_profile = white_profile(strip)
        col_gaps = find_gaps(col_profile, threshold, min_len)
        x_segments = content_segments(width, col_gaps)
        strips.append({"y": (y0, y1 + 1), "x": [(x0, x1 + 1) for x0, x1 in x_segments],
                       "col_gaps": col_gaps})
        if len(x_segments) != cols:
            reasons.append(f"row y={y0}-{y1}: expected {cols} columns, found {len(x_segments)}")

    if len(y_segments) != rows:
        reasons.append(f"expected {rows} row strips, found {len(y_segments)}")

    boxes = []
    if not reasons:
        for strip in strips:
            y0, y1 = strip["y"]
            for x0, x1 in strip["x"]:
                boxes.append((x0, y0, x1, y1))

    return {
        "ok": not reasons,
        "method": "detected" if not reasons else "uniform",
        "cols": cols,
        "rows": rows,
        "row_gaps": row_gaps,
        "strips": strips,
        "boxes": boxes,
        "reasons": reasons,
    }


def box_meta(box):
    x0, y0, x1, y1 = box
    return {
        "box": [x0, y0, x1, y1],
        "size": [x1 - x0, y1 - y0],
        "aspect": round((x1 - x0) / (y1 - y0), 4) if y1 > y0 else None,
    }


def fit_frame(panel, width, height, mode="contain", background=(255, 255, 255)):
    """Fit a raw panel into a fixed frame.

    contain: keep every source pixel, pad the rest (no content loss).
    cover:   fill the frame, cropping the overflow (content loss, recorded).
    """
    src_w, src_h = panel.size
    if src_w <= 0 or src_h <= 0:
        raise ValueError("empty panel")
    if mode == "stretch":
        frame = panel.resize((width, height), Image.Resampling.LANCZOS)
        return frame, {"scale": [width / src_w, height / src_h], "offset": [0, 0],
                       "cropped_px": 0, "padded_px": [0, 0], "distortion": True}

    scale = min(width / src_w, height / src_h) if mode == "contain" else max(width / src_w, height / src_h)
    new_w, new_h = max(1, round(src_w * scale)), max(1, round(src_h * scale))
    resized = panel.resize((new_w, new_h), Image.Resampling.LANCZOS)

    cropped_px = 0
    if mode == "cover":
        left = (new_w - width) // 2
        top = (new_h - height) // 2
        frame = resized.crop((left, top, left + width, top + height))
        cropped_px = (new_w - width) * height + (new_h - height) * width
        offset = [-left, -top]
    else:
        frame = Image.new("RGB", (width, height), background)
        left = (width - new_w) // 2
        top = (height - new_h) // 2
        frame.paste(resized, (left, top))
        offset = [left, top]

    pad_px = [max(0, width - new_w), max(0, height - new_h)]
    return frame, {
        "scale": round(scale, 6),
        "resized": [new_w, new_h],
        "offset": offset,
        "cropped_px": cropped_px,
        "padded_px": pad_px,
        "distortion": False,
    }


def file_sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


DEFAULT_SOURCE = Path(__file__).resolve().parent / "MIXUE世界展開ストーリーボード展開.png"
