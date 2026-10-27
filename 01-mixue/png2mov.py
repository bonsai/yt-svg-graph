#!/usr/bin/env python3
"""Split a storyboard PNG into panels and turn them into a narrated MP4.

Default grid is 3x3. All nine panels are extracted; video timing uses scenes defined in tts.json.
"""
from pathlib import Path
import argparse
import json
import subprocess

ROOT = Path(__file__).resolve().parent

def run(cmd):
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run([str(x) for x in cmd], check=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", type=Path, default=ROOT / "MIXUE世界展開ストーリーボード展開.png")
    ap.add_argument("--script", type=Path, default=ROOT / "tts.json")
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "mixue.mp4")
    ap.add_argument("--panel-map", type=Path, default=ROOT / "build" / "panel-map.json", help="Local-VLM mapping: scene_id -> panel_id")
    ap.add_argument("--prepare-only", action="store_true", help="Extract all panels and write manifest without rendering video")
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--rows", type=int, default=3)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    a = ap.parse_args()
    if not a.image.exists():
        raise SystemExit(f"Storyboard image not found: {a.image}")
    if a.cols < 1 or a.rows < 1:
        raise SystemExit("--cols and --rows must be >= 1")
    from PIL import Image
    scenes = json.loads(a.script.read_text(encoding="utf-8")).get("scenes", [])
    if not scenes:
        raise SystemExit(f"No scenes found in {a.script}")
    if len(scenes) > a.cols * a.rows:
        raise SystemExit(f"{len(scenes)} script scenes exceed grid capacity {a.cols*a.rows}; increase --cols/--rows")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    panels_dir = a.out.parent / "png-panels"
    panels_dir.mkdir(parents=True, exist_ok=True)
    image = Image.open(a.image).convert("RGB")
    w, h = image.size
    list_file = a.out.parent / "png-scenes.txt"
    # Extract every grid cell as a reusable asset, including cells without a narration scene.
    panel_paths = []
    for i in range(a.cols * a.rows):
        col, row = i % a.cols, i // a.cols
        panel = image.crop((round(col*w/a.cols), round(row*h/a.rows),
                            round((col+1)*w/a.cols), round((row+1)*h/a.rows)))
        # Cover-crop to 16:9 without distorting the panel.
        target_ratio, ratio = a.width/a.height, panel.width/panel.height
        if ratio > target_ratio:
            new_w = round(panel.height*target_ratio)
            x = (panel.width-new_w)//2
            panel = panel.crop((x, 0, x+new_w, panel.height))
        else:
            new_h = round(panel.width/target_ratio)
            y = (panel.height-new_h)//2
            panel = panel.crop((0, y, panel.width, y+new_h))
        panel = panel.resize((a.width, a.height), Image.Resampling.LANCZOS)
        panel_path = panels_dir / f"panel_{i:03d}.png"
        panel.save(panel_path)
        panel_paths.append(panel_path)

    manifest = {
        "schema_version": "1.0",
        "source_image": a.image.name,
        "grid": {"cols": a.cols, "rows": a.rows, "order": "row-major"},
        "source_size": {"width": w, "height": h},
        "panel_size": {"width": a.width, "height": a.height},
        "panels": [
            {"panel_id": f"panel_{i:03d}", "index": i, "row": i // a.cols, "col": i % a.cols,
             "path": panel_paths[i].relative_to(a.out.parent).as_posix()}
            for i in range(len(panel_paths))
        ],
        "scenes": [
            {"scene_id": f"scene_{i:02d}", "index": i, "start": scene["start"], "end": scene["end"],
             "text": scene["text"], "visual": scene.get("visual")}
            for i, scene in enumerate(scenes)
        ],
        "mapping_contract": {
            "file": a.panel_map.name,
            "shape": {"mappings": [{"scene_id": "scene_00", "panel_id": "panel_004", "confidence": 0.95, "reason": "short rationale"}]},
            "note": "Mapping is intentionally not inferred here. Use a local VLM to create panel-map.json."
        }
    }
    manifest_path = a.out.parent / "panel-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(panel_paths)} panels and manifest: {manifest_path}")

    if a.prepare_only:
        return

    if not a.panel_map.exists():
        raise SystemExit(
            f"Local VLM mapping required: {a.panel_map}. Run with --prepare-only to extract panels, "
            "then create panel-map.json using your local VLM."
        )
    mapping_data = json.loads(a.panel_map.read_text(encoding="utf-8"))
    mapping = {item["scene_id"]: item["panel_id"] for item in mapping_data.get("mappings", [])}
    expected_ids = {f"scene_{i:02d}" for i in range(len(scenes))}
    if set(mapping) != expected_ids:
        raise SystemExit(f"panel-map.json must map every scene exactly once; expected {sorted(expected_ids)}")
    valid_panels = {f"panel_{i:03d}" for i in range(len(panel_paths))}
    if not set(mapping.values()).issubset(valid_panels):
        raise SystemExit(f"panel-map.json references unknown panels; valid IDs: {sorted(valid_panels)}")
    if len(set(mapping.values())) != len(mapping):
        raise SystemExit("panel-map.json currently requires a unique panel for each scene")

    lines, total_duration = [], 0.0
    for i, scene in enumerate(scenes):
        scene_id = f"scene_{i:02d}"
        panel_id = mapping[scene_id]
        panel_index = int(panel_id.split("_")[1])
        panel_path = panel_paths[panel_index]
        duration = float(scene["end"]) - float(scene["start"])
        if duration <= 0:
            raise SystemExit(f"Invalid scene duration for scene {i}: {duration}")
        total_duration += duration
        lines.extend([f"file '{panel_path.resolve().as_posix()}'", f"duration {duration:.3f}"])
    # Repeat final still so concat demuxer respects its duration.
    last_panel_index = int(mapping[f"scene_{len(scenes)-1:02d}"].split("_")[1])
    lines.append(f"file '{panel_paths[last_panel_index].resolve().as_posix()}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    silent = a.out.with_name(a.out.stem + "-silent.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
         "-t", f"{total_duration:.3f}", "-vf", f"fps={a.fps},format=yuv420p",
         "-c:v", "libx264", "-r", str(a.fps), "-an", silent])
    audio = a.out.parent / "narration.mp3"
    if audio.exists():
        run(["ffmpeg", "-y", "-i", silent, "-i", audio, "-map", "0:v:0", "-map", "1:a:0",
             "-c:v", "copy", "-c:a", "aac", "-shortest", a.out])
        silent.unlink(missing_ok=True)
    else:
        silent.replace(a.out)
    print(f"Created {a.out} from {a.image}; split {len(scenes)} panels into {panels_dir}.")

if __name__ == "__main__":
    main()
