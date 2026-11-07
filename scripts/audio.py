"""Music bed + sfx + narration mix, following the (speed-mapped) timeline.
music: {"style": "auto"|"warm"|"bright"|"tech"|"cinematic"|"ambient"|"suspense", "bpm": 90, "key": "D minor", "seed": 7}
         mood-driven score that follows each scene's "mood"/"energy" (see scripts/score.py)
       {"file": "assets/music.mp3"} (licensed track) | {"generate": "ambient"|"pulse"|"none"} (legacy plain bed)
sfx in scenes: "sfx": [[0.8, "tick"], [3.2, "ok"]]  (scene-local 1x seconds)
"""
from __future__ import annotations
import argparse, os, sys, wave
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from avs_common import project_dir, load_json, save_json, ffmpeg, run
import score as scoremod

SR = 48000
def _env(x, a=.01, r=.4): return np.minimum(1, x / a) * np.exp(-x / r)

def music_bed(kind, dur, seed=7):
    n = int(SR * (dur + 1)); out = np.zeros((n, 2), np.float32); rng = np.random.default_rng(seed)
    def add(st, y, g=1.0, pan=0.0):
        i = int(st * SR); j = min(n, i + len(y))
        if j > i: y = y[:j - i] * g; out[i:j, 0] += y * (1 - pan) * .75; out[i:j, 1] += y * (1 + pan) * .75
    if kind == 'none': return out
    chords = [[50, 57, 62, 65], [46, 53, 58, 62], [43, 50, 55, 58], [45, 52, 57, 61]]
    for k, s in enumerate(np.arange(0, dur, 4.0)):
        ln = min(4.8, dur - s + 1); tt = np.arange(int(ln * SR)) / SR
        a = np.minimum(1, tt / 1.2) * np.minimum(1, np.maximum(0, (ln - tt) / 1.0))
        y = sum(np.sin(2 * np.pi * 440 * 2 ** ((m - 69) / 12) * tt + .3 * np.sin(2 * np.pi * .15 * tt)) for m in chords[k % 4]) / 4
        add(s, y * a, .10)
    if kind == 'pulse':
        for s in np.arange(0, dur, .5):
            tt = np.arange(int(.22 * SR)) / SR
            add(s, np.sin(2 * np.pi * (55 + 20 * np.exp(-tt * 25)) * tt) * _env(tt, .003, .08), .15 if int(s * 2) % 2 == 0 else .07)
    return out

