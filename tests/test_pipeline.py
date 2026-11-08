import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))

def proj(tmp, **over):
    p = {"title": "T", "brand": {"terms": {"旧名": "新名"}, "banned": ["禁词"]},
         "style": {"fps": 30, "width": 1920, "height": 1080},
         "voice": {"engine": "none"},
         "scenes": [{"id": "s01", "type": "title", "vo": "第一句，你好。", "speed": 1.0, "pad": 1.0, "data": {"title": "标题"}},
                    {"id": "s02", "type": "title", "vo": "第二句话稍长一点。", "speed": 1.25, "pad": 0.8, "data": {"title": "新名"}}]}
    p.update(over); (Path(tmp) / 'project.json').write_text(json.dumps(p, ensure_ascii=False), encoding='utf-8'); return Path(tmp)

class TimelineTest(unittest.TestCase):
    def test_speed_compresses_scene_and_subs(self):
        import timeline
        with tempfile.TemporaryDirectory() as t:
            d = proj(t); vo = {'s01': 2.0, 's02': 4.0}
            tl = timeline.build(json.loads((d / 'project.json').read_text(encoding='utf-8')), vo)
            s1, s2 = tl['scenes']
            self.assertAlmostEqual(s1['nd'], 0.45 + 2.0 + 1.0, 3)          # lead + vo + pad, speed 1
            self.assertAlmostEqual(s2['nd'], (0.45 + 4.0 + 0.8) / 1.25, 3)
            self.assertAlmostEqual(s2['ns'], s1['nd'], 3)
            self.assertAlmostEqual(tl['duration'], s1['nd'] + s2['nd'], 3)
            last = [x for x in tl['subs'] if x['scene'] == 's02'][-1]
            self.assertLessEqual(last['e'], s2['ns'] + s2['nd'])            # subs stay inside their scene after speed-up

class LintTest(unittest.TestCase):
    def test_flags_old_terms_banned_words_and_absolute_paths(self):
        import lint
        with tempfile.TemporaryDirectory() as t:
            d = proj(t); p = json.loads((d / 'project.json').read_text(encoding='utf-8'))
            p['scenes'][0]['vo'] = '这是旧名和禁词'; p['scenes'][1]['data']['img'] = 'C:/Users/x/a.png'
            issues = lint.check(p, d)
            kinds = {i['kind'] for i in issues}
            self.assertIn('term', kinds); self.assertIn('banned', kinds); self.assertIn('abs_path', kinds)

    def test_flags_missing_asset_and_screen_text_equal_to_subtitle(self):
        import lint
        with tempfile.TemporaryDirectory() as t:
            d = proj(t); p = json.loads((d / 'project.json').read_text(encoding='utf-8'))
            p['scenes'][1]['data']['video'] = 'assets/nope.mp4'
            p['scenes'][0]['data']['caption'] = '第一句，你好'
            kinds = {i['kind'] for i in lint.check(p, d)}
            self.assertIn('missing_asset', kinds); self.assertIn('dup_subtitle', kinds)

    def test_clean_project_passes(self):
        import lint
        with tempfile.TemporaryDirectory() as t:
            d = proj(t); self.assertEqual([i for i in lint.check(json.loads((d / 'project.json').read_text(encoding='utf-8')), d) if i['level'] == 'error'], [])

class ImageTest(unittest.TestCase):
    def test_only_quota_errors_trigger_fallback(self):
        import imagegen
        self.assertTrue(imagegen.is_quota_error(429, '{"code":2007}'))
        self.assertTrue(imagegen.is_quota_error(400, '额度已用尽'))
        self.assertFalse(imagegen.is_quota_error(500, 'upstream timeout'))
        self.assertEqual(imagegen.CHAIN[:2], ['GPT-Image-2.5-Flare-joybuilder', 'GPT-Image-2.5-Sunburst-joybuilder'])


