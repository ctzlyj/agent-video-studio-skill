"""Shared helpers: project paths, ffmpeg discovery, fonts, json IO. Cross-platform (Windows / macOS / Linux)."""
from __future__ import annotations
import json, os, platform, shutil, subprocess, sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SYSTEM = platform.system()  # 'Windows' | 'Darwin' | 'Linux'

def load_json(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def save_json(p, data): Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def project_dir(arg: str | None = None) -> Path:
    """Project root = directory containing project.json (arg, or cwd)."""
    p = Path(arg or '.').resolve()
    if p.is_file(): p = p.parent
    if not (p / 'project.json').exists():
        sys.exit(f'project.json not found in {p}. Run new_project.py first.')
    return p

def ffmpeg() -> str:
    """Prefer env override, then PATH, then lingjing's managed ffmpeg, then imageio-ffmpeg (auto-download)."""
    env = os.environ.get('AVS_FFMPEG')
    if env and Path(env).exists(): return env
    found = shutil.which('ffmpeg')
    if found: return found
    lj = shutil.which('lingjing')
    if lj:
        try:
            out = subprocess.run([lj, 'clip', 'which-ffmpeg'], capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=20).stdout.strip().splitlines()
            cand = [x.strip() for x in out if x.strip() and Path(x.strip()).exists()]
            if cand: return cand[-1]
        except Exception: pass
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        sys.exit('ffmpeg not found. Run: python scripts/check_env.py --install')

def media_duration(path) -> float:
    import re
    p = subprocess.run([ffmpeg(), '-hide_banner', '-i', str(path)], capture_output=True, text=True, encoding='utf-8', errors='ignore')
    m = re.search(r'Duration: (\d+):(\d+):([\d.]+)', p.stderr)
    if not m: raise RuntimeError(f'cannot read duration: {path}')
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])

def safe_name(s):
    import re
    return re.sub(r'[\\/:*?"<>|\s]+', '_', s).strip('_') or 'video'

def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], check=True, **kw)

# CSS font stacks: browser picks the first available, so one stack works on every OS.
FONT_STACK = '"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans CJK SC","Source Han Sans SC",sans-serif'
MONO_STACK = '"SF Mono",Menlo,Consolas,"Cascadia Mono",monospace'
