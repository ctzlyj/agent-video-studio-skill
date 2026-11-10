"""Narration per scene. Engines: edge (default, Win/mac/Linux), say (macOS offline), sapi (Windows offline),
file (bring your own recording: audio/vo/<id>.wav). Writes audio/vo/<id>.wav + <id>.json {dur}.
Only regenerates scenes whose text/voice changed (hash cache), or the ids you pass.

  python scripts/voice.py [project] [--only s02 s13] [--force]
  python scripts/voice.py [project] --check [--asr] [--strict]   # pronunciation review; --asr transcribes existing audio
"""
from __future__ import annotations
import argparse, asyncio, difflib, hashlib, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
from avs_common import project_dir, load_json, save_json, ffmpeg, media_duration, SYSTEM

# Common polyphonic words that edge-tts gets wrong in business/teaching scripts. "try" values are homophone spellings
# that were checked with edge-tts + faster-whisper + pypinyin (see references/voice.md); keep the original text for subtitles.
PRONOUNCE_HINTS = {
    '重复': {'read': 'chóng fù', 'try': ['虫复', '崇复'], 'note': '重 here is chóng; Yunxi/Yunyang/Xiaoxiao read it correctly in our 2026-11 test, but keep this hint if your voice reads zhòng'},
    '长度': {'read': 'cháng dù', 'try': ['常度', '肠度'], 'note': '长 here is cháng; Yunxi/Yunyang read the original as zhǎng in our test and read 常度 as cháng; Xiaoxiao was ambiguous'},
    '银行': {'read': 'yín háng', 'try': ['银杭'], 'note': '行 here is háng; the tested voices already read it correctly'},
    '还款': {'read': 'huán kuǎn', 'try': ['环款'], 'note': '还 here is huán; Yunyang/Xiaoxiao read the original as hái, Yunxi short-clip ASR failed, and all three read 环款 as huán'},
    '行业': {'read': 'háng yè', 'try': ['杭业'], 'note': '行 here is háng; the tested voices already read it correctly'},
    '重庆': {'read': 'chóng qìng', 'try': ['虫庆', '崇庆'], 'note': '重 here is chóng; the tested voices already read it correctly'},
    '得到': {'read': 'dé dào', 'try': ['德到'], 'note': '得 here is dé; the tested voices already read it correctly'},
    '数据': {'read': 'shù jù', 'try': ['数句'], 'note': '据 here is jù; the tested voices already read it correctly'},
    '为了': {'read': 'wèi le', 'try': ['位了'], 'note': '为 here is wèi; the tested voices already read it correctly'},
    '重要': {'read': 'zhòng yào', 'try': ['众要'], 'note': '重 here is zhòng; the tested voices already read it correctly'},
    '重新': {'read': 'chóng xīn', 'try': ['虫新', '崇新'], 'note': '重 here is chóng'},
    '重量': {'read': 'zhòng liàng', 'try': ['众量'], 'note': '重 here is zhòng'},
    '长大': {'read': 'zhǎng dà', 'try': ['掌大'], 'note': '长 here is zhǎng'},
    '音乐': {'read': 'yīn yuè', 'try': ['音月'], 'note': '乐 here is yuè'},
    '快乐': {'read': 'kuài lè', 'try': ['快勒'], 'note': '乐 here is lè'},
    '还是': {'read': 'hái shì', 'try': ['孩是'], 'note': '还 here is hái'},
    '归还': {'read': 'guī huán', 'try': ['归环'], 'note': '还 here is huán'},
    '处理': {'read': 'chǔ lǐ', 'try': ['楚理'], 'note': '处 here is chǔ; the tested voices already read it correctly'},
    '参与': {'read': 'cān yù', 'try': ['参玉'], 'note': '与 here is yù; the tested voices already read it correctly'},
    '角色': {'read': 'jué sè', 'try': ['决色'], 'note': '角 here is jué; the tested voices already read it correctly'},
}

def _say_text(project, text):
    for k, v in sorted(((project.get('voice') or {}).get('pronounce') or {}).items(), key=lambda kv: len(kv[0]), reverse=True):
        text = text.replace(k, v)
    return text

def _norm_text(s):
    return re.sub(r'[\s，。！？、；：,.!?;:“”"（）()《》【】·\-—…]', '', s or '')

def _pinyin(s):
    from pypinyin import lazy_pinyin, Style
    return [x for x in lazy_pinyin(_norm_text(s), style=Style.NORMAL, errors='ignore') if x.strip()]