class FallbackPolicyTest(unittest.TestCase):
    def _run(self, responses):
        import imagegen
        calls = []
        def fake(model, prompt, size, refs, timeout):
            calls.append(model); return responses.get(model, (None, 500, 'boom'))
        orig = imagegen._call; imagegen._call = fake; imagegen.time.sleep = lambda s: None
        try:
            with tempfile.TemporaryDirectory() as t:
                try: res = imagegen.generate('p', Path(t) / 'a.png', tries=1)
                except RuntimeError: res = None
        finally: imagegen._call = orig
        return res, calls

    def test_transient_error_does_not_downgrade(self):
        res, calls = self._run({})
        self.assertIsNone(res)
        self.assertNotIn('GPT-image-2-joybuilder', calls)

    def test_downgrade_only_after_both_gpt25_quota(self):
        q = (None, 429, 'quota')
        res, calls = self._run({'GPT-Image-2.5-Flare-joybuilder': q, 'GPT-Image-2.5-Sunburst-joybuilder': q, 'GPT-image-2-joybuilder': (b'x', 200, '')})
        self.assertEqual(res['model'], 'GPT-image-2-joybuilder'); self.assertTrue(res['fallback'])

    def test_sunburst_used_when_flare_quota(self):
        res, calls = self._run({'GPT-Image-2.5-Flare-joybuilder': (None, 429, 'quota'), 'GPT-Image-2.5-Sunburst-joybuilder': (b'x', 200, '')})
        self.assertEqual(res['model'], 'GPT-Image-2.5-Sunburst-joybuilder'); self.assertFalse(res['fallback'])




class PerSceneSubtitleTest(unittest.TestCase):
    def test_scene_can_disable_subtitle(self):
        import timeline
        with tempfile.TemporaryDirectory() as t:
            d = proj(t); p = json.loads((d / 'project.json').read_text(encoding='utf-8')); p['scenes'][0]['subtitle'] = False
            tl = timeline.build(p, {'s01': 2.0, 's02': 3.0})
            self.assertEqual({x['scene'] for x in tl['subs']}, {'s02'})



class TimedSubsTest(unittest.TestCase):
    def test_explicit_subs_follow_scene_speed(self):
        import timeline
        with tempfile.TemporaryDirectory() as t:
            d = proj(t); p = json.loads((d / 'project.json').read_text(encoding='utf-8'))
            p['scenes'][1].update({'vo': '', 'dur': 10, 'speed': 1.0, 'subs': [[2.0, 4.0, '台词']]})
            tl = timeline.build(p, {'s01': 2.0})
            sub = [x for x in tl['subs'] if x['scene'] == 's02'][0]
            s2 = tl['scenes'][1]
            self.assertAlmostEqual(sub['s'], s2['ns'] + 2.0, 3); self.assertEqual(sub['text'], '台词')


