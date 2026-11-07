"""Mood-driven score engine: a soundtrack composed from the storyboard, pure numpy (no samples, no model).

Each scene carries a mood/energy; the score follows it:
  * harmony  - one chord progression per style; the chord changes at scene cuts (and every few bars inside long
               scenes). Voicings are chosen nearest the previous chord, so a change is voice-leading, not a new piece.
  * layers   - pad always; bass from energy .3; arpeggio/bells from .2; kick/hat/clap from style thresholds.
  * accents  - a low hit on a cut into a high-energy scene.
  * space    - one convolution reverb on the tonal bus, deterministic seed, fade-out at the end.
Public: render(style, scenes, energies, dur, ...) -> (bed[n,2] float32, info);  energies_for(scenes);  analyze(...).
"""
from __future__ import annotations
import math
import numpy as np

SR = 48000
MOODS = {'silent': 0.0, 'calm': 0.25, 'build': 0.55, 'climax': 0.9, 'resolve': 0.3}
MODES = {'major': [0, 2, 4, 5, 7, 9, 11], 'minor': [0, 2, 3, 5, 7, 8, 10],
         'dorian': [0, 2, 3, 5, 7, 9, 10], 'phrygian': [0, 1, 3, 5, 7, 8, 10]}
PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}

STYLES = {
    'warm': dict(desc='温暖钢琴/电钢琴琶音，轻鼓点；汇报、品牌、人物、回顾', bpm=84, tonic='C', mode='major', prog=[0, 5, 3, 4], seventh=True,
                 chord_bars=2, pad=(5, 2.0, 1.0), lead='pluck', lead_div=2, lead_gain=.9, bass=None,
                 kick='x.......x.......', kick_at=.6, hat='x.x.x.x.x.x.x.x.', hat_at=.8, clap='', clap_at=2, reverb=.22),
    'bright': dict(desc='明亮有活力，四拍鼓点；发布会、促销、产品宣传', bpm=118, tonic='G', mode='major', prog=[0, 4, 5, 3], seventh=False,
                   chord_bars=2, pad=(5, 1.6, .5), lead='pluck', lead_div=2, lead_gain=1.0, bass='x.x.x.x.x.x.x.x.',
                   kick='x...x...x...x...', kick_at=.45, hat='..x...x...x...x.', hat_at=.55, clap='....x.......x...', clap_at=.7, reverb=.14),
    'tech': dict(desc='科技感，脉冲低音和方波短音；AI、数据、产品演示', bpm=100, tonic='A', mode='minor', prog=[0, 5, 2, 6], seventh=False,
                 chord_bars=2, pad=(4, 1.5, .8), lead='square', lead_div=2, lead_gain=.8, bass='x.xxx.xxx.xxx.xx',
                 kick='x...x...x...x...', kick_at=.5, hat='x.x.x.x.x.x.x.x.', hat_at=.65, clap='....x.......x...', clap_at=.85, reverb=.12),
    'cinematic': dict(desc='史诗厚重，弦乐感长音加定音鼓；纪录片、发展史、大事记', bpm=72, tonic='D', mode='minor', prog=[0, 5, 3, 4], seventh=False,
                      chord_bars=2, pad=(8, 1.2, 1.6), lead='bell', lead_div=.5, lead_gain=.8, bass=None,
                      kick='x...............', kick_at=.55, hat='', hat_at=2, clap='', clap_at=2, boom='x.......x...x...', boom_at=.85, reverb=.3),
    'ambient': dict(desc='极简氛围，几乎无节奏；知识讲解、科普、冥想感', bpm=60, tonic='C', mode='major', prog=[0, 3, 5, 4], seventh=True,
                    chord_bars=4, pad=(4, 2.2, 1.8), lead='bell', lead_div=.5, lead_gain=.6, bass=None,
                    kick='', kick_at=2, hat='', hat_at=2, clap='', clap_at=2, reverb=.35),
    'suspense': dict(desc='紧张悬疑，低频心跳和不协和和弦；揭秘、问题、危机', bpm=90, tonic='E', mode='phrygian', prog=[0, 1, 0, 6], seventh=False,
                     chord_bars=2, pad=(6, 1.3, 1.2), lead='bell', lead_div=1, lead_gain=.5, bass=None,
                     kick='x.x.............', kick_at=.3, hat='', hat_at=2, clap='', clap_at=2, reverb=.28),
}

