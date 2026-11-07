"""Narration per scene. Engines: edge (default, Win/mac/Linux), say (macOS offline), sapi (Windows offline),
file (bring your own recording: audio/vo/<id>.wav). Writes audio/vo/<id>.wav + <id>.json {dur}.
Only regenerates scenes whose text/voice changed (hash cache), or the ids you pass.

  python scripts/voice.py [project] [--only s02 s13] [--force]
"""
from __future__ import annotations
import argparse, asyncio, hashlib, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
from avs_common import project_dir, load_json, save_json, ffmpeg, media_duration, SYSTEM

def _say_text(project, text):
    for k, v in ((project.get('voice') or {}).get('pronounce') or {}).items(): text = text.replace(k, v)
    return text

async def _edge(text, voice, rate, pitch, out):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(out))

def synth(engine, text, cfg, out_wav: Path):
    tmp = Path(tempfile.mkdtemp(prefix='avs_vo_'))
    if engine == 'edge':
        raw = tmp / 'a.mp3'; asyncio.run(_edge(text, cfg.get('voice', 'zh-CN-YunyangNeural'), cfg.get('rate', '+0%'), cfg.get('pitch', '+0Hz'), raw))
    elif engine == 'say':
        if SYSTEM != 'Darwin': raise SystemExit('voice.engine "say" only exists on macOS')
        raw = tmp / 'a.aiff'; subprocess.run(['say', '-v', cfg.get('voice', 'Tingting'), '-o', str(raw), text], check=True)
    elif engine == 'sapi':
        if SYSTEM != 'Windows': raise SystemExit('voice.engine "sapi" only exists on Windows')
        raw = tmp / 'a.wav'; (tmp / 't.txt').write_text(text, encoding='utf-8')
        ps = ("Add-Type -AssemblyName System.Speech;$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
              f"$s.SetOutputToWaveFile('{raw}');$s.Speak([IO.File]::ReadAllText('{tmp / 't.txt'}'));$s.Dispose()")
        subprocess.run(['powershell', '-NoProfile', '-Command', ps], check=True)
    else: raise SystemExit(f'unknown voice engine {engine}')
    subprocess.run([ffmpeg(), '-y', '-hide_banner', '-loglevel', 'error', '-i', str(raw), '-ar', '48000', '-ac', '2', str(out_wav)], check=True)
    shutil.rmtree(tmp, ignore_errors=True)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('project', nargs='?'); ap.add_argument('--only', nargs='*'); ap.add_argument('--force', action='store_true')
    a = ap.parse_args(); d = project_dir(a.project); p = load_json(d / 'project.json')
    cfg = p.get('voice') or {}; engine = cfg.get('engine', 'edge'); vd = d / 'audio' / 'vo'; vd.mkdir(parents=True, exist_ok=True)
    if engine == 'none': print('voice.engine=none: silent video'); return
    for sc in p['scenes']:
        text = (sc.get('vo') or '').strip(); wav, meta = vd / f"{sc['id']}.wav", vd / f"{sc['id']}.json"
        if not text:
            for f in (wav, meta): f.unlink(missing_ok=True)
            continue
        spoken = _say_text(p, text)
        h = hashlib.sha1(json.dumps([engine, spoken, cfg.get('voice'), cfg.get('rate'), cfg.get('pitch')], ensure_ascii=False).encode()).hexdigest()[:12]
        if a.only and sc['id'] not in a.only: continue
        if engine == 'file':
            if not wav.exists(): sys.exit(f'voice.engine=file but {wav} is missing')
        elif not a.force and meta.exists() and wav.exists() and load_json(meta).get('hash') == h: continue
        else:
            for attempt in range(3):
                try: synth(engine, spoken, cfg, wav); break
                except SystemExit: raise
                except Exception as e:
                    if attempt == 2: sys.exit(f"TTS failed for {sc['id']}: {e}. Offline fallback: set voice.engine to {'say' if SYSTEM == 'Darwin' else 'sapi'}")
        save_json(meta, {'dur': round(media_duration(wav), 3), 'hash': h, 'engine': engine})
        print(f"{sc['id']}: {load_json(meta)['dur']:.2f}s")
    print('voice ok')

if __name__ == '__main__': main()
