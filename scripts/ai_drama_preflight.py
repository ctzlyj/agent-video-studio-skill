"""Hard preflight for AI-drama routes.

  python scripts/ai_drama_preflight.py [--cli PATH] [--skill-root DIR] [--json]

AI drama needs all four:
  1) the Lingjing CLI executable,
  2) the `lingjing` skill,
  3) the `lingjing-director` skill,
  4) `lingjing doctor` with ok=true.
If any is missing, this script exits non-zero and prints install instructions. Browser automation of the Lingjing
canvas is NOT a fallback for generation, billing or canvas writes; it bypasses the CLI contract.
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path

INSTALL_URL = 'https://j.jdcloud.com/lingjing-cli/latest/lingjing-cli.zip'
SKILL_NAMES = ('lingjing', 'lingjing-director')

def find_cli(explicit=None):
    if explicit:
        p = Path(explicit).expanduser()
        return str(p) if p.is_file() else None
    found = shutil.which('lingjing')
    if found: return found
    for p in (Path.home() / '.lingjing' / 'bin' / 'lingjing', Path.home() / '.lingjing' / 'bin' / 'lingjing.exe'):
        if p.is_file(): return str(p)
    return None

def default_skill_roots():
    roots = []
    env = os.environ.get('LINGJING_SKILL_DIR')
    if env: roots.append(env)
    for name in ('.codex', '.agents', '.claude', '.workbuddy', '.joycode'):
        roots.append(str(Path.home() / name / 'skills'))
    return roots

def find_skill(name, roots):
    for root in roots:
        p = Path(root).expanduser() / name / 'SKILL.md'
        if p.is_file(): return str(p.parent)
    return None

def run_doctor(cli):
    try:
        r = subprocess.run([cli, 'doctor'], capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=120)
    except Exception as e:
        return False, f'doctor failed to start: {e}', {}
    data = {}
    try:
        data = json.loads(r.stdout)
    except Exception:
        pass
    ok = r.returncode == 0 and (data.get('ok') is True if isinstance(data, dict) else True)
    if isinstance(data, dict):
        identity = (data.get('checks') or {}).get('identity', {}).get('identityVerified')
        if identity is False: ok = False
        detail = {'ok': bool(data.get('ok')), 'failures': data.get('failures') or [],
                  'warnings': data.get('warnings') or [],
                  'identityVerified': bool((data.get('checks') or {}).get('identity', {}).get('identityVerified')),
                  'bridge': (data.get('checks') or {}).get('bridge', {}).get('state')}
    else:
        detail = {'ok': ok, 'failures': [], 'warnings': [], 'identityVerified': None, 'bridge': None}
    return ok, ('ok' if ok else 'doctor returned ok=false or a non-zero exit'), detail

def instructions():
    print('安装灵境一体包（CLI + lingjing + lingjing-director）：')
    print(f'  下载 {INSTALL_URL}，解压后：')
    print('  Windows: $env:LINGJING_SKILL_DIR = "$HOME\\.codex\\skills"; powershell -ExecutionPolicy Bypass -File .\\install.ps1')
    print('  macOS:   LINGJING_SKILL_DIR="$HOME/.codex/skills" bash install.sh')
    print('  安装后重启 Codex 并新建会话；再运行 lingjing doctor。')
    print('  未登录时由用户本人完成 lingjing login --no-open 的授权。')
    print('不要把“浏览器自动化点灵境画布”当作兜底：生成、扣费、画布写入必须走 CLI（或宿主已注册的 lingjing MCP）。')

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cli'); ap.add_argument('--skill-root', action='append'); ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    roots = a.skill_root or default_skill_roots()
    cli = find_cli(a.cli); skills = {n: find_skill(n, roots) for n in SKILL_NAMES}
    missing = ([f'CLI ({a.cli or "lingjing"})'] if not cli else []) + [n for n, p in skills.items() if not p]
    report = {'cli': cli, 'skills': skills, 'missing': missing, 'doctor': None}
    if missing:
        if a.json: print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print('NOT READY - AI 剧缺少灵境依赖：' + ', '.join(missing)); instructions()
        sys.exit(2)
    ok, msg, detail = run_doctor(cli); report['doctor'] = {'ok': ok, 'detail': detail}
    if a.json: print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print('OK  灵境 CLI:', cli)
        for n, p in skills.items(): print(f'OK  {n}:', p)
        print('OK  lingjing doctor:', detail)
    if not ok:
        if not a.json:
            print('NOT READY -', msg); instructions()
            print('若已安装但未登录：运行 lingjing login --no-open，把授权链接发给用户本人。')
        sys.exit(3)
    if not a.json: print('\nREADY (AI drama)')

if __name__ == '__main__': main()