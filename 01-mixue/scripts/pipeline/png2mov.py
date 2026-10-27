#!/usr/bin/env python3
"""Extract storyboard panels and mux them against measured narration timing.

Simplified flat build/ structure:
  build/
    video/<name>.mp4
    audio/narration.wav, narration.mp3
    panels/panel_XXX.png       # raw crops for QA/VLM
    frames/panel_XXX.png       # 16:9 display frames (contain)
    manifest.json              # panels + scene timing + mapping
    qa.json                    # mechanical QA + VLM verdict
    timing.json                # measured audio timing
    mux-report.json            # duration verification
    tts/cache.json
    tts/voice/voice_XX.mp3/.wav
    normalized/panel_XXX.png   # equal W/H preview
    inspect/                   # comparison galleries
"""
from pathlib import Path
import argparse
import json
import subprocess
import sys

from PIL import Image

import panel_grid as pg

ROOT = Path(__file__).resolve().parent.parent.parent  # 01-mixue root
BUILD = ROOT / "build"


def run(cmd):
    cmd = [str(x) for x in cmd]
    if cmd and cmd[0] == "ffmpeg":
        cmd = [cmd[0], "-hide_banner", "-loglevel", "error", *cmd[1:]]
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def probe_duration(path, stream):
    cmd = ["ffprobe", "-v", "error", "-select_streams", stream,
           "-show_entries", "stream=duration", "-of", "default=nw=1:nk=1", str(path)]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()
    try:
        return float(out.splitlines()[0])
    except (ValueError, IndexError):
        return None


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", type=Path, default=ROOT / "assets" / "storyboard.png")
    ap.add_argument("--script", type=Path, default=ROOT / "config" / "tts.json")
    ap.add_argument("--timing", type=Path, default=BUILD / "timing.json")
    ap.add_argument("--out", type=Path, default=BUILD / "video" / "mixue.mp4")
    ap.add_argument("--prepare-only", action="store_true",
                    help="extract panels, manifest and QA only")
    ap.add_argument("--grid", choices=("detect", "uniform"), default="detect")
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--rows", type=int, default=3)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--fit", choices=("contain", "cover"), default="contain",
                    help="contain keeps every source pixel and pads; cover crops")
    ap.add_argument("--allow-script-timing", action="store_true",
                    help="fall back to tts.json start/end when timing.json is missing")
    ap.add_argument("--allow-unverified", action="store_true",
                    help="render even without VLM verdict (preview only)")
    ap.add_argument("--allow-review", action="store_true",
                    help="render when QA is review instead of pass")
    ap.add_argument("--no-normalized", action="store_true",
                    help="skip equal-width/height preview set at mux time")
    ap.add_argument("--normalized-size", default="640x360")
    ap.add_argument("--normalized-mode", choices=("fill", "cover", "contain"), default="fill")
    a = ap.parse_args()

    if not a.image.exists():
        raise SystemExit(f"storyboard image not found: {a.image}")
    if a.cols < 1 or a.rows < 1:
        raise SystemExit("--cols and --rows must be >= 1")

    im = Image.open(a.image).convert("RGB")
    width, height = im.size
    source_sha = pg.file_sha256(a.image)

    grid = pg.detect_boxes(im, a.cols, a.rows) if a.grid == "detect" else {
        "ok": False, "method": "uniform", "row_gaps": [], "strips": [],
        "reasons": ["uniform grid requested"], "boxes": [],
    }
    if a.grid == "detect" and not grid["ok"]:
        print("WARNING: gutter detection failed, falling back to uniform grid:")
        for reason in grid["reasons"]:
            print("  -", reason)
    boxes = grid["boxes"] if grid["ok"] else pg.uniform_boxes(width, height, a.cols, a.rows)

    if len(boxes) != a.cols * a.rows:
        raise SystemExit(f"expected {a.cols*a.rows} panels, got {len(boxes)}")

    scenes = load_json(a.script).get("scenes", [])
    if not scenes:
        raise SystemExit(f"no scenes in {a.script}")

    timing = None
    if a.timing.exists():
        timing = load_json(a.timing)
        if [s["scene_id"] for s in timing.get("scenes", [])] != [f"scene_{i:02d}" for i in range(len(scenes))]:
            raise SystemExit(f"timing.json scenes do not match {a.script}")
    elif not a.prepare_only and not a.allow_script_timing:
        raise SystemExit(
            f"measured timing required for muxing: {a.timing}\n"
            "run `make-tts.py` first, or pass --allow-script-timing for rough cut"
        )

    panels_dir = BUILD / "panels"
    frames_dir = BUILD / "frames"
    panels_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)

    panels = []
    for i, box in enumerate(boxes):
        raw = im.crop(box)
        raw_path = panels_dir / f"panel_{i:03d}.png"
        raw.save(raw_path)
        frame, display = pg.fit_frame(raw, a.width, a.height, a.fit, (255, 255, 255))
        frame_path = frames_dir / f"panel_{i:03d}.png"
        frame.save(frame_path)
        display["frame_size"] = [a.width, a.height]
        panels.append({
            "panel_id": f"panel_{i:03d}",
            "index": i,
            "row": i // a.cols,
            "col": i % a.cols,
            "source_box": list(box),
            "source_size": [box[2] - box[0], box[3] - box[1]],
            "aspect": round((box[2] - box[0]) / (box[3] - box[1]), 4),
            "raw_path": raw_path.relative_to(BUILD).as_posix(),
            "raw_sha256": pg.file_sha256(raw_path),
            "frame_path": frame_path.relative_to(BUILD).as_posix(),
            "display": display,
        })

    timing_scenes = timing.get("scenes") if timing else None
    manifest = {
        "schema_version": "2.0",
        "source_image": a.image.name,
        "source_sha256": source_sha,
        "source_size": {"width": width, "height": height},
        "grid": {
            "cols": a.cols, "rows": a.rows, "order": "row-major",
            "method": grid["method"] if grid["ok"] else "uniform",
            "requested": a.grid,
            "ok": grid["ok"],
            "reasons": grid["reasons"],
            "row_gaps": grid["row_gaps"],
            "strips": [{"y": s["y"], "col_gaps": s["col_gaps"]} for s in grid["strips"]],
        },
        "frame": {"width": a.width, "height": a.height, "fps": a.fps, "fit": a.fit,
                  "background": [255, 255, 255]},
        "panels": panels,
        "timing": {
            "file": a.timing.name, "present": bool(timing),
            "source": timing.get("source") if timing else "script",
            "total_duration": timing.get("total_duration") if timing else None,
            "gap": timing.get("gap") if timing else None,
            "lead_in": timing.get("lead_in") if timing else None,
        },
        "scenes": [
            {
                "scene_id": f"scene_{i:02d}",
                "index": i,
                "start": timing_scenes[i]["start"] if timing_scenes else scene["start"],
                "end": timing_scenes[i]["end"] if timing_scenes else scene["end"],
                "display_start": timing_scenes[i]["display_start"] if timing_scenes else scene["start"],
                "display_end": timing_scenes[i]["display_end"] if timing_scenes else scene["end"],
                "display_duration": timing_scenes[i]["display_duration"] if timing_scenes else scene["end"] - scene["start"],
                "text": scene["text"],
                "visual": scene.get("visual"),
            }
            for i, scene in enumerate(scenes)
        ],
    }
    manifest_path = BUILD / "manifest.json"
    write_json(manifest_path, manifest)
    print(f"panels: {len(panels)}  grid={manifest['grid']['method']}  -> {manifest_path}")
    for p in panels:
        print(f"  {p['panel_id']} box={p['source_box']} {p['source_size'][0]}x{p['source_size'][1]} "
              f"aspect={p['aspect']} padded={p['display']['padded_px']} cropped={p['display']['cropped_px']}")

    # Deterministic QA
    qa_path = BUILD / "qa.json"
    qa_cmd = [sys.executable, str(ROOT / "scripts" / "pipeline" / "panel_qa.py"),
              "--image", str(a.image), "--manifest", str(manifest_path), "--out", str(qa_path)]
    qa = subprocess.run(qa_cmd, text=True)
    if qa.returncode != 0:
        raise SystemExit("crop QA failed; see qa.json (render stopped)")
    qa_report = load_json(qa_path)

    if a.prepare_only:
        print("prepare-only: panels, manifest and crop QA are ready")
        return

    if qa_report["overall"] != "pass" and not a.allow_review:
        raise SystemExit(f"crop QA is {qa_report['overall']}; pass --allow-review to render anyway")

    # Load VLM verdict (merged into qa.json by qa_vlm.py)
    qa = load_json(qa_path)
    vlm_state = qa.get("vlm", {}).get("overall", "missing")
    if vlm_state == "fail":
        raise SystemExit("VLM crop verdict is fail; fix the crops before rendering")
    if vlm_state == "review" and not a.allow_review:
        raise SystemExit("VLM crop verdict is review; pass --allow-review to render anyway")
    if vlm_state in ("missing", "stale") and not a.allow_unverified:
        raise SystemExit(
            f"VLM crop verdict required ({vlm_state}): {qa_path}\n"
            "run `qa_vlm.py`, or pass --allow-unverified for preview"
        )

    # Timing
    if timing_scenes:
        total_duration = float(timing["total_duration"])
        display = [(s["display_start"], s["display_end"]) for s in timing_scenes]
    else:
        total_duration = float(scenes[-1]["end"])
        display = [(float(s["start"]), float(s["end"])) for s in scenes]
        print("WARNING: using script timing, not measured audio")

    scene_ids = [f"scene_{i:02d}" for i in range(len(scenes))]
    # Load panel-map.json and merge into manifest
    panel_map_path = BUILD / "panel-map.json"
    if panel_map_path.exists():
        panel_map = load_json(panel_map_path)
        pm = {m["scene_id"]: m["panel_id"] for m in panel_map.get("mappings", [])}
        for s in manifest.get("scenes", []):
            sid = s["scene_id"]
            if sid in pm:
                s["panel_id"] = pm[sid]
    # Mapping from manifest (panel-map merged in)
    mapping = {s["scene_id"]: s.get("panel_id") for s in manifest.get("scenes", [])}
    if set(mapping) != set(scene_ids):
        raise SystemExit(f"manifest.scenes missing panel_id for some scenes; expected {scene_ids}")
    valid = {p["panel_id"] for p in panels}
    if not set(mapping.values()).issubset(valid):
        raise SystemExit(f"manifest.scenes references unknown panels: {sorted(valid)}")

    # Normalized preview
    if not a.no_normalized:
        try:
            nw, nh = (int(x) for x in a.normalized_size.lower().split("x"))
        except ValueError:
            raise SystemExit(f"invalid --normalized-size: {a.normalized_size}")
        run([sys.executable, str(ROOT / "scripts" / "pipeline" / "normalize_panels.py"),
             "--manifest", str(manifest_path), "--out", str(BUILD / "normalized"),
             "--width", str(nw), "--height", str(nh),
             "--mode", a.normalized_mode, "--title", "mux normalized preview"])

    # Concat video
    list_file = BUILD / "png-scenes.txt"
    lines = []
    for scene_id, (d0, d1) in zip(scene_ids, display):
        duration = d1 - d0
        if duration <= 0:
            raise SystemExit(f"invalid display duration for {scene_id}: {duration}")
        panel_index = int(mapping[scene_id].split("_")[1])
        frame_path = (BUILD / panels[panel_index]["frame_path"]).resolve()
        lines.extend([f"file '{frame_path.as_posix()}'", f"duration {duration:.6f}"])
    last_index = int(mapping[scene_ids[-1]].split("_")[1])
    lines.append(f"file '{(BUILD / panels[last_index]['frame_path']).resolve().as_posix()}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    audio = BUILD / "audio" / "narration.wav"
    if not audio.exists():
        audio = BUILD / "audio" / "narration.mp3"
    if not audio.exists():
        raise SystemExit("narration.wav/mp3 not found; run make-tts.py first")

    a.out.parent.mkdir(parents=True, exist_ok=True)
    (BUILD / "video").mkdir(parents=True, exist_ok=True)

    silent = a.out.with_name(a.out.stem + "-silent.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
         "-t", f"{total_duration:.6f}", "-vf", f"fps={a.fps},format=yuv420p",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", str(a.fps),
         "-an", silent])
    run(["ffmpeg", "-y", "-i", silent, "-i", audio,
         "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-t", f"{total_duration:.6f}",
         "-movflags", "+faststart", a.out])
    silent.unlink(missing_ok=True)

    video_duration = probe_duration(a.out, "v:0")
    audio_duration = probe_duration(a.out, "a:0")
    drift = None if None in (video_duration, audio_duration) else audio_duration - video_duration
    tolerance = 0.12
    report = {
        "schema_version": "1.0",
        "output": a.out.name,
        "timing_source": "measured-audio" if timing_scenes else "script",
        "expected_duration": round(total_duration, 6),
        "video_duration": round(video_duration, 6) if video_duration else None,
        "audio_duration": round(audio_duration, 6) if audio_duration else None,
        "audio_file": audio.name,
        "audio_video_drift": round(drift, 6) if drift is not None else None,
        "tolerance": tolerance,
        "qa": {"crop": qa_report["overall"], "vlm": vlm_state},
        "scenes": [
            {"scene_id": sid, "panel_id": mapping[sid],
             "display_start": round(d0, 3), "display_end": round(d1, 3),
             "display_duration": round(d1 - d0, 3)}
            for sid, (d0, d1) in zip(scene_ids, display)
        ],
        "ok": bool(video_duration and audio_duration
                   and abs(video_duration - total_duration) <= tolerance
                   and abs(audio_duration - total_duration) <= tolerance
                   and abs(drift) <= tolerance),
    }
    write_json(BUILD / "mux-report.json", report)
    print(f"mux: video={video_duration:.3f}s audio={audio_duration:.3f}s "
          f"expected={total_duration:.3f}s drift={drift:+.4f}s -> {a.out}")
    if not report["ok"]:
        raise SystemExit("duration verification failed; see mux-report.json")
    print(f"created {a.out}")


if __name__ == "__main__":
    main()