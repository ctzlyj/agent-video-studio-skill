"""Delivery finalizer: loudness-normalise the rendered MP4, verify it, and write the deliverables.

  python scripts/finalize.py [project] [--file out/x.mp4] [--lufs -16] [--no-bgm-version]

Writes to <project>/deliver/ (nothing is written unless every check passes):
  <title>.mp4              master: video stream copied, audio two-pass loudnorm to the target, AAC 192k
  <title>_nobgm.mp4        same picture with narration + sfx only (for re-scoring later); needs audio/vo_sfx.wav from audio.py
  <title>.srt              sentence-level subtitles from timeline.json (speed-mapped)
  <title>_delivery.json    measured numbers: loudness, true peak, decode errors, black / freeze events
Checks (refuse to publish on failure): integrated loudness within +-0.7 LU of target, true peak <= -1.0 dBTP,
full decode with no errors, duration within 0.5 s of the timeline, no mid-video black gap.
Freeze events are reported (not failures): a still shot can be intentional; check each against the storyboard.
"""
from __future__ import annotations
import argparse, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
from avs_common import project_dir, load_json, save_json, ffmpeg, media_duration

TOL_LU = 0.7; MAX_TP = -1.0

def _run(cmd): return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding='utf-8', errors='ignore')

def measure(ff, f):
    """Two numbers from ebur128: integrated loudness (LUFS) and true peak (dBTP)."""
    r = _run([ff, '-hide_banner', '-nostats', '-i', f, '-vn', '-af', 'ebur128=peak=true', '-f', 'null', '-']).stderr
    tail = r[r.rfind('Summary:'):] if 'Summary:' in r else r
    i = re.search(r'I:\s+(-?[\d.]+) LUFS', tail); p = re.search(r'Peak:\s+(-?[\d.]+) dBFS', tail)
    if not i: raise RuntimeError('cannot measure loudness (no audio?)')
    return float(i[1]), (float(p[1]) if p else 0.0)

