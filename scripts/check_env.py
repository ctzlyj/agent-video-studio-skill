"""Check (and optionally install) everything the skill needs. Works on Windows and macOS.
Usage: python scripts/check_env.py [--install]
"""
from __future__ import annotations
import argparse, importlib, os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
from avs_common import SYSTEM

PKGS = {'playwright': 'playwright', 'edge_tts': 'edge-tts', 'PIL': 'pillow', 'numpy': 'numpy', 'requests': 'requests', 'imageio_ffmpeg': 'imageio-ffmpeg', 'faster_whisper': 'faster-whisper', 'pypinyin': 'pypinyin'}

def has(mod):
    try: importlib.import_module(mod); return True
    except Exception: return False

def chromium_status(install=False):
    """-> (ok, message). Tells apart three situations that used to look the same:
       installed and launches        -> ok
       installed but the sandbox blocks launching (macOS: 'Operation not permitted') -> ok for our purposes, with a note; do NOT reinstall
       not installed                 -> MISSING (installs it when install=True, then re-checks)"""
    if not has('playwright'): return False, 'MISSING (playwright package not installed)'
    from playwright.sync_api import sync_playwright
    def probe():
        """-> 'ok' | 'missing' | 'blocked' | 'error:<msg>'"""
        try:
            with sync_playwright() as p:
                exe = p.chromium.executable_path
                if not exe or not os.path.exists(exe): return 'missing'
                try: b = p.chromium.launch(); b.close(); return 'ok'
                except Exception as e:
                    m = str(e)
                    if "doesn't exist" in m or 'playwright install' in m: return 'missing'
                    if 'Operation not permitted' in m or 'Permission denied' in m or 'sandbox' in m.lower(): return 'blocked'
                    return 'error:' + m.splitlines()[0][:160]
        except Exception as e:
            m = str(e)
            if 'Operation not permitted' in m or 'Permission denied' in m: return 'blocked'
            return 'error:' + m.splitlines()[0][:160]
    st = probe()
    if st == 'missing' and install:
        subprocess.run([sys.executable, '-m', 'playwright', 'install', 'chromium'], check=False); st = probe()
    if st == 'ok': return True, 'ok'
    if st == 'blocked': return True, 'installed, but this sandbox blocked a test launch (Operation not permitted). Not a missing browser: do not reinstall; run builds with the sandbox permission that allows starting a local browser'
    if st == 'missing': return False, 'MISSING -> python -m playwright install chromium'
    return False, 'could not start: ' + st[6:]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--install', action='store_true'); a = ap.parse_args()
    rows, ok = [], True
    rows.append(('python', sys.version.split()[0], sys.version_info >= (3, 9)))
    missing = [pip for mod, pip in PKGS.items() if not has(mod)]
    if missing and a.install:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', *missing], check=False)
        missing = [pip for mod, pip in PKGS.items() if not has(mod)]
    for mod, pip in PKGS.items(): rows.append((pip, 'ok' if has(mod) else 'MISSING', has(mod)))
    chromium, chromium_note = chromium_status(a.install)
    rows.append(('chromium (playwright)', chromium_note, chromium))
    try:
        from avs_common import ffmpeg; ff = ffmpeg(); rows.append(('ffmpeg', ff, True))
    except SystemExit: rows.append(('ffmpeg', 'MISSING', False))
    key = bool(os.environ.get('JD_LLM_API_KEY') or os.environ.get('AVS_IMAGE_API_KEY'))
    rows.append(('image gateway key (JD_LLM_API_KEY / AVS_IMAGE_API_KEY)', 'set' if key else 'not set (image generation disabled)', True))
    lj = shutil.which('lingjing') or next((p for p in [os.path.expanduser('~/.lingjing/bin/lingjing'), os.path.expanduser('~/.lingjing/bin/lingjing.exe')] if os.path.exists(p)), None)
    rows.append(('lingjing CLI (AI drama routes only)', lj or 'not installed (optional)', True))
    offline = 'say (macOS)' if SYSTEM == 'Darwin' else ('SAPI (Windows)' if SYSTEM == 'Windows' else 'espeak if installed')
    rows.append(('offline TTS fallback', offline, True))
    # optional capabilities (never block READY; see references/capabilities.md)
    node = shutil.which('node'); rows.append(('node (optional: Remotion / HyperFrames / p5 / gsap installs)', node or 'not installed (optional)', True))
    rows.append(('rembg (optional: cut generated objects out as transparent PNG)', 'ok' if has('rembg') else 'not installed: pip install rembg', True))
    rows.append(('librosa (optional: beat / audio analysis)', 'ok' if has('librosa') else 'not installed: pip install librosa', True))
    for name, val, good in rows:
        ok &= good; print(f"{'OK ' if good else 'XX '} {name}: {val}")
    print('\nREADY' if ok else '\nNOT READY - rerun with --install')
    sys.exit(0 if ok else 1)

if __name__ == '__main__': main()

