"""Built-in background tracks, fitted to the storyboard.

The default track is mastered to sit under narration: level-matched, slow loudness drift flattened, then ridden by
each scene's mood/energy (same fields as scripts/score.py), faded in/out, and looped with a crossfade when the video
is longer than the track.  Public: TRACKS, resolve(music, route, warn=False), render(name, scenes, energies, dur, gain=1.0).
"""
from __future__ import annotations
import subprocess, sys
import numpy as np
from avs_common import SKILL_DIR, ffmpeg

SR = 48000
TRACKS = {'default': {'file': 'assets/music/vibe-knowledge.mp3', 'title': 'Vibe知识大赏', 'bpm': 112}}
DRAMA_ROUTES = {'ai-comic-drama', 'ai-live-drama'}   # pure AI drama: theme-based synthesized score; hybrid (code animation + AI shots) uses the built-in track
TARGET_DB = -26.0      # track RMS before mood riding; the narration sidechain and final loudnorm sit on top of this
FLATTEN = .7           # share of the track's own loudness drift that is removed (keeps some natural movement)
MOOD_SPAN_DB = 8.0     # climax vs calm difference ~ 5 dB at the defaults

def drama_track_blocked(music, route=None):
    """True when an AI-drama project would silently fall back to the built-in code-animation track.
    The built-in track is only for code animation; AI drama uses a theme-based synthesized score unless the
    user explicitly asked for the built-in music (music.allowBuiltinTrack = true)."""
    m = music or {}
    return route in DRAMA_ROUTES and m.get('track') == 'default' and not m.get('allowBuiltinTrack')

def resolve(music, route=None, warn=False):
    """Which music source a project uses. Priority: user file > explicit style > explicit generate > explicit track > default.
    For AI-drama routes a bare {"track": "default"} is treated as a template accident and switched to the synthesized
    score, unless music.allowBuiltinTrack is explicitly true."""
    m = music or {}
    if m.get('file'): return 'file'
    if m.get('style'): return 'style'
    if m.get('generate'): return 'generate'
    if drama_track_blocked(m, route):
        if warn:
            print('WARN: AI drama route should not use the built-in code-animation BGM; using the synthesized theme score instead. '
                  'If the user explicitly asked for the built-in track, set music.allowBuiltinTrack=true.', file=sys.stderr)
        return 'style'
    if m.get('track'):
        if m['track'] not in TRACKS: raise ValueError(f'unknown track "{m["track"]}"; choose from ' + ', '.join(TRACKS))
        return 'track'
    return 'style' if route in DRAMA_ROUTES else 'track'

def _decode(path):
    raw = subprocess.run([ffmpeg(), '-v', 'error', '-i', str(path), '-f', 'f32le', '-ac', '2', '-ar', str(SR), '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()

def _db(x): return 20 * np.log10(np.sqrt(float((x ** 2).mean())) + 1e-9)

def _flatten(y):
    """Level-match to TARGET_DB and remove most of the slow loudness drift (4 s windows, +-3 dB limit)."""
    w = 4 * SR; m = y.mean(1); n = len(y) // SR + 1; lv = np.array([_db(m[max(0, i * SR - w // 2):i * SR + w // 2]) if len(m[max(0, i * SR - w // 2):i * SR + w // 2]) else -90 for i in range(n)])
    body = lv[lv > lv.max() - 25]; ref = float(np.median(body))
    g = np.clip(-FLATTEN * (lv - ref), -3, 3); g[lv < ref - 12] = 0          # leave the natural tail alone
    gs = np.interp(np.arange(len(y)) / SR, np.arange(n), np.convolve(np.pad(g, 2, mode='edge'), np.ones(5) / 5, 'valid'))
    out = y * (10 ** (gs / 20))[:, None].astype(np.float32)
    return out * np.float32(10 ** ((TARGET_DB - _db(out[:int(len(out) * .95)])) / 20))

def _loop(y, n, xfade=3 * SR):
    if len(y) >= n: return y[:n].copy()
    out = np.zeros((n, 2), np.float32); step = len(y) - xfade; k = 0
    while k * step < n:
        seg = y.copy()
        if k > 0: seg[:xfade] *= np.linspace(0, 1, xfade, dtype=np.float32)[:, None]
        if (k + 1) * step < n: seg[-xfade:] *= np.linspace(1, 0, xfade, dtype=np.float32)[:, None]
        a = k * step; b = min(n, a + len(seg)); out[a:b] += seg[:b - a]; k += 1
    return out

def _ride(n, scenes, energies, gain):
    """Per-sample gain (linear): each scene's energy sets its level, silent scenes drop out, changes ramp over ~1.5 s."""
    hz = 50; t = np.arange(int(n / SR * hz) + 1) / hz; db = np.zeros(len(t))
    for s, e in zip(scenes, energies):
        sel = (t >= s['ns'] - 1e-9) & (t < s['ns'] + s['nd']); db[sel] = -40.0 if e <= 0 else (e - .6) * MOOD_SPAN_DB
    k = int(1.5 * hz); sm = np.convolve(np.pad(db, k, mode='edge'), np.ones(k) / k, 'same')[k:-k]
    return (10 ** (np.interp(np.arange(n) / SR, t, sm) / 20) * gain).astype(np.float32)

def render(name, scenes, energies, dur, gain=1.0):
    """-> (bed float32[n,2] with the same length convention as score.render, info)."""
    spec = TRACKS[name]; n = int(SR * (dur + 1))
    y = _flatten(_decode(SKILL_DIR / spec['file'])); bed = _loop(y, n) * _ride(n, scenes, energies, float(gain))[:, None]
    end = int(dur * SR); fi = int(1.2 * SR); fo = int(2.5 * SR)
    bed[:fi] *= np.linspace(0, 1, fi, dtype=np.float32)[:, None]; bed[max(0, end - fo):end] *= np.linspace(1, 0, end - max(0, end - fo), dtype=np.float32)[:, None]; bed[end:] = 0
    pk = float(np.abs(bed).max())
    if pk > .85: bed *= .85 / pk
    return bed.astype(np.float32), {'style': f'track:{name}', 'track': spec['title'], 'bpm': spec['bpm'], 'seed': None, 'chords': None, 'energies': energies}