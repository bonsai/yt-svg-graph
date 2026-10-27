#!/usr/bin/env python3
"""
VLM-based panel crop quality assessment.

Reads panel-manifest.json and panel-crop-qa.json, sends each panel crop to
a local VLM (LM Studio) for semantic evaluation, writes panel-crop-vlm.json.

Verdict per panel: pass / review / fail
- cut: content appears truncated at edges
- bleed: content from adjacent panel visible
- completeness: panel tells a coherent visual story

Usage:
    python qa_vlm.py                    # process all panels
    python qa_vlm.py --panel panel_003  # single panel
    python qa_vlm.py --model tempura-qwen2.5-vl-3b  # override model
"""
import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

BUILD = Path(__file__).resolve().parent / "build"
MANIFEST = BUILD / "panel-manifest.json"
QA_FILE = BUILD / "panel-crop-qa.json"
VLM_FILE = BUILD / "panel-crop-vlm.json"
PANEL_DIR = BUILD / "png-panels"

LMSTUDIO_URL = "http://localhost:1234/v1/chat/completions"
DEFAULT_MODEL = "tempura-qwen2.5-vl-3b"

# ──────────────────────────────────────────────────────────────────────
# Prompt
# ──────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a precise visual QA judge for manga/comic panel extraction.
You will see a single panel cropped from a storyboard page.
Evaluate THREE criteria and return ONLY valid JSON.

Criteria:
1. cut (bool) — Does the panel appear to have CONTENT TRUNCATED at any edge?
   Look for: text cut off, characters cut at border, speech bubbles sliced,
   action lines interrupted, background cut unnaturally.
   A clean margin of background/whitespace around content means cut=false.

2. bleed (bool) — Is there VISIBLE CONTENT FROM AN ADJACENT PANEL leaking in?
   Look for: panel borders doubling, foreign speech bubbles, partial characters
   from neighbor, gutter artifacts, line art that continues from outside.
   Clean isolation means bleed=false.

3. completeness (bool) — Does the panel form a COHERENT VISUAL UNIT?
   A complete panel has: clear subject, readable action/emotion, self-contained
   composition. Incomplete: only a fragment (e.g., just a hand, half a face,
   empty background), or so cluttered/cropped the meaning is lost.

