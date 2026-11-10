"""Pre-render checks on project.json: brand terms, banned words, absolute paths, missing assets,
screen text duplicating narration. Exit code 1 when any error is found."""
from __future__ import annotations
import os, re, sys
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
MEDIA = re.compile(r'\.(png|jpe?g|webp|gif|svg|mp4|mov|webm|mp3|wav|m4a|ttf|otf|woff2?)$', re.I)
ABS = re.compile(r'^(?:[A-Za-z]:[\\/]|/|\\\\|~[\\/])')
def _norm(s): return re.sub(r'[\s，。！？、；：,.!?;:“”"（）()·\-]', '', s)

def _strings(obj, path=''):
    if isinstance(obj, str): yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items(): yield from _strings(v, f'{path}.{k}' if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj): yield from _strings(v, f'{path}[{i}]')

def check(project, root: Path):
    from timeline import split_sub, max_chars
    issues = []
    brand = project.get('brand') or {}
    terms, banned = brand.get('terms') or {}, brand.get('banned') or []
    def add(level, kind, where, msg): issues.append({'level': level, 'kind': kind, 'where': where, 'msg': msg})
    for sc in project.get('scenes', []):
        sid = sc.get('id', '?')
        texts = [('vo', sc.get('vo', '') or '')] + list(_strings(sc.get('data') or {}, 'data'))
        for where, s in texts:
            for old, new in terms.items():
                if old and old in s: add('error', 'term', f'{sid}.{where}', f'uses "{old}", should be "{new}"')
            for w in banned:
                if w and w in s: add('error', 'banned', f'{sid}.{where}', f'banned word "{w}"')
            if where != 'vo' and MEDIA.search(s.strip()):
                if ABS.match(s.strip()): add('error', 'abs_path', f'{sid}.{where}', f'absolute path "{s}" breaks portability; copy into assets/ and use a relative path')
                elif not (root / s.strip()).exists(): add('error', 'missing_asset', f'{sid}.{where}', f'file not found: {s}')
        subs = {_norm(c) for c in split_sub(sc.get('vo', '') or '', max_chars(project))} | ({_norm(sc['vo'])} if sc.get('vo') else set())
        for where, s in (texts[1:] if sc.get('subtitle', True) else []):
            if len(_norm(s)) >= 4 and _norm(s) in subs:
                add('warn', 'dup_subtitle', f'{sid}.{where}', 'on-screen text repeats the subtitle line; drop one of them')
        sp = float(sc.get('speed', 1.0))
        if not 0.5 <= sp <= 2.0: add('error', 'speed', sid, f'speed {sp} outside 0.5-2.0')
        elif sp > 1.35: add('warn', 'speed', sid, f'speed {sp} may make on-screen text unreadable')
    limit = max_chars(project)
    for sc in project.get('scenes', []):
        if not sc.get('vo') or sc.get('subs') or not sc.get('subtitle', True) or not (project.get('subtitles') or {}).get('enabled', True): continue
        for line in split_sub(sc['vo'], limit):
            if len(_norm(line)) > limit + 8: add('warn', 'sub_long', sc.get('id', '?'), f'subtitle line is {len(_norm(line))} chars (limit {limit}): "{line[:24]}..."; add punctuation or shorten the sentence')
        if len(sc['vo']) > 120: add('warn', 'vo_long', sc.get('id', '?'), f'narration is {len(sc["vo"])} chars in one scene; split it (one idea per scene, <=120 chars)')
    ids = [s.get('id') for s in project.get('scenes', [])]
    if len(ids) != len(set(ids)): add('error', 'dup_id', 'scenes', 'duplicate scene ids')
    for name, v in (project.get('videos') or {}).items():
        src = v.get('src', '') if isinstance(v, dict) else v
        if ABS.match(src): add('error', 'abs_path', f'videos.{name}', f'absolute path "{src}"')
        elif not (root / src).exists(): add('error', 'missing_asset', f'videos.{name}', f'file not found: {src}')
    music = project.get('music') or {}
    f = music.get('file')
    if f and ABS.match(f): add('error', 'abs_path', 'music', f'absolute path "{f}"')
    elif f and not (root / f).exists(): add('error', 'missing_asset', 'music', f'file not found: {f}')
    rnd = project.get('render') or {}
    def _num(v, lo, hi, name):
        try: ok = lo <= float(v) <= hi
        except (TypeError, ValueError): ok = False
        if not ok: add('error', 'render', f'render.{name}', f'{name} must be a number in {lo}-{hi}, got {v!r}')
    if 'workers' in rnd: _num(rnd['workers'], 1, 16, 'workers')
    mbk = rnd.get('motionBlur') or {}
    if 'samples' in mbk: _num(mbk['samples'], 1, 16, 'motionBlur.samples')
    if 'shutter' in mbk: _num(mbk['shutter'], 0.05, 1.0, 'motionBlur.shutter')
    import bgm, score
    drama = project.get('route') in bgm.DRAMA_ROUTES
    drama_missing = drama and not music
    drama_blocked = drama and bgm.drama_track_blocked(music, project.get('route'))
    if drama_missing:
        add('warn', 'drama_music', 'music', 'AI 剧尚未选定配乐：先用灵境 MiniMax Music 生成两首候选、客观粗筛并让用户试听，再把选中的文件写进 music.file；不要用空 music 出片。')
    elif drama_blocked:
        add('error', 'drama_bgm', 'music', 'AI 剧不允许使用内置代码动画 BGM；请改用 music.file（MiniMax Music 生成）。只有用户明确要求时才写 music.allowBuiltinTrack=true。')
    elif drama and music.get('track') and music.get('allowBuiltinTrack'):
        add('warn', 'drama_bgm', 'music', '已显式允许 AI 剧使用内置 BGM；请确认这是用户在对话里明确要求的，而不是模板残留。')
    if drama and music.get('style'):
        add('warn', 'drama_synth', 'music', '代码合成配乐只适合做氛围衬底（没有真正旋律），AI 剧主配乐应优先用 MiniMax Music 生成 music.file。')
    if drama and music.get('file') and 'volume' not in music:
        add('warn', 'drama_volume', 'music', 'AI 剧 music.file 未写 volume，audio.py 会按默认 0.10 处理；如需更响/更轻请显式写明。')
    try: src = bgm.resolve(music, project.get('route'))
    except ValueError as e:
        src = None
        if not (drama_missing or drama_blocked): add('error', 'music', 'music', str(e))
    if src == 'style':
        try: score.pick_style(music.get('style') or 'auto', project.get('route')); score.parse_key(music.get('key'))
        except ValueError as e: add('error', 'music', 'music', str(e))
    if src in ('track', 'style'):
        for sc in project.get('scenes', []):
            if sc.get('mood') and sc['mood'] not in score.MOODS: add('error', 'mood', sc.get('id', '?'), f'mood "{sc["mood"]}" not in ' + '/'.join(score.MOODS))
            if sc.get('energy') is not None and not 0 <= float(sc['energy']) <= 1: add('error', 'mood', sc.get('id', '?'), 'energy must be 0-1')
        if not any(sc.get('mood') or sc.get('energy') is not None for sc in project.get('scenes', [])):
            add('warn', 'mood', 'scenes', 'no scene has "mood"/"energy"; the music will follow a default intro-build-climax-outro arc. Tag each scene so the music matches the story')
    for f in ('scenes.js', 'index.html'):
        p = root / f
        if p.exists():
            body = p.read_text(encoding='utf-8', errors='ignore')
            for old in terms:
                if old and old in body: add('error', 'term', f, f'uses "{old}" in code/markup')
            for w in banned:
                if w and w in body: add('error', 'banned', f, f'banned word "{w}" in code/markup')
            if re.search(r'requestAnimationFrame|setInterval|Math\.random\(\)|<video[\s>]', body):
                add('error', 'nondeterministic', f, 'use AVS.rand / AVS.video instead of requestAnimationFrame, setInterval, Math.random or <video>')
    return issues

def main():
    import argparse
    from avs_common import project_dir, load_json
    ap = argparse.ArgumentParser(); ap.add_argument('project', nargs='?'); a = ap.parse_args()
    d = project_dir(a.project); issues = check(load_json(d / 'project.json'), d)
    for i in issues: print(f"[{i['level'].upper()}] {i['kind']:<16} {i['where']}: {i['msg']}")
    errs = sum(i['level'] == 'error' for i in issues)
    print(f'lint: {errs} error(s), {len(issues) - errs} warning(s)'); sys.exit(1 if errs else 0)

if __name__ == '__main__': main()