def _t(n, dur): return np.arange(int(n * dur)) / n

def energies_for(scenes):
    """Per-scene energy 0..1. Scene keys: "energy": 0-1 or "mood": silent|calm|build|climax|resolve. Missing -> position arc."""
    n = len(scenes); out = []
    for i, sc in enumerate(scenes):
        if sc.get('energy') is not None: e = float(sc['energy'])
        elif sc.get('mood') in MOODS: e = MOODS[sc['mood']]
        else:
            x = i / (n - 1) if n > 1 else .5
            e = float(np.interp(x, [0, .12, .75, .88, 1], [.3, .4, .8, .5, .3]))
        out.append(min(1.0, max(0.0, e)))
    return out

def _nearest(pc, center): c = int(round(center)); m = c + ((pc - c + 6) % 12 - 6); return m

def chord_pcs(tonic, mode, deg, seventh):
    sc = MODES[mode]; idx = [deg, deg + 2, deg + 4] + ([deg + 6] if seventh else [])
    return [(tonic + sc[i % 7]) % 12 for i in idx]

def voicings(style, tonic, mode, count):
    """List of chord voicings (midi, sorted); each is placed nearest the previous one (voice-leading)."""
    st = STYLES[style]; out = []; center = 58
    for k in range(count):
        pcs = chord_pcs(tonic, mode, st['prog'][k % len(st['prog'])], st['seventh'])
        v = sorted(_nearest(pc, center) for pc in pcs); out.append(v); center = min(62, max(54, sum(v) / len(v)))
    return out

def _reverb(x, mix, seed):
    if mix <= 0: return x * 0
    rng = np.random.default_rng(seed); L = int(1.8 * SR); tt = np.arange(L) / SR
    ir = [rng.normal(0, 1, L) * np.exp(-tt / .55) for _ in range(2)]
    for c in ir: c[: int(.02 * SR)] *= np.linspace(0, 1, int(.02 * SR)); c /= np.sqrt((c ** 2).sum()) + 1e-9
    B = 1 << 16; N = 1 << 18; out = np.zeros_like(x); H = [np.fft.rfft(c, N) for c in ir]
    for ch in (0, 1):
        for i in range(0, len(x), B):
            blk = x[i:i + B, ch].astype(np.float64)
            y = np.fft.irfft(np.fft.rfft(blk, N) * H[ch], N)[:len(blk) + L - 1]; j = min(len(out), i + len(y)); out[i:j, ch] += y[:j - i]
    return out.astype(np.float32)

# ---- voices (all return mono float arrays) ----
def v_pad(f, ln, nh, roll, atk, rel=1.4):
    t = _t(SR, ln + rel).astype(np.float32); y = np.zeros_like(t)
    for d in (-.0035, .0035):
        ph = 2 * np.pi * f * (1 + d) * t
        for k in range(1, nh + 1): y += np.sin(k * ph + k * .7) / k ** roll
    env = np.minimum(1, t / atk) * np.minimum(1, np.maximum(0, (ln + rel - t) / rel))
    return y * env / (nh ** .25 * 2.4)
