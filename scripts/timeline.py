"""Build the master timeline from project.json + measured narration.

Scene authors animate in natural (1x) seconds. Each scene has its own `speed`; the
timeline maps output time t -> scene-local time lt = (t - ns) * speed, so speeding up
a scene compresses picture, narration (atempo), subtitles and sfx together.
"""
from __future__ import annotations
import re, sys, os
sys.path.insert(0, os.path.dirname(__file__))

def max_chars(project):
    sub = project.get('subtitles') or {}
    if sub.get('maxChars'): return int(sub['maxChars'])
    w = (project.get('format') or project.get('style') or {}).get('width', 1920)
    h = (project.get('format') or project.get('style') or {}).get('height', 1080)
    return 22 if w >= h else 14

def split_sub(text, limit):
    parts = [p.strip() for p in re.split(r'(?<=[。！？!?；;\n])', text) if p.strip()]
    out = []
    for p in parts:
        if len(p) <= limit: out.append(p); continue
        cur = ''
        for b in [b for b in re.split(r'(?<=[，,、：:])', p) if b]:
            while len(b) > limit:  # very long clause without punctuation
                if cur: out.append(cur); cur = ''
                out.append(b[:limit]); b = b[limit:]
            if cur and len(cur + b) > limit: out.append(cur); cur = b
            else: cur += b
        if cur: out.append(cur)
    return out

def _chars(s): return len(re.sub(r'[\s，。！？、；：,.!?;:“”"（）()]', '', s)) or 1

def build(project, vo):
    """vo: {scene_id: duration_seconds | {'dur': float, 'sentences': [[start, end, text], ...]}}"""
    limit = max_chars(project)
    repl = (project.get('subtitles') or {}).get('replace') or {}
    show_subs = (project.get('subtitles') or {}).get('enabled', True)
    t = 0.0; nt = 0.0; scenes = []; subs = []
    for i, sc in enumerate(project['scenes']):
        info = vo.get(sc['id'], 0.0)
        vdur = info['dur'] if isinstance(info, dict) else float(info or 0)
        text = sc.get('vo', '') or ''
        lead = float(sc.get('lead', 0.45 if text else 0.0))
        pad = float(sc.get('pad', 1.2))
        dur = float(sc['dur']) if sc.get('dur') else lead + vdur + pad
        dur = max(dur, float(sc.get('minDur', 0)))
        sp = float(sc.get('speed', project.get('speed', 1.0)))
        nd = dur / sp
        scenes.append({'id': sc['id'], 'start': round(t, 3), 'dur': round(dur, 3), 'speed': sp,
                       'ns': round(nt, 3), 'nd': round(nd, 3), 'voStart': round(lead, 3), 'voDur': round(vdur, 3),
                       'transition': sc.get('transition', project.get('transition', 'fade'))})
        if sc.get('subs') and show_subs:  # explicit timed lines (scene-local 1x seconds), e.g. dialogue inside a generated clip
            for st, en, line in sc['subs']:
                subs.append({'s': round(nt + float(st) / sp, 3), 'e': round(min(nt + float(en) / sp, nt + nd), 3), 'text': line, 'scene': sc['id']})
        elif text and vdur > 0 and show_subs and sc.get('subtitle', True):
            sub_text = text
            for k, v in repl.items(): sub_text = sub_text.replace(k, v)
            chunks = split_sub(sub_text, limit); total = sum(_chars(c) for c in chunks); cur = lead
            for c in chunks:
                d = vdur * _chars(c) / total
                s_, e_ = nt + cur / sp, nt + (cur + d - 0.04) / sp
                subs.append({'s': round(s_, 3), 'e': round(min(e_, nt + nd), 3), 'text': c.rstrip('。；;'), 'scene': sc['id']})
                cur += d
        t += dur; nt += nd
    return {'duration': round(nt, 3), 'origDuration': round(t, 3), 'fps': (project.get('format') or {}).get('fps', 30),
            'width': (project.get('format') or {}).get('width', 1920), 'height': (project.get('format') or {}).get('height', 1080),
            'scenes': scenes, 'subs': subs}

def main():
    import argparse
    from avs_common import project_dir, load_json, save_json
    ap = argparse.ArgumentParser(); ap.add_argument('project', nargs='?'); a = ap.parse_args()
    d = project_dir(a.project); p = load_json(d / 'project.json')
    vo = {}
    for sc in p['scenes']:
        meta = d / 'audio' / 'vo' / f"{sc['id']}.json"
        if sc.get('vo') and meta.exists(): vo[sc['id']] = load_json(meta)
        elif sc.get('vo'): sys.exit(f"narration for {sc['id']} missing: run voice.py first")
    tl = build(p, vo)
    save_json(d / 'timeline.json', tl)
    (d / 'timeline.js').write_text('window.TL=' + __import__('json').dumps(tl, ensure_ascii=False) + ';', encoding='utf-8')
    print(f"duration {tl['duration']:.2f}s (unsped {tl['origDuration']:.2f}s), {len(tl['scenes'])} scenes, {len(tl['subs'])} subtitles")
    for s in tl['scenes']: print(f"  {s['id']:<8} {s['ns']:7.2f}s  len {s['nd']:6.2f}s  x{s['speed']}")

if __name__ == '__main__': main()
