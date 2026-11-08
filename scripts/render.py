"""Render the HTML project to video with headless Chromium (frame-by-frame, deterministic).

  python scripts/render.py [project] --preview            # 960px, 12fps quick look -> out/preview.mp4
  python scripts/render.py [project] --stills 3,12.5,40   # PNG stills -> qa/
  python scripts/render.py [project] --sheet              # one still per scene -> qa/contact_sheet.jpg
  python scripts/render.py [project] --final              # full-res -> out/<title>.mp4 with audio
  options for --preview/--final:
    --mb N         motion blur: N sub-frame samples per output frame averaged (default 1 = off; 4-6 is a good look)
    --shutter S    shutter angle as a fraction of one frame (default 0.5)
    --workers N    N browsers render different time ranges in parallel (default 1); output is the same frames
  project.json may set the same defaults: "render": {"motionBlur": {"samples": 4, "shutter": 0.5}, "workers": 3}
"""
from __future__ import annotations
import argparse, asyncio, functools, http.server, json, os, re, socketserver, subprocess, sys, threading, time
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
from avs_common import project_dir, load_json, ffmpeg, run, SKILL_DIR, safe_name

def sync_runtime(d: Path):
    for f in ('avs-runtime.js',):
        src = SKILL_DIR / 'assets' / 'template' / f; dst = d / f
        if not dst.exists() or dst.read_bytes() != src.read_bytes(): dst.write_bytes(src.read_bytes())
    p = load_json(d / 'project.json')
    (d / 'project.js').write_text('window.PROJECT=' + json.dumps(p, ensure_ascii=False) + ';', encoding='utf-8')
    if not (d / 'videos.js').exists(): (d / 'videos.js').write_text('window.VIDEOS={};', encoding='utf-8')

def preview_scale(W, H, long_side=960):
    """Device scale so the long side is ~long_side px AND both output sides are even (libx264 rejects odd sizes).
    Landscape 1920x1080 -> 960x540; portrait 1080x1920 -> 540x960 (a width-based 960 would give 960x1707)."""
    s = long_side / max(W, H)
    for k in range(0, 200):
        for cand in (s - k * .0005, s + k * .0005):
            if cand > 0 and round(W * cand) % 2 == 0 and round(H * cand) % 2 == 0 and abs(W * cand - round(W * cand)) < 1e-6 and abs(H * cand - round(H * cand)) < 1e-6: return cand
    return 1.0

def browser_launch_help(e) -> str:
    """Turn a raw Playwright launch failure into one actionable line (distinguishes 'not installed' from 'blocked by a sandbox')."""
    msg = str(e)
    if "Executable doesn't exist" in msg or 'playwright install' in msg: return 'Chromium is not installed. Run: python -m playwright install chromium'
    if 'Operation not permitted' in msg or 'Permission denied' in msg or 'sandbox' in msg.lower(): return 'Chromium is installed but the sandbox blocked it from starting. Re-run this command with the sandbox disabled / network-and-process permission granted (it only starts a local headless browser).'
    return 'Chromium failed to start: ' + msg.splitlines()[0][:300]

LAUNCH_ARGS = ['--disable-gpu-vsync', '--disable-frame-rate-limit', '--force-color-profile=srgb', '--allow-file-access-from-files']

# Chrome frames are sRGB. Convert to YUV with the BT.709 matrix and tag the stream, otherwise players guess 601 and saturated colours shift.
COLOR_VF = 'scale=out_color_matrix=bt709:out_range=tv:flags=lanczos+accurate_rnd+full_chroma_int,format=yuv420p'
COLOR_TAGS = ['-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv']

def sample_times(f, fps, mb, shutter, duration):
    """Times (seconds) rendered for output frame f. One sample = the frame time. With mb > 1 the samples are spread
    evenly across the shutter window centred on the frame, clamped to [0, duration); averaging them gives motion blur."""
    if mb <= 1: return [f / fps]
    return [min(max(0.0, (f + shutter * ((s + .5) / mb - .5)) / fps), duration - 1e-3) for s in range(mb)]

def plan_chunks(n, workers):
    """Split frames [0, n) into at most `workers` contiguous (start, end) ranges that cover every frame exactly once."""
    w = max(1, min(int(workers), n)); size = -(-n // w)
    return [(a, min(n, a + size)) for a in range(0, n, size)]

def render_settings(a, project):
    """(mb, shutter, workers): command line wins over project.json "render", else off / 0.5 / 1."""
    r = project.get('render') or {}; m = r.get('motionBlur') or {}
    mb = max(1, int(a.mb if a.mb is not None else m.get('samples', 1)))
    shutter = float(a.shutter if a.shutter is not None else m.get('shutter', .5))
    workers = max(1, int(a.workers if a.workers is not None else r.get('workers', 1)))
    return mb, shutter, workers
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def handle(self):  # the browser resets connections it no longer needs; that is not an error
        try: super().handle()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError): pass


def start_server(d: Path):
    """Serve the project over loopback HTTP. Returns (httpd, base_url). If the OS / sandbox refuses to bind a socket
    (macOS sandboxes report PermissionError [Errno 1] Operation not permitted), returns (None, file:// url): the page
    renders identically from file:// because every asset is a relative path."""
    try:
        httpd = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(d))); httpd.daemon_threads = True  # threaded: the page fetches several scripts at once
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        return httpd, f'http://127.0.0.1:{httpd.server_address[1]}/index.html'
    except OSError as e:
        print(f'note: cannot open a local server ({e.strerror or e}); rendering from file:// instead (same result).', file=sys.stderr)
        return None, (d / 'index.html').resolve().as_uri()