def v_pluck(f, kind='pluck'):
    dur = 1.4 if kind == 'bell' else 1.0; t = _t(SR, dur).astype(np.float32)
    if kind == 'square':
        y = sum(np.sin(2 * np.pi * f * k * t) / k for k in (1, 3, 5, 7)); return (y * np.exp(-t / .16) * np.minimum(1, t / .003) * .5).astype(np.float32)
    if kind == 'bell':
        y = np.sin(2 * np.pi * f * t + 1.6 * np.exp(-t * 5) * np.sin(2 * np.pi * f * 1.4 * t)); return (y * np.exp(-t / .55) * np.minimum(1, t / .004) * .6).astype(np.float32)
    y = sum(np.sin(2 * np.pi * f * k * t) * np.exp(-t * (3 + 3.5 * k)) / k ** 1.2 for k in range(1, 6))
    return (y * np.minimum(1, t / .003) * 1.1).astype(np.float32)
def v_bass(f, ln):
    t = _t(SR, ln).astype(np.float32); y = np.sin(2 * np.pi * f * t) + .3 * np.sin(4 * np.pi * f * t)
    return y * np.minimum(1, t / .02) * np.minimum(1, np.maximum(0, (ln - t) / .25)) * .55
def v_kick(rng):
    t = _t(SR, .32).astype(np.float32); return np.sin(2 * np.pi * np.cumsum(48 + 110 * np.exp(-t * 30)) / SR) * np.exp(-t / .11) * np.minimum(1, t / .002)
def v_hat(rng):
    t = _t(SR, .06).astype(np.float32); n = rng.normal(0, 1, len(t)); return np.diff(n, prepend=0).astype(np.float32) * np.exp(-t / .012) * .35
def v_clap(rng):
    t = _t(SR, .22).astype(np.float32); n = np.diff(rng.normal(0, 1, len(t)), prepend=0).astype(np.float32); y = np.zeros_like(t)
    for off in (0, .012, .026): i = int(off * SR); y[i:] += n[:len(t) - i] * np.exp(-t[:len(t) - i] / (.012 if off < .02 else .07))
    return y * .3
def v_boom(f, rng):
    t = _t(SR, 1.5).astype(np.float32); y = np.sin(2 * np.pi * np.cumsum(f * (1 + .6 * np.exp(-t * 12))) / SR) * np.exp(-t / .55)
    return (y + np.convolve(rng.normal(0, 1, len(t)), np.ones(40) / 40, 'same') * np.exp(-t / .12) * .3) * np.minimum(1, t / .003)