class ScoreTest(unittest.TestCase):
    SC = [{'ns': 0, 'nd': 6}, {'ns': 6, 'nd': 8}, {'ns': 14, 'nd': 8}, {'ns': 22, 'nd': 6}]

    def test_energy_from_mood_and_explicit_energy(self):
        import score
        e = score.energies_for([{'mood': 'calm'}, {'mood': 'climax'}, {'energy': .6}, {'mood': 'silent'}])
        self.assertEqual(e, [score.MOODS['calm'], score.MOODS['climax'], .6, 0.0])

    def test_default_arc_when_untagged(self):
        import score
        e = score.energies_for([{} for _ in range(8)]); self.assertGreater(max(e), e[0]); self.assertLess(e[-1], max(e))

    def test_voice_leading_keeps_chords_close(self):
        import score
        for style in score.STYLES:
            vs = score.voicings(style, 0, 'major', 6)
            for a, b in zip(vs, vs[1:]): self.assertLessEqual(abs(sum(a) / len(a) - sum(b) / len(b)), 6, style)

    def test_every_style_renders_follows_energy_and_is_deterministic(self):
        import score
        en = [.25, .55, .9, .3]
        for style in score.STYLES:
            bed, info = score.render(style, self.SC, en, 28); rep = score.analyze(bed, self.SC, en)
            self.assertTrue(rep['noClip'], style); self.assertTrue(rep['arcOk'], f"{style}: {rep['arcNote']}")
            bed2, _ = score.render(style, self.SC, en, 28); self.assertTrue((bed == bed2).all(), style)

    def test_silent_scene_is_silent_and_seed_changes_output(self):
        import score
        bed, _ = score.render('warm', self.SC, [.3, 0.0, .5, .3], 28)
        loud = float(abs(bed[int(0 * score.SR):int(6 * score.SR)]).max()); tail = float(abs(bed[int(10 * score.SR):int(13.5 * score.SR)]).max())
        self.assertLess(tail, loud * .12)  # previous scene's reverb tail has decayed; no new notes in the silent scene
        a, _ = score.render('warm', self.SC, [.5] * 4, 28, seed=1); b, _ = score.render('warm', self.SC, [.5] * 4, 28, seed=2)
        self.assertFalse((a == b).all())

    def test_style_pick_and_key_parse(self):
        import score
        self.assertEqual(score.pick_style('auto', 'documentary'), 'cinematic'); self.assertEqual(score.pick_style('auto', None), 'warm')
        self.assertEqual(score.parse_key('D minor'), ('D', 'minor')); self.assertEqual(score.parse_key(None), (None, None))
        with self.assertRaises(ValueError): score.pick_style('nope')
        with self.assertRaises(ValueError): score.parse_key('D weird')

    def test_lint_checks_music_config(self):
        import lint
        with tempfile.TemporaryDirectory() as t:
            d = proj(t, music={'style': 'warm'}); p = json.loads((d / 'project.json').read_text(encoding='utf-8'))
            self.assertIn('mood', {i['kind'] for i in lint.check(p, d)})            # untagged -> warn
            p['scenes'][0]['mood'] = 'epic'; p['music'] = {'style': 'bogus'}
            kinds = [i['kind'] for i in lint.check(p, d) if i['level'] == 'error']
            self.assertIn('music', kinds); self.assertIn('mood', kinds)
            p['music'] = {'style': 'warm'}; p['scenes'][0]['mood'] = 'calm'; p['scenes'][1]['energy'] = .8
            self.assertEqual([i for i in lint.check(p, d) if i['level'] == 'error' or i['kind'] == 'mood'], [])

    def test_audio_script_writes_score_report(self):
        import audio, score, wave
        with tempfile.TemporaryDirectory() as t:
            d = proj(t, music={'style': 'auto'}, route='documentary'); d.joinpath('audio').mkdir()
            tl = {'duration': 14.0, 'scenes': [{'id': 's01', 'ns': 0, 'nd': 6, 'speed': 1.0, 'voStart': .45, 'voDur': 0}, {'id': 's02', 'ns': 6, 'nd': 8, 'speed': 1.0, 'voStart': .45, 'voDur': 0}], 'subs': []}
            d.joinpath('timeline.json').write_text(json.dumps(tl), encoding='utf-8')
            r = subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'audio.py'), str(d)], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(r.returncode, 0, r.stderr); rep = json.loads((d / 'audio' / 'score_report.json').read_text(encoding='utf-8'))
            self.assertEqual(rep['style'], 'cinematic'); self.assertTrue((d / 'audio' / 'mix.wav').exists())