def normalise_audio(ff, src, dst, target, tmp):
    """Two-pass loudnorm on the audio of src -> aac in dst (video copied)."""
    r = _run([ff, '-hide_banner', '-nostats', '-i', src, '-vn', '-af', f'loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-']).stderr
    m = re.search(r'\{[^{}]*"input_i"[^{}]*\}', r, re.S)
    if not m: raise RuntimeError('loudnorm analysis failed')
    j = json.loads(m[0])
    af = (f"loudnorm=I={target}:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}"
          f":measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    wav = Path(tmp) / 'norm.wav'
    p = _run([ff, '-y', '-hide_banner', '-loglevel', 'error', '-i', src, '-vn', '-af', af, '-ar', '48000', '-ac', '2', wav])
    if p.returncode: raise RuntimeError(p.stderr[-300:])
    p = _run([ff, '-y', '-hide_banner', '-loglevel', 'error', '-i', src, '-i', wav, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', dst])
    if p.returncode: raise RuntimeError(p.stderr[-300:])

def decode_errors(ff, f):
    r = _run([ff, '-v', 'error', '-i', f, '-f', 'null', '-'])
    return [l for l in r.stderr.splitlines() if l.strip()]

def events(ff, f):
    bd = _run([ff, '-hide_banner', '-i', f, '-vf', 'blackdetect=d=0.8:pix_th=0.06', '-an', '-f', 'null', '-']).stderr
    fz = _run([ff, '-hide_banner', '-i', f, '-vf', 'freezedetect=n=0.001:d=3', '-an', '-f', 'null', '-']).stderr
    blacks = [(float(a), float(b)) for a, b in re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', bd)]
    starts = [float(x) for x in re.findall(r'freeze_start: ([\d.]+)', fz)]; durs = [float(x) for x in re.findall(r'freeze_duration: ([\d.]+)', fz)]
    return blacks, [{'start': s, 'duration': (durs[i] if i < len(durs) else None)} for i, s in enumerate(starts)]

def _ts(t):
    t = max(0.0, t); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f'{h:02d}:{m:02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}'.replace(',1000', ',999')

def srt_text(tl):
    subs = [s for s in tl.get('subs', []) if s.get('text')]
    return ''.join(f"{i}\n{_ts(s['s'])} --> {_ts(s['e'])}\n{s['text']}\n\n" for i, s in enumerate(subs, 1))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); ap.add_argument('project', nargs='?'); ap.add_argument('--file')
    ap.add_argument('--lufs', type=float, default=-16.0); ap.add_argument('--no-bgm-version', action='store_true'); a = ap.parse_args()
    if not -30 <= a.lufs <= -8: sys.exit('--lufs must be between -30 and -8')
    d = project_dir(a.project); tl = load_json(d / 'timeline.json'); p = load_json(d / 'project.json'); ff = ffmpeg()
    from render import safe_name
    src = Path(a.file) if a.file else max((x for x in (d / 'out').glob('*.mp4') if not x.name.startswith('preview')), key=lambda x: x.stat().st_mtime, default=None)
    if not src or not src.exists(): sys.exit('no final render found in out/. Run build.py --final first.')
    stem = safe_name(p.get('title', 'video')); dest = d / 'deliver'
    for n in (f'{stem}.mp4', f'{stem}_nobgm.mp4', f'{stem}.srt', f'{stem}_delivery.json'):
        if (dest / n).exists(): sys.exit(f'refusing to overwrite deliver/{n}; fork a new version (new_project.py --version) or remove it yourself')
    rep = {'source': src.name, 'targetLUFS': a.lufs, 'checks': []}
    def chk(name, ok, detail): rep['checks'].append({'name': name, 'ok': bool(ok), 'detail': detail})
    with tempfile.TemporaryDirectory(prefix='avs_fin_') as tmp:
        master = Path(tmp) / 'master.mp4'; normalise_audio(ff, src, master, a.lufs, tmp)
        li, tp = measure(ff, master); chk('integrated loudness', abs(li - a.lufs) <= TOL_LU, f'{li:.1f} LUFS (target {a.lufs} +-{TOL_LU})'); chk('true peak', tp <= MAX_TP, f'{tp:.1f} dBTP (max {MAX_TP})')
        errs = decode_errors(ff, master); chk('full decode', not errs, 'no errors' if not errs else f'{len(errs)} error line(s): {errs[:2]}')
        dur = media_duration(master); chk('duration', abs(dur - tl['duration']) < 0.5, f'{dur:.2f}s vs timeline {tl["duration"]:.2f}s')
        blacks, freezes = events(ff, master); mid = [b for b in blacks if b[0] > 0.5 and b[1] < dur - 0.5]
        chk('no black gaps', not mid, 'none' if not mid else f'{mid[:4]}'); rep['freezeEvents'] = freezes
        rep['loudness'] = {'integrated': li, 'truePeak': tp}; rep['duration'] = round(dur, 2)
        nob = None; vs = d / 'audio' / 'vo_sfx.wav'
        if not a.no_bgm_version:
            if vs.exists():
                nob = Path(tmp) / 'nobgm.mp4'; vs_norm = Path(tmp) / 'vs_norm.mp4'
                p1 = _run([ff, '-y', '-hide_banner', '-loglevel', 'error', '-i', src, '-i', vs, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', vs_norm])
                if p1.returncode == 0:
                    normalise_audio(ff, vs_norm, nob, a.lufs, tmp); l2, t2 = measure(ff, nob); chk('no-BGM version loudness / peak', abs(l2 - a.lufs) <= 1.5 and t2 <= MAX_TP, f'{l2:.1f} LUFS, {t2:.1f} dBTP')
                else: nob = None; chk('no-BGM version', False, p1.stderr[-200:])
            else: rep['noBgmVersion'] = 'skipped: audio/vo_sfx.wav missing (run build.py --final again)'
        rep['pass'] = all(c['ok'] for c in rep['checks'])
        for c in rep['checks']: print(f"{'PASS' if c['ok'] else 'FAIL'}  {c['name']}: {c['detail']}")
        if rep['freezeEvents']: print(f"INFO  {len(rep['freezeEvents'])} still segment(s) >3 s at {[round(f['start'], 1) for f in rep['freezeEvents'][:6]]}s: confirm each is an intentional hold")
        if not rep['pass']: print('nothing published. fix the failing check(s) and rerun.'); sys.exit(1)
        dest.mkdir(exist_ok=True); shutil.copy(master, dest / f'{stem}.mp4')
        if nob and nob.exists(): shutil.copy(nob, dest / f'{stem}_nobgm.mp4')
        (dest / f'{stem}.srt').write_text(srt_text(tl), encoding='utf-8')
        rep['files'] = sorted(x.name for x in dest.glob(f'{stem}*')) + [f'{stem}_delivery.json']
        rep['notChecked'] = ['full-length human viewing', 'factual accuracy of narration', 'audio/picture sync by ear']; save_json(dest / f'{stem}_delivery.json', rep)
    print('delivered:', *[f'deliver/{n}' for n in rep['files']], sep='\n  ')

if __name__ == '__main__': main()