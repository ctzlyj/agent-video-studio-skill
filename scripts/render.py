"""Render the HTML project to video with headless Chromium (frame-by-frame, deterministic).

  python scripts/render.py [project] --preview            # 960px, 12fps quick look -> out/preview.mp4
  python scripts/render.py [project] --stills 3,12.5,40   # PNG stills -> qa/
  python scripts/render.py [project] --sheet              # one still per scene -> qa/contact_sheet.jpg
  python scripts/render.py [project] --final              # full-res -> out/<title>.mp4 with audio
"""
from __future__ import annotations
import argparse, asyncio, functools, http.server, json, os, re, socketserver, subprocess, sys, threading, time
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
from avs_common import project_dir, load_json, ffmpeg, run, SKILL_DIR

def sync_runtime(d: Path):
    for f in ('avs-runtime.js',):
        src = SKILL_DIR / 'assets' / 'template' / f; dst = d / f
        if not dst.exists() or dst.read_bytes() != src.read_bytes(): dst.write_bytes(src.read_bytes())
    p = load_json(d / 'project.json')
    (d / 'project.js').write_text('window.PROJECT=' + json.dumps(p, ensure_ascii=False) + ';', encoding='utf-8')
    if not (d / 'videos.js').exists(): (d / 'videos.js').write_text('window.VIDEOS={};', encoding='utf-8')

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

def safe_name(s): return re.sub(r'[\\/:*?"<>|\s]+', '_', s).strip('_') or 'video'

async def _render(d, a):
    from playwright.async_api import async_playwright
    tl = load_json(d / 'timeline.json'); W, H = tl['width'], tl['height']
    httpd = socketserver.TCPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(d))); port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    scale = 960 / W if a.preview or a.sheet else 1.0
    async with async_playwright() as pw:
        b = await pw.chromium.launch(args=['--disable-gpu-vsync', '--disable-frame-rate-limit', '--force-color-profile=srgb'])
        pg = await b.new_page(viewport={'width': W, 'height': H}, device_scale_factor=scale)
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(f'http://127.0.0.1:{port}/index.html')
        try: await pg.wait_for_function('window.READY===true || !!window.AVS_ERROR', timeout=120000)
        except Exception: pass
        err = await pg.evaluate('window.AVS_ERROR || null')
        if err or errs: sys.exit('page error:\n' + (err or '\n'.join(errs)))
        qa = d / 'qa'; qa.mkdir(exist_ok=True); out = d / 'out'; out.mkdir(exist_ok=True)
        if a.stills or a.sheet:
            ts = [float(x) for x in a.stills.split(',')] if a.stills else [round(s['ns'] + min(s['nd'] * .62, s['nd'] - .3), 2) for s in tl['scenes']]
            files = []
            for t in ts:
                await pg.evaluate(f'window.render({t})'); f = qa / f'still_{t:07.2f}.png'; await pg.screenshot(path=str(f)); files.append(f)
            if errs: sys.exit('page error:\n' + '\n'.join(errs))
            if a.sheet:
                from PIL import Image, ImageDraw
                ims = [Image.open(f).convert('RGB') for f in files]; tw = 480; th = int(tw * H / W); cols = 4
                sheet = Image.new('RGB', (tw * cols, (th + 26) * ((len(ims) + cols - 1) // cols)), (20, 20, 20)); dr = ImageDraw.Draw(sheet)
                for i, (im, s) in enumerate(zip(ims, tl['scenes'])):
                    x, y = (i % cols) * tw, (i // cols) * (th + 26); sheet.paste(im.resize((tw, th)), (x, y + 26)); dr.text((x + 6, y + 6), f"{s['id']}  {s['ns']:.1f}s", fill=(230, 230, 230))
                sheet.save(qa / 'contact_sheet.jpg', quality=88); print(qa / 'contact_sheet.jpg')
            else: print('\n'.join(map(str, files)))
        if a.preview or a.final:
            fps = 12 if a.preview else tl['fps']; n = round(tl['duration'] * fps)
            silent = out / ('_preview_silent.mp4' if a.preview else '_final_silent.mp4')
            enc = ['-preset', 'veryfast', '-crf', '26'] if a.preview else ['-preset', 'medium', '-crf', '17']
            proc = subprocess.Popen([ffmpeg(), '-y', '-hide_banner', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(fps), '-i', '-',
                                     '-c:v', 'libx264', *enc, '-pix_fmt', 'yuv420p', '-color_range', 'tv', '-movflags', '+faststart', str(silent)], stdin=subprocess.PIPE)
            t0 = time.time()
            for i in range(n):
                await pg.evaluate(f'window.render({i / fps})'); proc.stdin.write(await pg.screenshot(type='jpeg', quality=92))
                if errs: proc.kill(); sys.exit('page error at frame %d:\n%s' % (i, '\n'.join(errs)))
                if i % 300 == 0: print(f'frame {i}/{n}  {time.time() - t0:.0f}s', flush=True)
            proc.stdin.close(); proc.wait()
            mix = d / 'audio' / 'mix.wav'
            name = 'preview.mp4' if a.preview else safe_name(load_json(d / 'project.json').get('title', 'video')) + '.mp4'
            final = out / name
            if mix.exists():
                run([ffmpeg(), '-y', '-hide_banner', '-loglevel', 'error', '-i', silent, '-i', mix, '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', final])
            else: silent.replace(final)
            silent.unlink(missing_ok=True); print('done', final, f'{time.time() - t0:.0f}s')
        await b.close()
    httpd.shutdown()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('project', nargs='?')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--preview', action='store_true'); g.add_argument('--final', action='store_true')
    g.add_argument('--stills'); g.add_argument('--sheet', action='store_true')
    a = ap.parse_args(); d = project_dir(a.project); sync_runtime(d); asyncio.run(_render(d, a))

if __name__ == '__main__': main()