Return format (exactly):
{
  "cut": true|false,
  "bleed": true|false,
  "completeness": true|false,
  "reason": "concise Japanese explanation (≤80 chars)"
}"""

USER_PROMPT = """Evaluate this manga panel crop. Return ONLY the JSON."""


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def img_to_b64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def call_vlm(model: str, b64: str) -> dict:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": USER_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"}
                    }
                ]
            }
        ],
        "temperature": 0.0,
        "max_tokens": 200,
    }
    r = requests.post(LMSTUDIO_URL, json=payload, timeout=180)
    r.raise_for_status()
    data = r.json()
    content = data["choices"][0]["message"]["content"].strip()
    # Extract JSON from possible markdown fences
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content)


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", help="Single panel ID (e.g., panel_003)")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="LM Studio model ID")
    ap.add_argument("--force", action="store_true", help="Re-evaluate even if VLM file exists")
    args = ap.parse_args()

    if not MANIFEST.exists():
        sys.exit(f"Manifest not found: {MANIFEST}. Run png2mov.py --prepare-only first.")
    if not QA_FILE.exists():
        sys.exit(f"QA file not found: {QA_FILE}. Run png2mov.py --prepare-only first.")

    manifest = load_json(MANIFEST)
    qa = load_json(QA_FILE)
    panels = manifest.get("panels", [])

    # Load existing VLM results if any
    vlm_results = {}
    if VLM_FILE.exists() and not args.force:
        vlm_results = load_json(VLM_FILE).get("panels", {})

    # Filter panels to process
    if args.panel:
        panels = [p for p in panels if p["panel_id"] == args.panel]
        if not panels:
            sys.exit(f"Panel {args.panel} not in manifest")

    print(f"VLM QA: {len(panels)} panel(s) with model {args.model}")
    print(f"LM Studio: {LMSTUDIO_URL}")

    for i, panel in enumerate(panels, 1):
        pid = panel["panel_id"]
        crop_path = PANEL_DIR / f"{pid}.png"

        if not crop_path.exists():
            print(f"  [{i}/{len(panels)}] {pid}: crop missing, skip")
            vlm_results[pid] = {"cut": True, "bleed": True, "completeness": False,
                                "reason": "crop file missing", "error": "missing_file"}
            continue

        if pid in vlm_results and not args.force:
            print(f"  [{i}/{len(panels)}] {pid}: cached")
            continue

        print(f"  [{i}/{len(panels)}] {pid}: evaluating...", end=" ", flush=True)

        try:
            b64 = img_to_b64(crop_path)
            result = call_vlm(args.model, b64)

            # Normalize
            verdict = {
                "cut": bool(result.get("cut", True)),
                "bleed": bool(result.get("bleed", True)),
                "completeness": bool(result.get("completeness", False)),
                "reason": str(result.get("reason", "")).strip()[:120],
            }
            # Overall: pass only if all three good
            verdict["verdict"] = "pass" if (not verdict["cut"] and not verdict["bleed"] and verdict["completeness"]) else "review"
            if verdict["cut"] or verdict["bleed"]:
                verdict["verdict"] = "fail"

            vlm_results[pid] = verdict
            print(f"{verdict['verdict']} ({verdict['reason'][:50]})")
            # Incremental save
            save_json(VLM_FILE, {
                "model": args.model,
                "panels": vlm_results,
                "summary": {
                    "total": len(vlm_results),
                    "pass": sum(1 for v in vlm_results.values() if v.get("verdict") == "pass"),
                    "review": sum(1 for v in vlm_results.values() if v.get("verdict") == "review"),
                    "fail": sum(1 for v in vlm_results.values() if v.get("verdict") == "fail"),
                }
            })

        except Exception as e:
            print(f"ERROR: {e}")
            vlm_results[pid] = {"cut": True, "bleed": True, "completeness": False,
                                "reason": f"VLM error: {e}", "error": str(e), "verdict": "fail"}
            save_json(VLM_FILE, {
                "model": args.model,
                "panels": vlm_results,
                "summary": {
                    "total": len(vlm_results),
                    "pass": sum(1 for v in vlm_results.values() if v.get("verdict") == "pass"),
                    "review": sum(1 for v in vlm_results.values() if v.get("verdict") == "review"),
                    "fail": sum(1 for v in vlm_results.values() if v.get("verdict") == "fail"),
                }
            })

    # Merge with QA for summary
    qa_by_id = {p["panel_id"]: p for p in qa.get("panels", [])}
    out = {
        "model": args.model,
        "panels": vlm_results,
        "summary": {
            "total": len(vlm_results),
            "pass": sum(1 for v in vlm_results.values() if v.get("verdict") == "pass"),
            "review": sum(1 for v in vlm_results.values() if v.get("verdict") == "review"),
            "fail": sum(1 for v in vlm_results.values() if v.get("verdict") == "fail"),
        }
    }
    save_json(VLM_FILE, out)

    # Print summary
    s = out["summary"]
    print(f"\nVLM QA: pass={s['pass']} review={s['review']} fail={s['fail']}")
    print(f"→ {VLM_FILE}")

    # Cross-check with mechanical QA
    print("\nCross-check with mechanical QA:")
    for pid, v in vlm_results.items():
        mq = qa_by_id.get(pid, {})
        mq_verdict = mq.get("verdict", "?")
        vlm_verdict = v.get("verdict", "?")
        if mq_verdict != vlm_verdict:
            print(f"  [!] {pid}: mechanical={mq_verdict} VLM={vlm_verdict}  reason={v.get('reason')}")


if __name__ == "__main__":
    main()