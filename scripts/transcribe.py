"""Transcribe speech with timestamps (local faster-whisper; Windows/macOS/Linux, CPU).
  python scripts/transcribe.py <audio_or_video> [--model small] [--prompt "术语"] [-o out.json]
Outputs [{"start","end","text"}]. Use it to subtitle generated video dialogue, or to align a user's
voice-over recording to its script. Install once: pip install faster-whisper
Model download goes through HF_ENDPOINT (defaults to the hf-mirror.com mirror when unset).
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, tempfile, wave
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
from avs_common import ffmpeg

def to_pcm(path):
    import numpy as np
    tmp = Path(tempfile.mkdtemp(prefix='avs_asr_')) / 'a.wav'
    subprocess.run([ffmpeg(), '-y', '-hide_banner', '-loglevel', 'error', '-i', str(path), '-vn', '-ac', '1', '-ar', '16000', str(tmp)], check=True)
    w = wave.open(str(tmp)); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768; w.close()
    return a  # decoded here (not by PyAV) so it works with any av version

def transcribe(path, model='small', prompt=None, language='zh'):
    os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
    try: from faster_whisper import WhisperModel
    except ImportError: sys.exit('pip install faster-whisper')
    m = WhisperModel(model, device='cpu', compute_type='int8')
    segs, _ = m.transcribe(to_pcm(path), language=language, word_timestamps=True, vad_filter=False, initial_prompt=prompt)
    return [{'start': round(s.start, 2), 'end': round(s.end, 2), 'text': s.text.strip()} for s in segs]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--model', default='small'); ap.add_argument('--prompt'); ap.add_argument('--language', default='zh'); ap.add_argument('-o')
    a = ap.parse_args(); res = transcribe(a.file, a.model, a.prompt, a.language)
    txt = json.dumps(res, ensure_ascii=False, indent=1)
    if a.o: Path(a.o).write_text(txt, encoding='utf-8')
    print(txt)

if __name__ == '__main__': main()