class BuiltinTrackTest(unittest.TestCase):
    SC = [{'ns': 0, 'nd': 6}, {'ns': 6, 'nd': 8}, {'ns': 14, 'nd': 8}, {'ns': 22, 'nd': 6}]

    def test_source_priority_and_default(self):
        import bgm
        self.assertEqual(bgm.resolve(None, 'promo'), 'track'); self.assertEqual(bgm.resolve({}, 'documentary'), 'track')
        self.assertEqual(bgm.resolve({}, 'ai-comic-drama'), 'style'); self.assertEqual(bgm.resolve({}, 'hybrid'), 'track')
        self.assertEqual(bgm.resolve({'generate': 'none'}, 'promo'), 'generate'); self.assertEqual(bgm.resolve({'style': 'warm'}, 'promo'), 'style')
        self.assertEqual(bgm.resolve({'file': 'assets/x.mp3', 'style': 'warm', 'generate': 'none'}, 'promo'), 'file')
        with self.assertRaises(ValueError): bgm.resolve({'track': 'nope'}, 'promo')

    def test_track_file_is_bundled(self):
        import bgm
        for spec in bgm.TRACKS.values(): self.assertTrue((SK / spec['file']).exists(), spec['file'])

    def test_render_follows_energy_loops_and_fades(self):
        import bgm, score
        en = [.25, .55, .9, .3]; bed, info = bgm.render('default', self.SC, en, 28); rep = score.analyze(bed, self.SC, en)
        self.assertTrue(rep['noClip'] and rep['arcOk'], rep['arcNote'])
        self.assertEqual(float(abs(bed[int(28 * bgm.SR):]).max()), 0.0); self.assertLess(float(abs(bed[int(27.8 * bgm.SR):int(28 * bgm.SR)]).max()), .05)
        long, _ = bgm.render('default', [{'ns': 0, 'nd': 170}], [.5], 170); tail = long[int(160 * bgm.SR):int(166 * bgm.SR)]
        self.assertGreater(float(abs(tail).max()), .02)                                    # looped, not silent after the 160 s track ends

    def test_silent_scene_drops_out(self):
        import bgm
        bed, _ = bgm.render('default', self.SC, [.5, 0.0, .5, .5], 28)
        loud = float(abs(bed[int(2 * bgm.SR):int(5 * bgm.SR)]).max()); quiet = float(abs(bed[int(9 * bgm.SR):int(12 * bgm.SR)]).max())
        self.assertLess(quiet, loud * .1)

    def test_audio_script_uses_track_by_default_and_user_choice_overrides(self):
        with tempfile.TemporaryDirectory() as t:
            d = proj(t, route='promo'); d.joinpath('audio').mkdir()
            tl = {'duration': 14.0, 'scenes': [{'id': 's01', 'ns': 0, 'nd': 6, 'speed': 1.0, 'voStart': .45, 'voDur': 0}, {'id': 's02', 'ns': 6, 'nd': 8, 'speed': 1.0, 'voStart': .45, 'voDur': 0}], 'subs': []}
            d.joinpath('timeline.json').write_text(json.dumps(tl), encoding='utf-8')
            def run(music):
                p = json.loads((d / 'project.json').read_text(encoding='utf-8')); p['music'] = music
                if music is None: p.pop('music')
                (d / 'project.json').write_text(json.dumps(p, ensure_ascii=False), encoding='utf-8')
                r = subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'audio.py'), str(d)], capture_output=True, text=True, encoding='utf-8'); self.assertEqual(r.returncode, 0, r.stderr); return r.stdout
            self.assertIn('built-in track', run(None)); rep = json.loads((d / 'audio' / 'score_report.json').read_text(encoding='utf-8')); self.assertEqual(rep['style'], 'track:default')
            self.assertIn('score: warm', run({'style': 'warm'})); self.assertNotIn('built-in', run({'generate': 'none'}))


class FinalizeTest(unittest.TestCase):
    def test_srt_text_is_speed_mapped_and_numbered(self):
        import finalize
        out = finalize.srt_text({'subs': [{'s': 0.45, 'e': 4.09, 'text': '第一句'}, {'s': 3661.5, 'e': 3662.0, 'text': '第二句'}, {'s': 5, 'e': 6, 'text': ''}]})
        self.assertIn('1\n00:00:00,450 --> 00:00:04,090\n第一句\n', out); self.assertIn('2\n01:01:01,500 --> 01:01:02,000\n第二句\n', out); self.assertNotIn('3\n', out)

    def test_loudness_is_measured_and_normalised_to_target(self):
        import finalize
        from avs_common import ffmpeg
        ff = ffmpeg()
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / 'in.mp4'
            r = subprocess.run([ff, '-y', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=160x90:d=6:r=10', '-f', 'lavfi', '-i', 'sine=f=300:d=6', '-af', 'volume=-31dB', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(src)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            before, _ = finalize.measure(ff, src); self.assertLess(before, -25)
            out = Path(t) / 'out.mp4'; finalize.normalise_audio(ff, src, out, -16.0, t)
            after, tp = finalize.measure(ff, out); self.assertLess(abs(after + 16.0), 1.2); self.assertLessEqual(tp, -1.0)
            self.assertEqual(finalize.decode_errors(ff, out), [])

    def test_script_refuses_overwrite_and_bad_target(self):
        with tempfile.TemporaryDirectory() as t:
            d = proj(t); (d / 'out').mkdir(); (d / 'deliver').mkdir(); (d / 'deliver' / 'T.mp4').write_bytes(b'x'); (d / 'out' / 'T.mp4').write_bytes(b'x')
            (d / 'timeline.json').write_text(json.dumps({'duration': 1, 'scenes': [], 'subs': []}), encoding='utf-8')
            run = lambda *a: subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'finalize.py'), str(d), *a], capture_output=True, text=True, encoding='utf-8')
            r = run(); self.assertNotEqual(r.returncode, 0); self.assertIn('refusing to overwrite', r.stderr + r.stdout)
            r = run('--lufs', '-3'); self.assertNotEqual(r.returncode, 0); self.assertIn('between', r.stderr + r.stdout)


