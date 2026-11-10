"""Objective first-pass screen for AI-drama music candidates.

  python scripts/music_screen.py candidate.mp3 --expect-mode major --bpm-min 100 --bpm-max 135 --centroid-min 1200

Uses librosa: chroma + Krumhansl key profiles for a rough key/mode estimate, beat tracking for BPM, and mean spectral
centroid as a brightness proxy. This is a coarse filter, NOT a substitute for listening: it cannot judge melody,
arrangement, whether the music fits the story, or whether the vocal sits under narration.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np

KEYS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

def _corr(a, b):
    a = a - a.mean(); b = b - b.mean()
    return float((a @ b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

def analyze(path):
    import librosa
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    if len(y) == 0: raise ValueError('empty audio')
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr).mean(axis=1)
    best = (-9, 0, 'major')
    for tonic in range(12):
        v = np.roll(chroma, -tonic)
        for mode, prof in (('major', MAJOR), ('minor', MINOR)):
            score = _corr(v, prof)
            if score > best[0]: best = (score, tonic, mode)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0])
    centroid = float(librosa.feature.spectral_centroid(y=y, sr=sr).mean())
    dur = len(y) / sr
    brightness = 'bright' if centroid >= 1800 else ('dark' if centroid < 1000 else 'mid')
    return {'file': str(path), 'duration': round(dur, 2), 'bpm': round(bpm, 1), 'key': f'{KEYS[best[1]]} {best[2]}',
            'mode': best[2], 'keyConfidence': round(best[0], 3), 'spectralCentroidHz': round(centroid),
            'brightness': brightness}

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file'); ap.add_argument('--expect-mode', choices=['major', 'minor'])
    ap.add_argument('--bpm-min', type=float); ap.add_argument('--bpm-max', type=float)
    ap.add_argument('--centroid-min', type=float); ap.add_argument('--centroid-max', type=float)
    ap.add_argument('--json'); a = ap.parse_args()
    try: r = analyze(a.file)
    except Exception as e: sys.exit(f'cannot analyse {a.file}: {e}')
    checks = {}
    if a.expect_mode: checks['mode'] = r['mode'] == a.expect_mode
    if a.bpm_min is not None: checks['bpm_min'] = r['bpm'] >= a.bpm_min
    if a.bpm_max is not None: checks['bpm_max'] = r['bpm'] <= a.bpm_max
    if a.centroid_min is not None: checks['centroid_min'] = r['spectralCentroidHz'] >= a.centroid_min
    if a.centroid_max is not None: checks['centroid_max'] = r['spectralCentroidHz'] <= a.centroid_max
    r['checks'] = checks; r['pass'] = all(checks.values()) if checks else True
    text = json.dumps(r, ensure_ascii=False, indent=2)
    if a.json: Path(a.json).write_text(text, encoding='utf-8')
    print(text)
    print('NOTE: key/mode/BPM/brightness are rough estimates; always audition the file before choosing it.')
    sys.exit(0 if r['pass'] else 1)

if __name__ == '__main__': main()