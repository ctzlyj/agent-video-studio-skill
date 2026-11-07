"""Extract a video asset into frames for deterministic canvas playback.
project.json: "videos": {"name": {"src": "assets/clip.mp4", "fps": 25, "width": 540}}
Writes assets/_frames/<name>/f_00001.jpg ... and videos.js. Re-run after changing videos.
"""
from __future__ import annotations
import argparse, json, os, shutil, sys
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
from avs_common import project_dir, load_json, ffmpeg, run

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('project', nargs='?'); a = ap.parse_args()
    d = project_dir(a.project); p = load_json(d / 'project.json'); meta = {}
    for name, v in (p.get('videos') or {}).items():
        v = {'src': v} if isinstance(v, str) else v
        src = d / v['src']; fps = int(v.get('fps', 25)); width = int(v.get('width', 640))
        out = d / 'assets' / '_frames' / name
        stamp = out / '.src'; key = f"{src.stat().st_mtime_ns}:{fps}:{width}:{v.get('start', 0)}:{v.get('duration', '')}"
        if not (stamp.exists() and stamp.read_text() == key):
            shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
            cut = (['-ss', str(v['start'])] if v.get('start') else []) + (['-t', str(v['duration'])] if v.get('duration') else [])
            run([ffmpeg(), '-y', '-hide_banner', '-loglevel', 'error', *cut, '-i', src, '-vf', f'fps={fps},scale={width}:-2', '-q:v', '3', out / 'f_%05d.jpg'])
            stamp.write_text(key)
        frames = sorted(out.glob('f_*.jpg'))
        from PIL import Image
        w, h = Image.open(frames[0]).size
        meta[name] = {'dir': f'assets/_frames/{name}', 'count': len(frames), 'fps': fps, 'w': w, 'h': h, 'seconds': round(len(frames) / fps, 2)}
        print(f"{name}: {len(frames)} frames, {meta[name]['seconds']}s, {w}x{h}")
    (d / 'videos.js').write_text('window.VIDEOS=' + json.dumps(meta, ensure_ascii=False) + ';', encoding='utf-8')

if __name__ == '__main__': main()
