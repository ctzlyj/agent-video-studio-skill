"""Check or apply skill updates through the O2 `oxygenskills` CLI.

  python scripts/self_update.py            # check only
  python scripts/self_update.py --apply    # update now
  python scripts/self_update.py --apply --quiet
  python scripts/self_update.py --json

O2 has no native per-skill auto-update switch: `oxygenskills check/update` are CLI commands. This wrapper makes the
check/update reproducible; a running Codex session still needs a restart/new session to load new SKILL.md instructions.
"""
from __future__ import annotations
import argparse, json, os, re, shutil, subprocess, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
NAME = 'agent-video-studio'
AGENT = 'codex'

def local_version():
    text = (SKILL / 'CHANGELOG.md').read_text(encoding='utf-8')
    m = re.search(r'^##\s+(\d+\.\d+\.\d+)', text, re.M)
    return m.group(1) if m else None

def _cmd():
    exe = shutil.which('oxygenskills')
    if exe:
        return ([os.environ.get('COMSPEC', 'cmd.exe'), '/c', exe] if exe.lower().endswith(('.cmd', '.bat')) else [exe])
    # Fallback for machines where the npm bin shim is not on PATH.
    roots = [Path(os.environ.get('APPDATA', '')) / 'npm', Path('D:/CodexTools/npm-global')]
    for root in roots:
        js = root / 'node_modules' / '@jd' / 'oxygenskills' / 'bin' / 'oxygenskills.js'
        if js.is_file():
            node = shutil.which('node')
            if node: return [node, str(js)]
    return None

def parse_check(text):
    lines = text.splitlines(); best = None
    for i, line in enumerate(lines):
        if NAME not in line: continue
        for j in range(i + 1, min(len(lines), i + 5)):
            m = re.search(r'Latest:\s*([0-9]+\.[0-9]+\.[0-9]+)', lines[j])
            if m:
                v = m.group(1)
                if best is None or tuple(map(int, v.split('.'))) > tuple(map(int, best.split('.'))): best = v
                break
    return best

def run_check():
    cmd = _cmd()
    if not cmd: return None, 'oxygenskills CLI not found (install O2 oxygenskills or add it to PATH)'
    r = subprocess.run(cmd + ['check'], capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=180)
    if r.returncode != 0: return None, (r.stdout + r.stderr)[-500:]
    return parse_check(r.stdout + r.stderr), None

def cleanup_backups(keep=2):
    parent = SKILL.parent
    backups = sorted(parent.glob(f'{NAME}.backup.*'), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in backups[keep:]:
        try:
            if p.is_symlink() or p.is_junction(): os.unlink(p)
            else: shutil.rmtree(p)
        except Exception: pass
    return len(backups[keep:])

def apply_update():
    cmd = _cmd()
    if not cmd: return False, 'oxygenskills CLI not found'
    r = subprocess.run(cmd + ['update', NAME, '--agent', AGENT, '--force'], capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=300)
    cleanup_backups()
    return r.returncode == 0, (r.stdout + r.stderr)[-800:]

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--apply', action='store_true'); ap.add_argument('--quiet', action='store_true'); ap.add_argument('--json', action='store_true')
    a = ap.parse_args(); local = local_version(); latest, err = run_check()
    changed = False; msg = ''
    if err:
        msg = f'check failed: {err}'
    elif not latest:
        msg = 'up to date (no newer agent-video-studio version found)'
    elif tuple(map(int, latest.split('.'))) <= tuple(map(int, (local or '0.0.0').split('.'))):
        msg = f'up to date ({local})'
    elif a.apply:
        ok, out = apply_update(); changed = ok; msg = ('updated to ' + latest + '; restart Codex / open a new session') if ok else ('update failed: ' + out)
    else:
        msg = f'new version available: {local} -> {latest}; run python scripts/self_update.py --apply'
    result = {'local': local, 'latest': latest, 'changed': changed, 'message': msg}
    if a.json: print(json.dumps(result, ensure_ascii=False, indent=2))
    elif not a.quiet or changed or err: print(msg)
    sys.exit(0 if not err and (not a.apply or changed or 'up to date' in msg) else 1)

if __name__ == '__main__': main()