"""One-shot pipeline: lint -> voice -> prep_video -> timeline -> audio -> render.
  python scripts/build.py [project] --preview | --final | --sheet
"""
from __future__ import annotations
import argparse, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))

def step(name, *args):
    r = subprocess.run([sys.executable, '-X', 'utf8', os.path.join(HERE, name), *args])
    if r.returncode: sys.exit(f'{name} failed')

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('project', nargs='?', default='.')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--preview', action='store_true'); g.add_argument('--final', action='store_true'); g.add_argument('--sheet', action='store_true')
    ap.add_argument('--skip-lint', action='store_true'); a = ap.parse_args()
    if not a.skip_lint: step('lint.py', a.project)
    step('voice.py', a.project); step('prep_video.py', a.project); step('timeline.py', a.project)
    if not a.sheet: step('audio.py', a.project)
    step('render.py', a.project, '--preview' if a.preview else '--final' if a.final else '--sheet')
    if a.final: step('qa.py', a.project)

if __name__ == '__main__': main()