class LintLengthTest(unittest.TestCase):
    def test_long_subtitle_and_long_narration_warn(self):
        import lint
        with tempfile.TemporaryDirectory() as t:
            d = proj(t); p = json.loads((d / 'project.json').read_text(encoding='utf-8'))
            p['scenes'][0]['vo'] = '没有任何标点的一个特别特别特别特别特别特别特别特别特别特别特别长的句子' + '啊' * 10
            kinds = {i['kind'] for i in lint.check(p, d)}; self.assertNotIn('sub_long', kinds)          # unpunctuated text is hard-split by split_sub
            p['scenes'][1]['vo'] = '字' * 130 + '。'; kinds = {i['kind'] for i in lint.check(p, d)}; self.assertIn('vo_long', kinds)

    def test_audio_writes_companion_track_without_music(self):
        with tempfile.TemporaryDirectory() as t:
            d = proj(t, route='promo'); (d / 'audio').mkdir()
            tl = {'duration': 8.0, 'scenes': [{'id': 's01', 'ns': 0, 'nd': 8, 'speed': 1.0, 'voStart': .45, 'voDur': 0}], 'subs': []}
            (d / 'timeline.json').write_text(json.dumps(tl), encoding='utf-8')
            r = subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'audio.py'), str(d)], capture_output=True, text=True, encoding='utf-8'); self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((d / 'audio' / 'vo_sfx.wav').exists()); self.assertTrue((d / 'audio' / 'mix.wav').exists())


class SceneVoiceTest(unittest.TestCase):
    def test_scene_voice_override_changes_hash_and_is_passed_to_engine(self):
        import voice
        seen = {}
        def fake(engine, text, cfg, out):
            seen[text] = (cfg.get('rate'), cfg.get('pitch')); Path(out).write_bytes(b'x')
        orig_s, orig_d = voice.synth, voice.media_duration; voice.synth = fake; voice.media_duration = lambda p: 1.0
        try:
            with tempfile.TemporaryDirectory() as t:
                d = proj(t, voice={'engine': 'edge', 'voice': 'v', 'rate': '+0%', 'pitch': '+0Hz'})
                p = json.loads((d / 'project.json').read_text(encoding='utf-8')); p['scenes'][1]['voiceCfg'] = {'rate': '-10%', 'pitch': '-4Hz'}
                (d / 'project.json').write_text(json.dumps(p, ensure_ascii=False), encoding='utf-8')
                old = sys.argv; sys.argv = ['voice.py', str(d)]
                try: voice.main()
                finally: sys.argv = old
                self.assertEqual(seen['第一句，你好。'], ('+0%', '+0Hz')); self.assertEqual(seen['第二句话稍长一点。'], ('-10%', '-4Hz'))
                h1 = json.loads((d / 'audio' / 'vo' / 's01.json').read_text(encoding='utf-8'))['hash']; h2 = json.loads((d / 'audio' / 'vo' / 's02.json').read_text(encoding='utf-8'))['hash']; self.assertNotEqual(h1, h2)
        finally: voice.synth, voice.media_duration = orig_s, orig_d


class PreviewScaleTest(unittest.TestCase):
    def test_even_sizes_for_every_supported_format(self):
        import render
        for W, H in ((1920, 1080), (1080, 1920), (1080, 1080), (1440, 1080), (1080, 1440)):
            s = render.preview_scale(W, H)
            w, h = W * s, H * s
            self.assertAlmostEqual(w, round(w), 6); self.assertAlmostEqual(h, round(h), 6)
            self.assertEqual(round(w) % 2, 0, (W, H)); self.assertEqual(round(h) % 2, 0, (W, H)); self.assertLessEqual(max(w, h), 1000)
        self.assertEqual((round(1920 * render.preview_scale(1920, 1080)), round(1080 * render.preview_scale(1920, 1080))), (960, 540))
        self.assertEqual((round(1080 * render.preview_scale(1080, 1920)), round(1920 * render.preview_scale(1080, 1920))), (540, 960))


