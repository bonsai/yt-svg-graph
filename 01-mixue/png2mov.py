#!/usr/bin/env python3
"""Split a storyboard PNG into panels and turn them into a narrated MP4.

Default grid is 4x2, with panel order matched to scenes in tts.json.
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
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--rows", type=int, default=2)
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
    lines, total_duration = [], 0.0
    for i, scene in enumerate(scenes):
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
        duration = float(scene["end"]) - float(scene["start"])
        if duration <= 0:
            raise SystemExit(f"Invalid scene duration for scene {i}: {duration}")
        total_duration += duration
        lines.extend([f"file '{panel_path.resolve().as_posix()}'", f"duration {duration:.3f}"])
    # Repeat final still so concat demuxer respects its duration.
    lines.append(f"file '{(panels_dir / f'panel_{len(scenes)-1:03d}.png').resolve().as_posix()}'")
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