async def _render(d, a):
    from playwright.async_api import async_playwright
    tl = load_json(d / 'timeline.json'); W, H = tl['width'], tl['height']
    httpd, url = start_server(d)
    scale = preview_scale(W, H) if a.preview or a.sheet else 1.0
    async with async_playwright() as pw:
        try: b = await pw.chromium.launch(args=LAUNCH_ARGS)
        except Exception as e: sys.exit(browser_launch_help(e))
        pg = await b.new_page(viewport={'width': W, 'height': H}, device_scale_factor=scale)
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(url)
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
            proj = load_json(d / 'project.json')
            mb, shutter, workers = render_settings(a, proj)
            if a.preview and a.mb is None: mb = 1            # quick looks stay quick unless blur is asked for
            fps = 12 if a.preview else tl['fps']; n = round(tl['duration'] * fps); dur = tl['duration']
            chunks = plan_chunks(n, workers)
            enc = ['-preset', 'veryfast', '-crf', '26'] if a.preview else ['-preset', 'medium', '-crf', '17']
            vf = ['-vf', (f"tmix=frames={mb},select='eq(mod(n\\,{mb})\\,{mb - 1})',setpts=N/({fps}*TB)," if mb > 1 else '') + COLOR_VF] + (['-r', str(fps)] if mb > 1 else [])
            t0 = time.time(); done = [0]
            print(f'render {n} frames @ {fps}fps  motion-blur samples={mb} shutter={shutter}  browsers={len(chunks)}', flush=True)

            async def do_chunk(w, lo, hi, page, page_errs):
                seg = out / f'_seg_{w:02d}.mp4'
                proc = subprocess.Popen([ffmpeg(), '-y', '-hide_banner', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(fps * mb), '-i', '-', *vf,
                                         '-c:v', 'libx264', *enc, *COLOR_TAGS, '-movflags', '+faststart', str(seg)], stdin=subprocess.PIPE)
                for i in range(lo, hi):
                    for ts in sample_times(i, fps, mb, shutter, dur):
                        await page.evaluate(f'window.render({ts})'); proc.stdin.write(await page.screenshot(type='jpeg', quality=92))
                    if page_errs: proc.kill(); raise RuntimeError('page error at frame %d:\n%s' % (i, '\n'.join(page_errs)))
                    done[0] += 1
                    if done[0] % 300 == 0: print(f'frame {done[0]}/{n}  {time.time() - t0:.0f}s', flush=True)
                proc.stdin.close(); proc.wait()
                if proc.returncode: raise RuntimeError(f'ffmpeg failed on segment {w}')
                return seg

            extra = []
            async def open_worker():
                nb = await pw.chromium.launch(args=LAUNCH_ARGS); extra.append(nb)
                p2 = await nb.new_page(viewport={'width': W, 'height': H}, device_scale_factor=scale); e2 = []; p2.on('pageerror', lambda e: e2.append(str(e)))
                await p2.goto(url)
                try: await p2.wait_for_function('window.READY===true || !!window.AVS_ERROR', timeout=120000)
                except Exception: pass
                err2 = await p2.evaluate('window.AVS_ERROR || null')
                if err2 or e2: raise RuntimeError('page error:\n' + (err2 or '\n'.join(e2)))
                return p2, e2
            try:
                jobs = [do_chunk(0, *chunks[0], pg, errs)]
                for w, (lo, hi) in enumerate(chunks[1:], 1):
                    p2, e2 = await open_worker(); jobs.append(do_chunk(w, lo, hi, p2, e2))
                segs = await asyncio.gather(*jobs)
            except RuntimeError as ex:
                for s in out.glob('_seg_*.mp4'): s.unlink(missing_ok=True)
                sys.exit(str(ex))
            finally:
                for nb in extra: await nb.close()
            silent = out / ('_preview_silent.mp4' if a.preview else '_final_silent.mp4')
            if len(segs) == 1: segs[0].replace(silent)
            else:
                lst = out / '_seg_list.txt'
                lst.write_text(''.join("file '%s'\n" % s.resolve().as_posix().replace("'", "'\\''") for s in segs), encoding='utf-8')
                run([ffmpeg(), '-y', '-hide_banner', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', '-movflags', '+faststart', silent])
                lst.unlink(missing_ok=True)
                for s in segs: s.unlink(missing_ok=True)
            mix = d / 'audio' / 'mix.wav'
            name = 'preview.mp4' if a.preview else safe_name(proj.get('title', 'video')) + '.mp4'
            final = out / name
            if mix.exists():
                run([ffmpeg(), '-y', '-hide_banner', '-loglevel', 'error', '-i', silent, '-i', mix, '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', final])
            else: silent.replace(final)
            silent.unlink(missing_ok=True); print('done', final, f'{time.time() - t0:.0f}s')
        await b.close()
    if httpd: httpd.shutdown()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('project', nargs='?')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--preview', action='store_true'); g.add_argument('--final', action='store_true')
    g.add_argument('--stills'); g.add_argument('--sheet', action='store_true')
    ap.add_argument('--mb', type=int); ap.add_argument('--shutter', type=float); ap.add_argument('--workers', type=int)
    a = ap.parse_args(); d = project_dir(a.project); sync_runtime(d); asyncio.run(_render(d, a))

if __name__ == '__main__': main()