class TruePeakAfterAacTest(unittest.TestCase):
    def test_pre_aac_ceiling_leaves_headroom_for_encoder_overshoot(self):
        """Regression (2026-11 film): loudnorm held TP at -1.5 in the WAV, but AAC pushed it to -0.3 dBTP and finalize.py (rightly) rejected the film.
        The ceiling before the encode must therefore be at least ~1 dB lower than the delivery limit."""
        import finalize
        self.assertLessEqual(finalize.PRE_AAC_TP, finalize.MAX_TP - 1.0)

    def test_dense_transients_stay_under_limit_after_aac(self):
        import finalize, wave, numpy as np
        from avs_common import ffmpeg
        ff = ffmpeg(); sr = 48000
        with tempfile.TemporaryDirectory() as t:
            rng = np.random.default_rng(5); n = sr * 10; x = .08 * np.sin(2 * np.pi * 330 * np.arange(n) / sr)
            for s in range(0, n - 2400, int(sr * .35)):                      # dense broadband bursts every 0.35 s: many sample peaks inside each AAC frame
                x[s:s + 2400] += rng.uniform(-.9, .9, 2400) * np.hanning(2400)
            x = np.clip(x, -.99, .99); wav = Path(t) / 'in.wav'
            with wave.open(str(wav), 'wb') as w:
                w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); w.writeframes((np.repeat(x[:, None], 2, axis=1) * 32767).astype('<i2').tobytes())
            src = Path(t) / 'in.mp4'
            r = subprocess.run([ff, '-y', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=160x90:d=10:r=10', '-i', str(wav), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '256k', '-shortest', str(src)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = Path(t) / 'out.mp4'; li, tp, used = finalize.normalise_to_limit(ff, src, out, -16.0, t)
            self.assertLessEqual(tp, finalize.MAX_TP, f'true peak {tp} dBTP after AAC (ceiling used {used})')
            self.assertLess(abs(li + 16.0), 2.0)


class ThreeLayerTest(unittest.TestCase):
    def test_three_layer_renders_deterministically_through_the_shader_post(self):
        import asyncio, functools, hashlib, http.server, shutil, socketserver, threading
        from playwright.async_api import async_playwright
        fx = SK / 'assets' / 'fx'
        if not (fx / 'vendor' / 'three.module.min.js').exists(): self.skipTest('three.module.min.js not bundled')
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            for f in ('fx.js', 'lib.js', 'three-layer.js'): shutil.copy(fx / f, d / f)
            shutil.copy(SK / 'assets' / 'template' / 'avs-runtime.js', d / 'avs-runtime.js'); (d / 'vendor').mkdir(); shutil.copy(fx / 'vendor' / 'three.module.min.js', d / 'vendor' / 'three.module.min.js')
            shutil.copy(fx / 'examples' / 'three-demo-index.html', d / 'index.html'); shutil.copy(fx / 'examples' / 'three-demo-scenes.js', d / 'scenes.js'); (d / 'style.css').write_text('body{background:#000}', encoding='utf-8')
            (d / 'timeline.js').write_text('window.TL={"duration":4,"fps":30,"width":1920,"height":1080,"scenes":[{"id":"s01","start":0,"dur":4,"speed":1,"ns":0,"nd":4,"voStart":0,"voDur":0,"transition":"cut"}],"subs":[]};', encoding='utf-8')
            (d / 'project.js').write_text('window.PROJECT={"scenes":[{"id":"s01","type":"x","data":{}}]};', encoding='utf-8'); (d / 'videos.js').write_text('window.VIDEOS={};', encoding='utf-8')
            class Q(http.server.SimpleHTTPRequestHandler):
                def log_message(self, *a): pass
                def handle(self):
                    try: super().handle()
                    except Exception: pass
            httpd = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Q, directory=str(d))); httpd.daemon_threads = True
            port = httpd.server_address[1]; threading.Thread(target=httpd.serve_forever, daemon=True).start()
            async def run():
                out = {}
                async with async_playwright() as p:
                    b = await p.chromium.launch(args=['--force-color-profile=srgb']); pg = await b.new_page(viewport={'width': 1920, 'height': 1080}); errs = []
                    pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
                    await pg.goto(f'http://127.0.0.1:{port}/index.html'); await pg.wait_for_function('window.READY===true||window.AVS_ERROR', timeout=60000)
                    out['avs_error'] = await pg.evaluate('window.AVS_ERROR||null'); await pg.evaluate('window.__ready'); h = []
                    for tt in (.5, .5, 2.0): await pg.evaluate(f'window.render({tt})'); h.append(hashlib.md5(await pg.screenshot(type='png')).hexdigest())
                    out['hashes'] = h; out['errs'] = errs; await b.close()
                return out
            try: r = asyncio.run(run())
            finally: httpd.shutdown()
            self.assertIsNone(r['avs_error']); self.assertEqual(r['errs'], [])
            self.assertEqual(r['hashes'][0], r['hashes'][1], 'same t must give identical pixels'); self.assertNotEqual(r['hashes'][0], r['hashes'][2])


