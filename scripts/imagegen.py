"""Image generation through the company LLM gateway.

Model chain, gateway and key come from env (references/image-providers.md). The first
AVS_IMAGE_PRIMARY_COUNT models are primary; fallback models are used ONLY when every primary
model reports quota / rate-limit / auth exhaustion (never on ordinary network errors).

  python scripts/imagegen.py "prompt" -o out.png [--size 1536x1024] [--ref a.jpg ...]
"""
from __future__ import annotations
import argparse, base64, io, json, os, re, sys, time
from pathlib import Path

GATEWAY = os.environ.get('AVS_IMAGE_BASE_URL', 'http://llm-gw.jd.local/v1').rstrip('/')
_DEFAULT = ['GPT-Image-2.5-Flare-joybuilder', 'GPT-Image-2.5-Sunburst-joybuilder', 'GPT-image-2-joybuilder', 'Oxygen-Product-Pro', 'Oxygen-Imagen']
CHAIN = [m.strip() for m in os.environ['AVS_IMAGE_MODELS'].split(',') if m.strip()] if os.environ.get('AVS_IMAGE_MODELS') else _DEFAULT
PRIMARY = CHAIN[:int(os.environ.get('AVS_IMAGE_PRIMARY_COUNT', 2 if not os.environ.get('AVS_IMAGE_MODELS') else 1))]
QUOTA = re.compile(r'2007|quota|额度|配额|限流|rate.?limit|exceed|余额|insufficient|次数超过|阈值|too many', re.I)

def api_key():
    k = os.environ.get('AVS_IMAGE_API_KEY') or os.environ.get('JD_LLM_API_KEY')
    if not k: raise SystemExit('Set AVS_IMAGE_API_KEY (or JD_LLM_API_KEY on the JD gateway) to enable image generation. See references/image-providers.md')
    return k

def is_quota_error(status: int, body: str) -> bool:
    """True when this model is exhausted for now -> switch model instead of retrying."""
    return status in (401, 402, 429) or bool(QUOTA.search(body or ''))

def _data_url(path):
    from PIL import Image
    im = Image.open(path)
    if im.mode in ('P', 'LA', 'RGBA'):
        im = im.convert('RGBA'); bg = Image.new('RGBA', im.size, 'white'); bg.alpha_composite(im); im = bg
    b = io.BytesIO(); im.convert('RGB').save(b, 'JPEG', quality=92)
    return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()

def _call(model, prompt, size, refs, timeout):
    import requests
    body = {'model': model, 'prompt': prompt, 'size': size, 'n': 1}
    ep = 'images/generations'
    if refs: body['image'] = [_data_url(r) for r in refs]; ep = 'images/edits'
    if model.startswith('Oxygen'): body['response_format'] = 'url'
    r = requests.post(f'{GATEWAY}/{ep}', headers={'Authorization': 'Bearer ' + api_key()}, json=body, timeout=timeout)
    if r.status_code >= 400: return None, r.status_code, r.text[:400]
    d = (r.json().get('data') or [{}])[0]
    if d.get('b64_json') or d.get('b64Json'): return base64.b64decode(d.get('b64_json') or d.get('b64Json')), 200, ''
    if d.get('url'): return requests.get(d['url'], timeout=120).content, 200, ''
    return None, 500, 'empty data'

def generate(prompt, out, size='1536x1024', refs=None, tries=2, timeout=180, chain=None):
    """Returns {'file','model','seconds','fallback':bool,'log':[...]}. Raises if all models fail."""
    chain = chain or CHAIN; log = []; t0 = time.time()
    primaries_exhausted = 0
    for model in chain:
        is_primary = model in PRIMARY
        if not is_primary and primaries_exhausted < len([m for m in chain if m in PRIMARY]):
            log.append(f'skip {model}: primary models not quota-exhausted, refusing to downgrade'); break
        for attempt in range(tries):
            try:
                data, status, err = _call(model, prompt, size, refs or [], timeout)
            except Exception as e:
                data, status, err = None, 0, f'{type(e).__name__}: {e}'
            if data:
                Path(out).parent.mkdir(parents=True, exist_ok=True); Path(out).write_bytes(data)
                return {'file': str(out), 'model': model, 'seconds': round(time.time() - t0, 1), 'fallback': not is_primary, 'log': log}
            log.append(f'{model} try{attempt + 1}: HTTP {status} {err[:160]}')
            if is_quota_error(status, err):
                if is_primary: primaries_exhausted += 1
                break
            time.sleep(2 * (attempt + 1))
        else:
            continue
    raise RuntimeError('image generation failed:\n  ' + '\n  '.join(log))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('prompt'); ap.add_argument('-o', '--out', required=True)
    ap.add_argument('--size', default='1536x1024'); ap.add_argument('--ref', action='append', default=[])
    ap.add_argument('--model', help='force one model (no fallback)'); a = ap.parse_args()
    res = generate(a.prompt, a.out, a.size, a.ref, chain=[a.model] if a.model else None)
    print(json.dumps(res, ensure_ascii=False))

if __name__ == '__main__': main()
