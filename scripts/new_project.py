"""Create a new video project from the template.
  python scripts/new_project.py <dir> --title "标题" [--format 16:9|9:16|1:1|4:3] [--route promo] [--textures] [--music-style workplace]
  --textures copies the texture pack (paper, grain, dust, washi tape) into <dir>/assets/textures/.
Never overwrites an existing project; use --version to fork an existing one into <dir>_vN.
"""
from __future__ import annotations
import argparse, json, os, shutil, sys
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
from avs_common import SKILL_DIR, save_json, load_json
from bgm import DRAMA_ROUTES
import score as scoremod

FORMATS = {'16:9': (1920, 1080), '9:16': (1080, 1920), '1:1': (1080, 1080), '4:3': (1440, 1080), '3:4': (1080, 1440)}

def fork(src: Path):
    n = 2
    while (src.parent / f'{src.name}_v{n}').exists(): n += 1
    dst = src.parent / f'{src.name}_v{n}'
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns('out', 'qa', '_frames'))
    print(dst); return dst

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('dir'); ap.add_argument('--title', default='未命名视频')
    ap.add_argument('--format', default='16:9', choices=FORMATS); ap.add_argument('--route', default='promo'); ap.add_argument('--version', action='store_true'); ap.add_argument('--textures', action='store_true', help='copy assets/textures into the project')
    ap.add_argument('--music-style', choices=['auto'] + list(scoremod.STYLES), help='music.style; AI drama defaults to auto (workplace/healing by route), code animation defaults to the built-in track')
    a = ap.parse_args(); d = Path(a.dir).resolve()
    if a.version:
        if not (d / 'project.json').exists(): sys.exit('nothing to fork')
        fork(d); return
    if (d / 'project.json').exists(): sys.exit(f'{d} already has a project. Use --version to fork it.')
    d.mkdir(parents=True, exist_ok=True)
    for sub in ('assets', 'audio/vo', 'out', 'qa', 'refs'): (d / sub).mkdir(parents=True, exist_ok=True)
    t = SKILL_DIR / 'assets' / 'template'
    for f in ('index.html', 'avs-runtime.js', 'scenes.js', 'style.css'): shutil.copy(t / f, d / f)
    w, h = FORMATS[a.format]
    p = load_json(t / 'project.example.json'); p['title'] = a.title; p['route'] = a.route; p['format'].update({'width': w, 'height': h, 'aspect': a.format})
    # The template ships with the built-in track because most projects are code animation. A pure AI drama project
    # must not inherit it: its music is a theme-based synthesized score, chosen by the story (workplace / healing /
    # comedy / hotblood / suspense / cinematic / tech ...). An explicit --music-style wins on every route.
    if a.music_style:
        p['music'] = {'style': a.music_style}
    elif a.route in DRAMA_ROUTES:
        p['music'] = {'style': 'auto'}
    else:
        p['music'] = {'track': 'default'}
    save_json(d / 'project.json', p)
    if a.textures: shutil.copytree(SKILL_DIR / 'assets' / 'textures', d / 'assets' / 'textures', dirs_exist_ok=True)
    print(d)

if __name__ == '__main__': main()