def pronunciation_hints(text):
    """Return [(word, info)] for known polyphonic words present in text."""
    return [(w, info) for w, info in PRONOUNCE_HINTS.items() if w in (text or '')]

def _check_asr(spoken, asr_text):
    """Compare pinyin syllables of the written spoken text vs the ASR transcript. Homophones with the same pinyin do
    not raise a false alarm; tone errors are NOT detectable this way (documented in references/voice.md)."""
    a, b = _pinyin(spoken), _pinyin(asr_text)
    sm = difflib.SequenceMatcher(a=a, b=b)
    diffs = [(tag, a[i1:i2], b[j1:j2]) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != 'equal']
    return diffs

def check_project(d, p, a):
    cfg = p.get('voice') or {}; pron = cfg.get('pronounce') or {}; issues = 0
    for sc in p['scenes']:
        if a.only and sc['id'] not in a.only: continue
        vo = (sc.get('vo') or '').strip()
        if not vo: continue
        hints = pronunciation_hints(vo)
        if hints:
            print(f"[{sc['id']}] 读音提示：")
            for w, info in hints:
                if w in pron: print(f"  已配置 {w} -> {pron[w]}（{info['read']}）")
                else: print(f"  建议 {w} -> {' / '.join(info['try'])}（{info['read']}；{info['note']}）"); issues += 1
        if a.asr:
            wav = d / 'audio' / 'vo' / f"{sc['id']}.wav"
            if not wav.exists(): print(f"  [ASR] {sc['id']}: 没有 {wav.name}，先跑 voice.py"); continue
            import transcribe
            segs = transcribe.transcribe(wav, model=a.asr_model, prompt=vo)
            asr = ''.join(x.get('text', '') for x in segs)
            spoken = _say_text(p, vo)
            diffs = _check_asr(spoken, asr)
            print(f"  [ASR] {sc['id']}: 转写「{asr}」")
            if diffs:
                print('  [ASR] 拼音不一致，请重点听：' + '; '.join(f"{''.join(x)}→{''.join(y)}" for _, x, y in diffs[:4])); issues += len(diffs)
            else: print('  [ASR] 拼音与配音文本一致（不代表声调一定正确）')
    if a.strict and issues: sys.exit(f'读音校对发现 {issues} 处需要确认')
    return issues

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
    ap.add_argument('--check', action='store_true', help='review polyphonic words and optional ASR pronunciation'); ap.add_argument('--asr', action='store_true', help='transcribe existing audio and compare pinyin (slow)'); ap.add_argument('--asr-model', default='small'); ap.add_argument('--strict', action='store_true')
    a = ap.parse_args(); d = project_dir(a.project); p = load_json(d / 'project.json')
    if a.check or a.asr:
        check_project(d, p, a); return
    cfg = p.get('voice') or {}; engine = cfg.get('engine', 'edge'); vd = d / 'audio' / 'vo'; vd.mkdir(parents=True, exist_ok=True)
    if engine == 'none': print('voice.engine=none: silent video'); return
    for sc in p['scenes']:
        text = (sc.get('vo') or '').strip(); wav, meta = vd / f"{sc['id']}.wav", vd / f"{sc['id']}.json"
        if not text:
            for f in (wav, meta): f.unlink(missing_ok=True)
            continue
        spoken = _say_text(p, text); scfg = {**cfg, **(sc.get('voiceCfg') or {})}   # per-scene override: voice / rate / pitch
        h = hashlib.sha1(json.dumps([engine, spoken, scfg.get('voice'), scfg.get('rate'), scfg.get('pitch')], ensure_ascii=False).encode()).hexdigest()[:12]
        if a.only and sc['id'] not in a.only: continue
        if engine == 'file':
            if not wav.exists(): sys.exit(f'voice.engine=file but {wav} is missing')
        elif not a.force and meta.exists() and wav.exists() and load_json(meta).get('hash') == h: continue
        else:
            for attempt in range(3):
                try: synth(engine, spoken, scfg, wav); break
                except SystemExit: raise
                except Exception as e:
                    if attempt == 2: sys.exit(f"TTS failed for {sc['id']}: {e}. Offline fallback: set voice.engine to {'say' if SYSTEM == 'Darwin' else 'sapi'}")
        save_json(meta, {'dur': round(media_duration(wav), 3), 'hash': h, 'engine': engine})
        print(f"{sc['id']}: {load_json(meta)['dur']:.2f}s")
    print('voice ok')

if __name__ == '__main__': main()
