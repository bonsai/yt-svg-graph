#!/usr/bin/env python3
"""Create a silent MP4 from captured PNG frames, then mux optional narration."""
from pathlib import Path
import argparse, subprocess, sys
ROOT=Path(__file__).resolve().parent

def run(cmd):
    print('+', ' '.join(map(str,cmd)), flush=True)
    subprocess.run(list(map(str,cmd)), check=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--frames',type=Path,default=ROOT/'build'/'frames')
    ap.add_argument('--audio',type=Path,default=ROOT/'build'/'narration.mp3')
    ap.add_argument('--out',type=Path,default=ROOT/'build'/'mixue.mp4')
    ap.add_argument('--fps',type=int,default=1)
    ap.add_argument('--duration',type=int,default=120)
    a=ap.parse_args(); a.out.parent.mkdir(parents=True,exist_ok=True)
    silent=a.out.with_name(a.out.stem+'-silent.mp4')
    run(['ffmpeg','-y','-framerate',a.fps,'-i',a.frames/'frame_%06d.png','-t',a.duration,'-c:v','libx264','-pix_fmt','yuv420p','-r',30,silent])
    if a.audio.exists():
        run(['ffmpeg','-y','-i',silent,'-i',a.audio,'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-shortest',a.out])
        silent.unlink(missing_ok=True)
    else:
        silent.replace(a.out)
    print(f'Created {a.out}')
if __name__=='__main__': main()