def sfx_wave(kind, rng):
    if kind == 'tick': tt = np.arange(int(.12 * SR)) / SR; return np.sin(2 * np.pi * 1600 * tt) * _env(tt, .002, .025) * .9, .12
    if kind == 'ok': tt = np.arange(int(.35 * SR)) / SR; return (np.sin(2 * np.pi * 880 * tt) + .6 * np.sin(2 * np.pi * 1320 * tt)) * _env(tt, .005, .12), .10
    if kind == 'alert': tt = np.arange(int(.75 * SR)) / SR; return np.sin(2 * np.pi * (440 + 80 * np.sin(2 * np.pi * 8 * tt)) * tt) * _env(tt, .01, .25), .11
    if kind == 'whoosh': tt = np.arange(int(.55 * SR)) / SR; y = np.convolve(rng.normal(0, 1, len(tt)), np.ones(80) / 80, 'same') * np.sin(np.pi * tt / .55); return y, .08
    if kind == 'boom': tt = np.arange(int(1.2 * SR)) / SR; return np.sin(2 * np.pi * (60 + 40 * np.exp(-tt * 6)) * tt) * _env(tt, .005, .5), .2
    if kind == 'pop': tt = np.arange(int(.14 * SR)) / SR; return np.sin(2 * np.pi * (300 + 700 * np.exp(-tt * 40)) * tt) * _env(tt, .001, .04), .16
    if kind == 'click': tt = np.arange(int(.05 * SR)) / SR; return np.convolve(rng.normal(0, 1, len(tt)), np.array([1, -1]), 'same') * _env(tt, .0005, .008), .12
    if kind == 'swell': tt = np.arange(int(1.4 * SR)) / SR; return np.sin(2 * np.pi * 220 * tt) * np.sin(np.pi * tt / 1.4) ** 2 * .6, .09
    raise ValueError(f'unknown sfx {kind}')

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('project', nargs='?'); a = ap.parse_args()
    d = project_dir(a.project); p = load_json(d / 'project.json'); tl = load_json(d / 'timeline.json'); dur = tl['duration']
    ad = d / 'audio'; ad.mkdir(exist_ok=True); m = p.get('music') or {'generate': 'ambient'}; rng = np.random.default_rng(3)
    scenes = {s['id']: s for s in p['scenes']}
    if m.get('file'): bed = music_bed('none', dur)
    elif m.get('style'):
        style = scoremod.pick_style(m['style'], p.get('route')); tonic, mode = scoremod.parse_key(m.get('key'))
        en = scoremod.energies_for([scenes[s['id']] for s in tl['scenes']])
        bed, info = scoremod.render(style, tl['scenes'], en, dur, bpm=m.get('bpm'), tonic=tonic, mode=mode, seed=int(m.get('seed', 7)))
        rep = scoremod.analyze(bed, tl['scenes'], en); rep.update(info); rep['sceneIds'] = [s['id'] for s in tl['scenes']]; save_json(ad / 'score_report.json', rep)
        print(f"score: {style} {info['bpm']:.0f} bpm, {info['chords']} chord changes, energy {[round(x, 2) for x in en]}, scene dB {rep['sceneRmsDb']}")
        if not (rep['noClip'] and rep['arcOk']): print(f"WARN score check: noClip={rep['noClip']} arcOk={rep['arcOk']} ({rep['arcNote']})")
    else: bed = music_bed(m.get('generate', 'ambient'), dur)
    for s in tl['scenes']:
        cues = list(scenes[s['id']].get('sfx') or [])
        if (p.get('sfx') or {}).get('transitions', True) and s['ns'] > 0: cues.append([0.02, 'whoosh'])
        for off, kind in cues:
            y, g = sfx_wave(kind, rng); st = s['ns'] + float(off) / s['speed']; i = int(st * SR); j = min(len(bed), i + len(y))
            if j > i: bed[i:j, 0] += y[:j - i] * g; bed[i:j, 1] += y[:j - i] * g
    with wave.open(str(ad / 'bed.wav'), 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(bed * .75, -1, 1) * 32767).astype('<i2').tobytes())
    inputs = ['-i', str(ad / 'bed.wav')]; filt = []; k = 0
    if m.get('file'):
        inputs += ['-stream_loop', '-1', '-i', str(d / m['file'])]; k += 1
        filt.append(f"[{k}:a]atrim=0:{dur},afade=t=out:st={max(0, dur - 2.5)}:d=2.5,volume={m.get('volume', .5)}[mus]")
    vos = []
    for s in tl['scenes']:  # clip audio: generated dialogue / ambience carried by a video asset
        sc = scenes[s['id']]
        if not sc.get('clipAudio'): continue
        src = (p.get('videos') or {}).get(sc['clipAudio'], {}); src = src.get('src') if isinstance(src, dict) else src
        k += 1; inputs += ['-i', str(d / src)]; dl = int(s['ns'] * 1000)
        tempo = f"atempo={s['speed']}," if abs(s['speed'] - 1) > 1e-3 else ''
        filt.append(f"[{k}:a]aresample=48000,{tempo}atrim=0:{s['nd']},adelay={dl}|{dl},volume={sc.get('clipGain', 1.0)}[v{k}]"); vos.append(f'[v{k}]')
    for s in tl['scenes']:
        wav = ad / 'vo' / f"{s['id']}.wav"
        if s['voDur'] <= 0 or not wav.exists(): continue
        k += 1; inputs += ['-i', str(wav)]; dl = int((s['ns'] + s['voStart'] / s['speed']) * 1000)
        tempo = f"atempo={s['speed']}," if abs(s['speed'] - 1) > 1e-3 else ''
        filt.append(f"[{k}:a]{tempo}adelay={dl}|{dl},volume={(p.get('voice') or {}).get('gain', 1.15)}[v{k}]"); vos.append(f'[v{k}]')
    bg = '[0:a]' if not m.get('file') else '[0:a][mus]amix=inputs=2:normalize=0[bgm];[bgm]'
    if vos:
        fc = ';'.join(filt + [f"{''.join(vos)}amix=inputs={len(vos)}:normalize=0:duration=longest,apad=whole_dur={dur}[vo]", f"{bg}volume=.62,apad=whole_dur={dur}[bg]",
              "[vo]asplit=2[vo1][vo2]", "[bg][vo1]sidechaincompress=threshold=0.035:ratio=6:attack=20:release=350[duck]",
              f"[duck][vo2]amix=inputs=2:normalize=0:duration=longest,alimiter=limit=0.92,atrim=0:{dur}[mix]"])
    else:
        fc = ';'.join(filt + [f"{bg}alimiter=limit=0.92,atrim=0:{dur}[mix]"])
    run([ffmpeg(), '-y', '-hide_banner', '-loglevel', 'error', *inputs, '-filter_complex', fc, '-map', '[mix]', '-ar', str(SR), '-ac', '2', ad / 'mix_raw.wav'])
    run([ffmpeg(), '-y', '-hide_banner', '-loglevel', 'error', '-i', ad / 'mix_raw.wav', '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-ar', str(SR), ad / 'mix.wav'])
    print(f'audio ok: {dur:.2f}s')

if __name__ == '__main__': main()

