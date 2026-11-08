"""Build the evidence pack an independent reviewer needs to judge a finished film.

  python scripts/review_pack.py [project] [--file out/x.mp4] [--every 0.5] [--moves 3.2,7.5] [--frames 6]

Writes <project>/qa/review/:
  sheet_<every>s.jpg   contact sheet, one frame every --every seconds (timecode on each tile)
  strip_<t>s.jpg       filmstrip of 12 consecutive frames around each --moves time (fast moves, the hero moment)
  frame_<t>s.png       full-resolution frames at --frames evenly spaced key times (check type, edges, banding)
  spec.json            measured: duration, size, fps, audio present, loudness, true peak, black / frozen spans
The reviewer should be a separate agent session that has not seen the code (see references/mg-styles.md for the brief).
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
from avs_common import project_dir, ffmpeg, media_duration, save_json

def _run(cmd): return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding='utf-8', errors='ignore')

def probe(ff, f):
    info = _run([ff, '-hide_banner', '-i', f]).stderr
    m = re.search(r'Video:.*?, (\d{2,5})x(\d{2,5})', info); fps = re.search(r'([\d.]+) fps', info)
    return {'width': int(m[1]) if m else None, 'height': int(m[2]) if m else None, 'fps': float(fps[1]) if fps else None, 'has_audio': 'Audio:' in info}

def loudness(ff, f):
    r = _run([ff, '-hide_banner', '-nostats', '-i', f, '-vn', '-af', 'ebur128=peak=true', '-f', 'null', '-']).stderr
    tail = r[r.rfind('Summary:'):] if 'Summary:' in r else r
    i = re.search(r'I:\s+(-?[\d.]+) LUFS', tail); p = re.search(r'Peak:\s+(-?[\d.]+) dBFS', tail)
    return (float(i[1]) if i else None), (float(p[1]) if p else None)

def spans(ff, f):
    bd = _run([ff, '-hide_banner', '-i', f, '-vf', 'blackdetect=d=0.2:pix_th=0.06', '-an', '-f', 'null', '-']).stderr
    fz = _run([ff, '-hide_banner', '-i', f, '-vf', 'freezedetect=n=0.001:d=1', '-an', '-f', 'null', '-']).stderr
    black = [[float(a), float(b)] for a, b in re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', bd)]
    st = [float(x) for x in re.findall(r'freeze_start: ([\d.]+)', fz)]; du = [float(x) for x in re.findall(r'freeze_duration: ([\d.]+)', fz)]
    return black, [{'start': s, 'duration': (du[i] if i < len(du) else None)} for i, s in enumerate(st)]

def grab(ff, f, t, out, scale=None):
    vf = f'scale={scale}' if scale else 'null'
    _run([ff, '-y', '-loglevel', 'error', '-ss', f'{max(t, 0):.3f}', '-i', f, '-vf', vf, '-vframes', '1', out])

def label(im, text):
    from PIL import ImageDraw
    d = ImageDraw.Draw(im); d.rectangle([0, 0, 8 * len(text) + 8, 16], fill=(0, 0, 0)); d.text((4, 2), text, fill=(255, 255, 255))

def main():
    from PIL import Image
    ap = argparse.ArgumentParser(); ap.add_argument('project', nargs='?'); ap.add_argument('--file'); ap.add_argument('--every', type=float, default=0.5)
    ap.add_argument('--moves', default=''); ap.add_argument('--frames', type=int, default=6); a = ap.parse_args()
    d = project_dir(a.project); ff = ffmpeg()
    f = Path(a.file) if a.file else max((d / 'out').glob('*.mp4'), key=lambda x: x.stat().st_mtime)
    out = d / 'qa' / 'review'; out.mkdir(parents=True, exist_ok=True); tmp = out / '_t'; tmp.mkdir(exist_ok=True)
    dur = media_duration(f); info = probe(ff, str(f)); lufs, tp = loudness(ff, str(f)) if info['has_audio'] else (None, None); black, freeze = spans(ff, str(f))
    tiles = []; t = 0.0
    while t < dur - 1e-6:
        p = str(tmp / f's_{len(tiles):04d}.jpg'); grab(ff, str(f), min(t, dur - 0.05), p, '320:-2'); tiles.append((t, p)); t += a.every
    ims = [Image.open(p).convert('RGB') for _, p in tiles if os.path.exists(p)]
    if ims:
        tw, th = ims[0].size; cols = 6; rows = -(-len(ims) // cols); sheet = Image.new('RGB', (tw * cols, th * rows), (18, 18, 18))
        for i, (im, (tt, _)) in enumerate(zip(ims, tiles)): label(im, f'{tt:.1f}s'); sheet.paste(im, ((i % cols) * tw, (i // cols) * th))
        sheet.save(out / f'sheet_{a.every:g}s.jpg', quality=88)
    fps = info['fps'] or 30
    for ts in [float(x) for x in a.moves.split(',') if x.strip()]:
        fr = []
        for k in range(12):
            p = str(tmp / f'm_{ts}_{k}.jpg'); grab(ff, str(f), min(ts + (k - 4) / fps, dur - 0.05), p, '360:-2'); fr.append(p)
        im = [Image.open(p).convert('RGB') for p in fr if os.path.exists(p)]
        if im:
            tw, th = im[0].size; strip = Image.new('RGB', (tw * 6, th * 2), (18, 18, 18))
            for k, x in enumerate(im): label(x, f'{ts + (k - 4) / fps:.2f}s'); strip.paste(x, ((k % 6) * tw, (k // 6) * th))
            strip.save(out / f'strip_{ts:g}s.jpg', quality=88)
    keys = [round(dur * (i + 0.5) / a.frames, 2) for i in range(a.frames)] if a.frames > 0 else []
    for ts in keys: grab(ff, str(f), ts, str(out / f'frame_{ts:g}s.png'))
    for p in tmp.glob('*'): p.unlink()
    tmp.rmdir()
    spec = {'file': f.name, 'duration': round(dur, 3), **info, 'lufs': lufs, 'true_peak_dbfs': tp, 'black_spans': black, 'freeze_spans': freeze, 'key_frames': keys}
    save_json(out / 'spec.json', spec)
    print(json.dumps(spec, ensure_ascii=False, indent=2)); print('review pack ->', out)

if __name__ == '__main__': main()