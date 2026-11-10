"""Install a one-time daily auto-update task for this skill (opt-in).

  python scripts/install_auto_update.py --time 07:30            # install
  python scripts/install_auto_update.py --time 07:30 --dry-run  # preview only
  python scripts/install_auto_update.py --uninstall             # remove

Windows uses Task Scheduler; macOS uses launchd. The task runs `self_update.py --apply --quiet` once a day.
O2 itself has no per-skill auto-update switch; this is the supported wrapper. A running Codex session still needs a
restart/new session to load new SKILL.md instructions.
"""
from __future__ import annotations
import argparse, html, os, re, shutil, subprocess, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
SELF = SKILL / 'scripts' / 'self_update.py'
DEFAULT_NAME = 'agent-video-studio-auto-update'

def check_time(s):
    m = re.fullmatch(r'(\d{1,2}):(\d{2})', s or '')
    if not m or not (0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59): raise argparse.ArgumentTypeError('time must be HH:MM')
    return f'{int(m.group(1)):02d}:{m.group(2)}'

def windows(name, when, dry):
    base = Path(os.environ.get('LOCALAPPDATA') or (Path.home() / 'AppData' / 'Local')) / 'agent-video-studio'
    cmd = base / 'auto_update.cmd'; log = base / 'update.log'
    body = f'@echo off\r\n"{sys.executable}" "{SELF}" --apply --quiet >> "{log}" 2>&1\r\n'
    task = name
    schtasks = shutil.which('schtasks') or 'schtasks'
    create = [schtasks, '/Create', '/SC', 'DAILY', '/TN', task, '/TR', f'"{cmd}"', '/ST', when, '/F']
    print('Windows Task Scheduler action:')
    print('  command file:', cmd); print('  log:', log); print('  command:', body.strip()); print('  create:', subprocess.list2cmdline(create))
    if dry: return 0
    base.mkdir(parents=True, exist_ok=True); cmd.write_text(body, encoding='utf-8')
    r = subprocess.run(create, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    print((r.stdout + r.stderr).strip())
    return r.returncode

def macos(name, when, dry):
    hh, mm = map(int, when.split(':'))
    plist = Path.home() / 'Library' / 'LaunchAgents' / f'com.{name}.plist'
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.{html.escape(name)}</string>
<key>ProgramArguments</key><array><string>{html.escape(sys.executable)}</string><string>{html.escape(str(SELF))}</string><string>--apply</string><string>--quiet</string></array>
<key>StartCalendarInterval</key><dict><key>Hour</key><integer>{hh}</integer><key>Minute</key><integer>{mm}</integer></dict>
<key>StandardOutPath</key><string>{html.escape(str(Path.home() / 'Library' / 'Logs' / (name + '.log')))}</string>
<key>StandardErrorPath</key><string>{html.escape(str(Path.home() / 'Library' / 'Logs' / (name + '.err.log')))}</string>
</dict></plist>
'''
    print('macOS launchd action:'); print('  plist:', plist); print(xml)
    if dry: return 0
    plist.parent.mkdir(parents=True, exist_ok=True); plist.write_text(xml, encoding='utf-8')
    subprocess.run(['launchctl', 'unload', str(plist)], capture_output=True)
    r = subprocess.run(['launchctl', 'load', '-w', str(plist)], capture_output=True, text=True, encoding='utf-8', errors='ignore')
    print((r.stdout + r.stderr).strip()); return r.returncode

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--time', type=check_time, default='07:30'); ap.add_argument('--name', default=DEFAULT_NAME)
    ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--uninstall', action='store_true'); a = ap.parse_args()
    if sys.platform.startswith('win'):
        if a.uninstall:
            cmd = [shutil.which('schtasks') or 'schtasks', '/Delete', '/TN', a.name, '/F']; print(subprocess.list2cmdline(cmd))
            return 0 if a.dry_run else subprocess.run(cmd).returncode
        return windows(a.name, a.time, a.dry_run)
    if sys.platform == 'darwin':
        plist = Path.home() / 'Library' / 'LaunchAgents' / f'com.{a.name}.plist'
        if a.uninstall:
            print('launchctl unload -w', plist); return 0 if a.dry_run else (subprocess.run(['launchctl', 'unload', '-w', str(plist)]).returncode if plist.exists() else 0)
        return macos(a.name, a.time, a.dry_run)
    print('Linux: add this line to crontab -e (not installed automatically):')
    print(f'{a.time.split(":")[1]} {a.time.split(":")[0]} * * * "{sys.executable}" "{SELF}" --apply --quiet')
    return 0

if __name__ == '__main__': sys.exit(main())