"""Post-render QA on the final file: duration vs timeline, audio present & loudness, black/frozen frames,
and a contact sheet sampled from the encoded MP4 (what the viewer actually sees). Writes qa/report.json.
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
from avs_common import project_dir, load_json, save_json, ffmpeg, media_duration

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('project', nargs='?'); ap.add_argument('--file'); a = ap.parse_args()
    d = project_dir(a.project); tl = load_json(d / 'timeline.json')
    f = Path(a.file) if a.file else max((d / 'out').glob('*.mp4'), key=lambda x: x.stat().st_mtime)
    ff = ffmpeg(); rep = {'file': str(f), 'checks': []}
    def chk(name, ok, detail): rep['checks'].append({'name': name, 'ok': bool(ok), 'detail': detail})
    dur = media_duration(f); chk('duration', abs(dur - tl['duration']) < 0.5, f'{dur:.2f}s vs timeline {tl["duration"]:.2f}s')
    info = subprocess.run([ff, '-hide_banner', '-i', str(f)], capture_output=True, text=True, encoding='utf-8', errors='ignore').stderr
    has_audio = 'Audio:' in info; chk('audio stream', has_audio, 'present' if has_audio else 'missing')
    if has_audio:
        v = subprocess.run([ff, '-hide_banner', '-i', str(f), '-af', 'volumedetect', '-vn', '-f', 'null', '-'], capture_output=True, text=True, encoding='utf-8', errors='ignore').stderr
        mean = float(re.search(r'mean_volume: ([-\d.]+)', v)[1]); peak = float(re.search(r'max_volume: ([-\d.]+)', v)[1])
        chk('loudness', -24 < mean < -9 and peak <= -0.1, f'mean {mean} dB, peak {peak} dB')
    sr = d / 'audio' / 'score_report.json'
    if sr.exists():
        r = load_json(sr); chk('score: no clipping, energy arc audible', r.get('noClip') and r.get('arcOk'), f"{r.get('style')} {r.get('bpm'):.0f} bpm; {r.get('arcNote')}")
    bd = subprocess.run([ff, '-hide_banner', '-i', str(f), '-vf', 'blackdetect=d=0.8:pix_th=0.06', '-an', '-f', 'null', '-'], capture_output=True, text=True, encoding='utf-8', errors='ignore').stderr
    blacks = re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', bd)
    mid = [(float(s), float(e)) for s, e in blacks if float(s) > 0.5 and float(e) < dur - 0.5]
    chk('no black gaps', not mid, f'{len(mid)} black segment(s) mid-video: {mid[:5]}' if mid else 'none')
    fz = subprocess.run([ff, '-hide_banner', '-i', str(f), '-vf', 'freezedetect=n=0.001:d=6', '-an', '-f', 'null', '-'], capture_output=True, text=True, encoding='utf-8', errors='ignore').stderr
    frozen = re.findall(r'freeze_start: ([\d.]+)', fz)
    chk('no long frozen picture (>6s)', not frozen, f'frozen at {frozen[:5]}' if frozen else 'none')
    qa = d / 'qa'; qa.mkdir(exist_ok=True)
    pts = [round(s['ns'] + s['nd'] * .6, 2) for s in tl['scenes']]
    from PIL import Image, ImageDraw
    tiles = []
    for t in pts:
        p = qa / f'_fq_{t:07.2f}.jpg'
        subprocess.run([ff, '-y', '-hide_banner', '-loglevel', 'error', '-ss', str(t), '-i', str(f), '-frames:v', '1', '-vf', 'scale=480:-2', str(p)], check=True)
        tiles.append(Image.open(p).convert('RGB'))
    tw, th = tiles[0].size; cols = 4; sheet = Image.new('RGB', (tw * cols, (th + 24) * ((len(tiles) + cols - 1) // cols)), (18, 18, 18)); dr = ImageDraw.Draw(sheet)
    for i, (im, s) in enumerate(zip(tiles, tl['scenes'])):
        x, y = (i % cols) * tw, (i // cols) * (th + 24); sheet.paste(im, (x, y + 24)); dr.text((x + 6, y + 5), f"{s['id']} @ {pts[i]}s", fill=(235, 235, 235))
    sheet.save(qa / 'final_sheet.jpg', quality=88)
    for p in qa.glob('_fq_*.jpg'): p.unlink()
    rep['sheet'] = str(qa / 'final_sheet.jpg'); rep['pass'] = all(c['ok'] for c in rep['checks'])
    rep['notChecked'] = ['full-length human viewing', 'factual accuracy of narration', 'readability at speed > 1.3x']
    save_json(qa / 'report.json', rep)
    for c in rep['checks']: print(f"{'PASS' if c['ok'] else 'FAIL'}  {c['name']}: {c['detail']}")
    print('sheet:', rep['sheet']); sys.exit(0 if rep['pass'] else 1)

if __name__ == '__main__': main()
