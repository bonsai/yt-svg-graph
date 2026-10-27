#!/usr/bin/env python3
"""Generate per-scene Japanese TTS and an audio-locked timeline.

The narration is assembled locally into one WAV (sample-accurate silence between
scenes) so the panel timeline can be derived from *measured* audio length
instead of the hand-written start/end values in tts.json.

Outputs (in --out, default 01-mixue/build):

  voice/voice_XX.mp3   per-scene clips (cached by text hash)
  narration.wav        48 kHz / 16-bit / stereo, used for muxing
  narration.mp3        same audio, compressed, for preview
  timing.json          measured scene start/end and display intervals
"""
from pathlib import Path
import argparse
import asyncio
import hashlib
import json
import subprocess
import wave

import edge_tts

ROOT = Path(__file__).resolve().parent
RATE = 48000
CHANNELS = 2
SAMPLE_WIDTH = 2


def run(cmd):
    cmd = [str(x) for x in cmd]
    if cmd and cmd[0] == "ffmpeg":
        cmd = [cmd[0], "-hide_banner", "-loglevel", "error", *cmd[1:]]
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def to_wav(src, dst):
    run(["ffmpeg", "-y", "-i", src, "-ar", RATE, "-ac", CHANNELS,
         "-sample_fmt", "s16", dst])


def wav_frames(path):
    with wave.open(str(path), "rb") as w:
        if w.getframerate() != RATE or w.getnchannels() != CHANNELS or w.getsampwidth() != SAMPLE_WIDTH:
            raise SystemExit(f"unexpected wav format: {path}")
        return w.readframes(w.getnframes())


def silence(frames):
    return b"\x00" * (frames * CHANNELS * SAMPLE_WIDTH)


async def synth(text, voice, out):
    await edge_tts.Communicate(text, voice, rate="-5%").save(str(out))


async def build(a):
    script = json.loads(a.script.read_text(encoding="utf-8"))
    scenes = script.get("scenes", [])
    if not scenes:
        raise SystemExit(f"no scenes in {a.script}")

    out = a.out
    voice_dir = out / "voice"
    wav_dir = out / "voice-wav"
    voice_dir.mkdir(parents=True, exist_ok=True)
    wav_dir.mkdir(parents=True, exist_ok=True)

    lead_in = float(a.lead_in if a.lead_in is not None else script.get("lead_in", 0.30))
    gap = float(a.gap if a.gap is not None else script.get("gap", 0.40))
    tail = float(a.tail if a.tail is not None else script.get("tail", 0.60))
    lead_frames, gap_frames, tail_frames = (round(x * RATE) for x in (lead_in, gap, tail))

    voice = script.get("voice", "ja-JP-NanamiNeural")
    cache_path = voice_dir / "cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}

    pcm_parts = [silence(lead_frames)]
    timing_scenes = []
    cursor = lead_frames

    for i, scene in enumerate(scenes):
        text = scene["text"]
        key = sha256_text(text + "|" + voice)
        mp3 = voice_dir / f"voice_{i:02d}.mp3"
        wav = wav_dir / f"voice_{i:02d}.wav"
        if a.force or cache.get(f"voice_{i:02d}") != key or not mp3.exists():
            print(f"TTS {i:02d}: {len(text)} chars", flush=True)
            await synth(text, voice, mp3)
            cache[f"voice_{i:02d}"] = key
        else:
            print(f"TTS {i:02d}: cached", flush=True)
        to_wav(mp3, wav)
        data = wav_frames(wav)
        frames = len(data) // (CHANNELS * SAMPLE_WIDTH)
        if frames == 0:
            raise SystemExit(f"empty audio for scene {i}")

        start = cursor / RATE
        end = (cursor + frames) / RATE
        timing_scenes.append({
            "scene_id": f"scene_{i:02d}",
            "index": i,
            "text_sha256": key,
            "audio": (Path("voice") / mp3.name).as_posix(),
            "duration": round(frames / RATE, 6),
            "start": round(start, 6),
            "end": round(end, 6),
        })
        pcm_parts.append(data)
        cursor += frames
        if i < len(scenes) - 1:
            pcm_parts.append(silence(gap_frames))
            cursor += gap_frames

    pcm_parts.append(silence(tail_frames))
    cursor += tail_frames
    total_duration = cursor / RATE

    # Display intervals: a panel holds from the previous speech end (through the
    # gap) until the next speech starts. First panel covers the lead-in.
    for i, scene in enumerate(timing_scenes):
        prev_end = 0.0 if i == 0 else timing_scenes[i - 1]["end"]
        next_start = timing_scenes[i + 1]["start"] if i + 1 < len(timing_scenes) else total_duration
        scene["display_start"] = round(prev_end if i else 0.0, 6)
        scene["display_end"] = round(next_start, 6)
        scene["display_duration"] = round(next_start - scene["display_start"], 6)

    wav_path = out / "narration.wav"
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(SAMPLE_WIDTH)
        w.setframerate(RATE)
        w.writeframes(b"".join(pcm_parts))

    mp3_path = out / "narration.mp3"
    run(["ffmpeg", "-y", "-i", wav_path, "-c:a", "libmp3lame", "-q:a", "3", mp3_path])
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    timing = {
        "schema_version": "1.0",
        "source": "measured-audio",
        "script": a.script.name,
        "voice": voice,
        "rate": RATE,
        "channels": CHANNELS,
        "lead_in": lead_in,
        "gap": gap,
        "tail": tail,
        "total_duration": round(total_duration, 6),
        "narration": {"wav": "narration.wav", "mp3": "narration.mp3"},
        "scenes": timing_scenes,
    }
    timing_path = out / "timing.json"
    timing_path.write_text(json.dumps(timing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"\n{'scene':<9}{'speech':>8}{'start':>8}{'end':>8}{'display':>10}")
    for s in timing_scenes:
        print(f"{s['scene_id']:<9}{s['duration']:>8.2f}{s['start']:>8.2f}{s['end']:>8.2f}"
              f"{s['display_duration']:>10.2f}")
    print(f"total: {total_duration:.3f}s  -> {timing_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", type=Path, default=ROOT / "tts.json")
    ap.add_argument("--out", type=Path, default=ROOT / "build")
    ap.add_argument("--lead-in", type=float, default=None, help="silence before the first scene")
    ap.add_argument("--gap", type=float, default=None, help="silence between scenes")
    ap.add_argument("--tail", type=float, default=None, help="silence after the last scene")
    ap.add_argument("--force", action="store_true", help="ignore the TTS cache")
    a = ap.parse_args()
    asyncio.run(build(a))


if __name__ == "__main__":
    main()