def render(style, scenes, energies, dur, bpm=None, tonic=None, mode=None, seed=7):
    """scenes: [{'ns': start_s, 'nd': length_s}] on the final (speed-mapped) timeline. Returns (bed float32[n,2], info)."""
    st = STYLES[style]; rng = np.random.default_rng(seed); n = int(SR * (dur + 1))
    bpm = float(bpm or st['bpm']); beat = 60 / bpm; bar = 4 * beat
    tonic = PC[tonic[0].upper()] + (1 if '#' in tonic else -1 if len(tonic) > 1 and tonic[1] == 'b' else 0) if tonic else PC[st['tonic']]
    mode = mode or st['mode']
    starts = [s['ns'] for s in scenes]; ends = [s['ns'] + s['nd'] for s in scenes]
    def scene_at(t):
        for i in range(len(scenes) - 1, -1, -1):
            if t >= starts[i] - 1e-6: return i
        return 0
    def e_at(t): return energies[scene_at(min(t, dur - 1e-3))]
    # change points: every scene start (>=half a bar apart) + bar grid inside long scenes (>=1 bar from other points)
    pts = []
    for s in starts:
        if not pts or s - pts[-1] >= bar / 2: pts.append(s)
    pts[0] = 0.0
    grid = [k * bar * st['chord_bars'] for k in range(1, int(dur / (bar * st['chord_bars'])) + 1)]
    for g in grid:
        if all(abs(g - p) >= bar for p in pts) and g < dur - bar: pts.append(g)
    pts = sorted(pts); segs = [(p, (pts[i + 1] if i + 1 < len(pts) else dur)) for i, p in enumerate(pts)]
    vs = voicings(style, tonic, mode, len(segs)); wet = np.zeros((n, 2), np.float32); dry = np.zeros((n, 2), np.float32)
    def put(buf, t0, y, g=1.0, pan=0.0):
        i = int(t0 * SR); j = min(n, i + len(y))
        if i < 0 or j <= i: return
        y = y[:j - i] * g; buf[i:j, 0] += y * (1 - pan) * .75; buf[i:j, 1] += y * (1 + pan) * .75
    hz = lambda m: 440.0 * 2 ** ((m - 69) / 12)
    nh, roll, atk = st['pad']; step_idx = 0
    for (a, b), v in zip(segs, vs):
        e = e_at(a + .01)
        if e <= 0: continue
        for m in v: put(wet, a, v_pad(hz(m), b - a + .3, nh, roll, atk), (.55 + .45 * e) * .24, (m - 58) / 40)
        if e >= .3:
            root = 36 + ((v[0] - 36) % 12)
            if st['bass']:
                for k in range(int((b - a) / (beat / 4))):
                    if st['bass'][k % 16] == 'x': put(dry, a + k * beat / 4, v_bass(hz(root), .2), (.35 + .45 * e) * .7)
            else: put(dry, a, v_bass(hz(root), b - a + .2), (.3 + .45 * e) * .6)
        if e >= .2 and st['lead_div'] > 0:  # arpeggio / bells over the chord tones, thinned when calm
            pool = sorted({m + 12 for m in v} | {m + 24 for m in v} | {m + 36 for m in v[:2]}); seq = pool + pool[-2:0:-1]; sl = beat / st['lead_div']
            k0 = int(math.ceil(a / sl)); k = k0
            while k * sl < b - .05:
                t0 = k * sl
                if rng.random() < (.3 + .7 * e) and (e >= .4 or k % 2 == 0):
                    put(wet, t0, v_pluck(hz(seq[step_idx % len(seq)]), st['lead']), st['lead_gain'] * (.25 + .6 * e) * 1.25, ((step_idx % 4) - 1.5) / 6)
                step_idx += 1; k += 1
    # drums on the global 16th grid, gated by energy at each step
    steps = int(dur / (beat / 4)); K = v_kick(rng); H = v_hat(rng); C = v_clap(rng); BM = v_boom(48, rng)
    for k in range(steps):
        t0 = k * beat / 4; e = e_at(t0); s = k % 16
        if e <= 0: continue
        if st['kick'] and st['kick'][s] == 'x' and e >= st['kick_at']: put(dry, t0, K if style != 'cinematic' else BM, (.5 + .4 * e) * (.8 if style == 'suspense' else 1))
        if st['hat'] and st['hat'][s] == 'x' and e >= st['hat_at']: put(dry, t0, H, .6 + .4 * e, .25 if k % 2 else -.25)
        if st['clap'] and st['clap'][s] == 'x' and e >= st['clap_at']: put(dry, t0, C, .6 + .4 * e)
        if st.get('boom') and st['boom'][s] == 'x' and e >= st['boom_at']: put(dry, t0, BM, .5 * e)
    for i in range(1, len(scenes)):  # accent on a cut into a high-energy scene
        if energies[i] >= .75 and energies[i] - energies[i - 1] >= .15: put(dry, starts[i], v_boom(45 + 5 * (tonic % 12) / 12 * 3, rng), .6)
    bed = wet * (1 - st['reverb'] * .5) + _reverb(wet, st['reverb'], seed + 11) * 1.4 + dry
    fo = int(2.5 * SR); end = int(dur * SR); i0 = max(0, end - fo)
    bed[i0:end] *= np.linspace(1, 0, end - i0)[:, None].astype(np.float32); bed[end:] = 0
    rms = float(np.sqrt((bed[:end] ** 2).mean())) + 1e-9; bed *= min(.032 / rms, .85 / (np.abs(bed).max() + 1e-9))
    info = {'style': style, 'bpm': bpm, 'tonic': int(tonic), 'mode': mode, 'seed': seed, 'chords': len(segs), 'energies': energies}
    return bed.astype(np.float32), info