class WorldCameraTest(unittest.TestCase):
    """The one-take camera spline must pass through every key and never overshoot (no stop-start, no rubber-banding)."""
    def test_track_interpolates_keys_and_never_overshoots(self):
        import shutil as _sh
        node = _sh.which('node')
        if not node: self.skipTest('node not installed')
        src = (SK / 'assets' / 'fx' / 'world.js').read_text(encoding='utf-8')
        track = src[src.index('function track(keys, field)'):src.index('const CAM =')]
        js = (SK / 'tests' / 'camera_spline_check.js').read_text(encoding='utf-8').replace('%%TRACK%%', track)
        r = subprocess.run([node, '-e', js], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stderr); self.assertEqual(r.stdout.strip(), 'OK', r.stdout)


class SandboxResilienceTest(unittest.TestCase):
    """Regressions from the macOS run: (1) check_env reported a blocked-but-installed Chromium as MISSING five times in a row;
    (2) render.py crashed with PermissionError when the sandbox refused to bind a loopback port."""
    def _status(self, behaviour, install=False):
        import types, check_env
        launches = []
        class Chromium:
            executable_path = __file__ if behaviour != 'missing' else '/no/such/chrome'
            def launch(self, **k):
                launches.append(1)
                if behaviour == 'blocked': raise Exception('BrowserType.launch: Operation not permitted')
                if behaviour == 'weird': raise Exception('BrowserType.launch: kaboom happened\nsecond line')
                return types.SimpleNamespace(close=lambda: None)
        class P:
            chromium = Chromium()
            def __enter__(self): return self
            def __exit__(self, *a): return False
        fake = types.ModuleType('playwright.sync_api'); fake.sync_playwright = lambda: P()
        sys.modules['playwright.sync_api'] = fake; orig_has = check_env.has; check_env.has = lambda m: True
        try: return check_env.chromium_status(install)
        finally: check_env.has = orig_has; sys.modules.pop('playwright.sync_api', None)

    def test_chromium_status_distinguishes_ok_blocked_missing_and_other_errors(self):
        self.assertEqual(self._status('ok'), (True, 'ok'))
        ok, msg = self._status('blocked'); self.assertTrue(ok); self.assertIn('do not reinstall', msg)
        ok, msg = self._status('missing'); self.assertFalse(ok); self.assertIn('playwright install chromium', msg)
        ok, msg = self._status('weird'); self.assertFalse(ok); self.assertIn('kaboom', msg)

    def test_render_falls_back_to_file_url_when_port_bind_is_denied(self):
        import render, socketserver
        with tempfile.TemporaryDirectory() as t:
            d = Path(t); (d / 'index.html').write_text('<html></html>', encoding='utf-8')
            orig = socketserver.ThreadingTCPServer
            def deny(*a, **k): raise PermissionError(1, 'Operation not permitted')
            socketserver.ThreadingTCPServer = deny
            try: httpd, url = render.start_server(d)
            finally: socketserver.ThreadingTCPServer = orig
            self.assertIsNone(httpd); self.assertTrue(url.startswith('file:///') or url.startswith('file://'), url); self.assertTrue(url.endswith('index.html'))
            httpd2, url2 = render.start_server(d)
            try: self.assertTrue(url2.startswith('http://127.0.0.1:'))
            finally: httpd2.shutdown()

    def test_browser_launch_help_is_actionable(self):
        import render
        self.assertIn('playwright install chromium', render.browser_launch_help(Exception("Executable doesn't exist at /x")))
        self.assertIn('sandbox', render.browser_launch_help(Exception('launch: Operation not permitted')))
        self.assertIn('failed to start', render.browser_launch_help(Exception('something else')).lower())


if __name__ == '__main__': unittest.main()
