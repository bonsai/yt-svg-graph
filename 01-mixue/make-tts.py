#!/usr/bin/env python3
"""Generate one Japanese speech clip per scene and concatenate them in scene order."""
from pathlib import Path
import argparse, asyncio, json, subprocess
import edge_tts
ROOT=Path(__file__).resolve().parent
async def main_async(args):
    data=json.loads(args.script.read_text(encoding='utf-8'))
    out=args.out; out.mkdir(parents=True,exist_ok=True)
    parts=[]
    for i,scene in enumerate(data['scenes']):
        target=out/f'voice_{i:02d}.mp3'
        communicate=edge_tts.Communicate(scene['text'], data.get('voice','ja-JP-NanamiNeural'), rate='-5%')
        await communicate.save(str(target)); parts.append(target)
    listing=out/'concat.txt'
    listing.write_text(''.join("file '"+p.name+"'\\n" for p in parts),encoding='utf-8')
    subprocess.run(['ffmpeg','-y','-f','concat','-safe','0','-i',str(listing),'-c:a','libmp3lame','-q:a','3',str(out/'narration.mp3')],check=True)
    print('Narration:',out/'narration.mp3')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--script',type=Path,default=ROOT/'tts.json');ap.add_argument('--out',type=Path,default=ROOT/'build');args=ap.parse_args();asyncio.run(main_async(args))
if __name__=='__main__':main()