def analyze(bed, scenes, energies):
    """Per-scene RMS (dB) + checks: no clipping, and the loudest-mood scene is >=1.5 dB above the quietest when moods differ by >=.3."""
    lv = []
    for s in scenes:
        a = int(s['ns'] * SR); b = int((s['ns'] + s['nd']) * SR); seg = bed[a:b]
        lv.append(round(20 * math.log10(float(np.sqrt((seg ** 2).mean())) + 1e-9), 1) if len(seg) else -99.0)
    peak = float(np.abs(bed).max()); ok_arc = True; note = 'flat moods'
    live = [(e, l) for e, l in zip(energies, lv) if e > 0]
    if live:
        hi = max(live); lo = min(live)
        if hi[0] - lo[0] >= .3: ok_arc = hi[1] - lo[1] >= 1.5; note = f'energy {lo[0]:.2f}->{hi[0]:.2f}: {lo[1]} dB -> {hi[1]} dB'
    return {'sceneRmsDb': lv, 'peak': round(peak, 3), 'noClip': peak < .99, 'arcOk': ok_arc, 'arcNote': note}
ROUTE_STYLE = {'promo': 'warm', 'product-demo': 'tech', 'explainer': 'ambient', 'voiceover': 'warm', 'motion-graphics': 'bright',
               'documentary': 'cinematic', 'script-first': 'warm', 'ai-comic-drama': 'cinematic', 'ai-live-drama': 'cinematic', 'hybrid': 'cinematic'}
def pick_style(style, route=None):
    if style == 'auto': return ROUTE_STYLE.get(route or '', 'warm')
    if style not in STYLES: raise ValueError(f'unknown music style "{style}"; choose from auto, ' + ', '.join(STYLES))
    return style
def parse_key(key):
    """"D minor" / "F# major" / "A" -> (tonic_name|None, mode|None)."""
    if not key: return None, None
    parts = str(key).split(); mode = parts[1].lower() if len(parts) > 1 else None
    if mode and mode not in MODES: raise ValueError(f'unknown mode "{mode}"; choose from ' + ', '.join(MODES))
    return parts[0], mode
def main():
    """Audition a style without a project:  python scripts/score.py --style warm --seconds 30 -o warm.wav [--mood calm,build,climax,resolve]"""
    import argparse, wave
    ap = argparse.ArgumentParser(description=main.__doc__); ap.add_argument('--style', default='warm', choices=list(STYLES)); ap.add_argument('--seconds', type=float, default=32)
    ap.add_argument('--mood', default='calm,build,climax,resolve'); ap.add_argument('--bpm', type=float); ap.add_argument('--key'); ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('-o', '--out'); ap.add_argument('--list', action='store_true'); a = ap.parse_args()
    if a.list:
        for k, v in STYLES.items(): print(f"{k:<10} {v['bpm']:>3} bpm {v['tonic']} {v['mode']:<9} {v['desc']}")
        return
    moods = a.mood.split(','); L = a.seconds / len(moods); scenes = [{'ns': i * L, 'nd': L, 'mood': m} for i, m in enumerate(moods)]
    tonic, mode = parse_key(a.key); bed, info = render(a.style, scenes, energies_for(scenes), a.seconds, bpm=a.bpm, tonic=tonic, mode=mode, seed=a.seed)
    out = a.out or f'{a.style}.wav'
    with wave.open(out, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(bed[:int(a.seconds * SR)], -1, 1) * 32767).astype('<i2').tobytes())
    print(f"wrote {out}: {info['style']} {info['bpm']:.0f} bpm, moods {moods}")

if __name__ == '__main__': main()
