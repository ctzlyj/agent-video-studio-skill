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
        with self.assertRaises(ValueError): bgm.resolve({}, 'ai-comic-drama')
        self.assertEqual(bgm.resolve({}, 'hybrid'), 'track')
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

class MotionBlurAndWorkersTest(unittest.TestCase):
    """Sub-frame motion blur and multi-browser rendering (render.py)."""
    def test_sample_times_single_sample_is_the_frame_time(self):
        import render
        self.assertEqual(render.sample_times(30, 30, 1, 0.5, 10.0), [1.0])

    def test_sample_times_are_centred_on_the_frame_and_stay_inside_the_film(self):
        import render
        ts = render.sample_times(30, 30, 4, 0.5, 10.0)
        self.assertEqual(len(ts), 4); self.assertEqual(ts, sorted(ts))
        self.assertAlmostEqual(sum(ts) / 4, 1.0, 6)                       # symmetric around the frame time
        self.assertAlmostEqual(ts[-1] - ts[0], 0.5 * (3 / 4) / 30, 6)     # spans shutter * (n-1)/n of one frame
        first = render.sample_times(0, 30, 4, 1.0, 10.0); self.assertTrue(all(t >= 0 for t in first))
        last = render.sample_times(299, 30, 4, 1.0, 10.0); self.assertTrue(all(t < 10.0 for t in last))

    def test_plan_chunks_cover_every_frame_exactly_once(self):
        import render
        for n, w in ((10, 3), (7, 7), (5, 9), (1, 4), (100, 1)):
            ch = render.plan_chunks(n, w)
            self.assertEqual(ch[0][0], 0); self.assertEqual(ch[-1][1], n)
            self.assertTrue(all(a < b for a, b in ch)); self.assertTrue(all(ch[i][1] == ch[i + 1][0] for i in range(len(ch) - 1)))
            self.assertLessEqual(len(ch), min(w, n))

    def test_hold_runtime_helper_quantises_time(self):
        rt = (SK / 'assets' / 'template' / 'avs-runtime.js').read_text(encoding='utf-8')
        self.assertIn('hold', rt)

    def _tiny_project(self, root, **fmt):
        d = Path(root) / 'p'; subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'new_project.py'), str(d), '--title', 'tiny'], check=True, capture_output=True)
        p = json.loads((d / 'project.json').read_text(encoding='utf-8'))
        p['format'].update({'width': 640, 'height': 360, 'fps': 10, **fmt}); p['voice']['engine'] = 'none'; p['music'] = {'generate': 'none'}
        for sc in p['scenes']: sc.pop('vo', None); sc['pad'] = 0.6
        (d / 'project.json').write_text(json.dumps(p, ensure_ascii=False), encoding='utf-8')
        subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'timeline.py'), str(d)], check=True, capture_output=True)
        return d

    def _frames(self, mp4):
        from avs_common import ffmpeg
        r = subprocess.run([ffmpeg(), '-hide_banner', '-i', str(mp4), '-map', '0:v:0', '-f', 'null', '-'], capture_output=True, text=True, encoding='utf-8', errors='ignore')
        import re
        self.assertNotIn('error', r.stderr.lower().replace('error resilience', ''))
        return int(re.findall(r'frame=\s*(\d+)', r.stderr)[-1])

    def test_final_render_frame_count_is_exact_with_blur_and_workers(self):
        with tempfile.TemporaryDirectory() as t:
            d = self._tiny_project(t); tl = json.loads((d / 'timeline.json').read_text(encoding='utf-8')); n = round(tl['duration'] * tl['fps'])
            counts = {}
            for tag, extra in (('plain', []), ('blur', ['--mb', '3']), ('par', ['--workers', '2']), ('both', ['--workers', '3', '--mb', '2'])):
                r = subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'render.py'), str(d), '--final', *extra], capture_output=True, text=True, encoding='utf-8', errors='ignore')
                self.assertEqual(r.returncode, 0, tag + '\n' + r.stdout[-800:] + r.stderr[-800:])
                counts[tag] = self._frames(d / 'out' / 'tiny.mp4')
            self.assertEqual(set(counts.values()), {n}, counts)
            self.assertEqual([p.name for p in (d / 'out').glob('_*')], [], 'temporary segment files must be cleaned up')

    def test_final_video_is_tagged_bt709_and_brand_colours_survive_a_709_player(self):
        """Chrome frames are sRGB; HD players decode untagged/601 files with the 709 matrix, which shifts saturated brand colours
        (measured: mint #2EE6A8 off by 23/255). The encoder must convert with the 709 matrix AND tag it."""
        import numpy as np
        from PIL import Image
        from avs_common import ffmpeg
        with tempfile.TemporaryDirectory() as t:
            d = self._tiny_project(t)
            pj = json.loads((d / 'project.json').read_text(encoding='utf-8'))
            for sc in pj['scenes']: sc['transition'] = 'cut'          # frame 0 must not be a fade-in from black
            (d / 'project.json').write_text(json.dumps(pj, ensure_ascii=False), encoding='utf-8')
            subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'timeline.py'), str(d)], check=True, capture_output=True)
            (d / 'scenes.js').write_text("for (const k of ['title','bullets']) AVS.scene(k, (o)=>{ o.root.style.background='linear-gradient(90deg,#e5402b 0 25%,#ffc425 25% 50%,#2b2bff 50% 75%,#2ee6a8 75%)' }, ()=>{})", encoding='utf-8')
            for extra in ([], ['--mb', '2']):
                r = subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'render.py'), str(d), '--final', *extra], capture_output=True, text=True, encoding='utf-8', errors='ignore')
                self.assertEqual(r.returncode, 0, r.stdout[-500:] + r.stderr[-500:])
                mp4 = d / 'out' / 'tiny.mp4'
                info = subprocess.run([ffmpeg(), '-hide_banner', '-i', str(mp4)], capture_output=True, text=True, encoding='utf-8', errors='ignore').stderr
                self.assertIn('bt709', info.split('Video:')[1].split('\n')[0])
                png = d / 'dec.png'
                subprocess.run([ffmpeg(), '-y', '-loglevel', 'error', '-i', str(mp4), '-vf', 'scale=in_color_matrix=bt709:in_range=tv:out_range=pc,format=rgb24', '-vframes', '1', str(png)], check=True)
                im = np.asarray(Image.open(png).convert('RGB'), int)
                for x, want in ((80, (0xe5, 0x40, 0x2b)), (240, (0xff, 0xc4, 0x25)), (400, (0x2b, 0x2b, 0xff)), (560, (0x2e, 0xe6, 0xa8))):
                    err = max(abs(int(a) - b) for a, b in zip(im[180, x], want))
                    self.assertLessEqual(err, 6, f'colour at x={x} off by {err} (mb={extra})')

class RenderSettingsLintTest(unittest.TestCase):
    def _issues(self, render):
        import lint
        with tempfile.TemporaryDirectory() as t:
            d = proj(t, render=render); return lint.check(json.loads((d / 'project.json').read_text(encoding='utf-8')), d)

    def test_valid_render_block_is_clean(self):
        self.assertEqual([i for i in self._issues({'motionBlur': {'samples': 4, 'shutter': 0.5}, 'workers': 3}) if i['kind'] == 'render'], [])

    def test_out_of_range_values_are_errors(self):
        for bad in ({'workers': 0}, {'workers': 64}, {'motionBlur': {'samples': 0}}, {'motionBlur': {'samples': 99}}, {'motionBlur': {'shutter': 1.5}}, {'workers': 'many'}):
            self.assertTrue([i for i in self._issues(bad) if i['kind'] == 'render' and i['level'] == 'error'], bad)

    def test_render_settings_precedence_cli_over_project(self):
        import render, types
        a = types.SimpleNamespace(mb=None, shutter=None, workers=None)
        self.assertEqual(render.render_settings(a, {}), (1, 0.5, 1))
        self.assertEqual(render.render_settings(a, {'render': {'motionBlur': {'samples': 4, 'shutter': .25}, 'workers': 2}}), (4, .25, 2))
        b = types.SimpleNamespace(mb=2, shutter=None, workers=5)
        self.assertEqual(render.render_settings(b, {'render': {'motionBlur': {'samples': 4}, 'workers': 2}}), (2, .5, 5))


class TexturesAndReviewTest(unittest.TestCase):
    def test_new_project_textures_flag_copies_the_pack_into_the_project(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / 'p'
            r = subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'new_project.py'), str(d), '--textures'], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(r.returncode, 0, r.stderr)
            tex = d / 'assets' / 'textures'
            self.assertTrue((tex / 'paper_2048.jpg').exists()); self.assertTrue(any(tex.glob('dust_*.png'))); self.assertTrue((tex / 'CREDITS.md').exists())
            d2 = Path(t) / 'q'; subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'new_project.py'), str(d2)], check=True, capture_output=True)
            self.assertFalse((d2 / 'assets' / 'textures').exists(), 'textures are opt-in')

    def test_texture_pack_has_credits_for_every_file(self):
        tex = SK / 'assets' / 'textures'; credits = (tex / 'CREDITS.md').read_text(encoding='utf-8')
        for f in tex.iterdir():
            if f.suffix.lower() in ('.png', '.jpg'): self.assertIn(f.name.split('_')[0], credits, f.name)
        self.assertTrue((tex / 'LICENSE-mg-styles-15.txt').exists())

    def test_review_pack_writes_sheet_strips_and_spec(self):
        from avs_common import ffmpeg
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / 'p'; subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'new_project.py'), str(d), '--title', 'rv'], check=True, capture_output=True)
            mp4 = d / 'out' / 'rv.mp4'
            subprocess.run([ffmpeg(), '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc=size=320x180:rate=10:duration=4', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=4', '-shortest', '-pix_fmt', 'yuv420p', str(mp4)], check=True)
            r = subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'review_pack.py'), str(d), '--file', str(mp4), '--moves', '1.0,2.5'], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            rv = d / 'qa' / 'review'
            self.assertTrue((rv / 'sheet_0.5s.jpg').exists()); self.assertEqual(len(list(rv.glob('strip_*.jpg'))), 2); self.assertTrue(list(rv.glob('frame_*.png')))
            spec = json.loads((rv / 'spec.json').read_text(encoding='utf-8'))
            self.assertAlmostEqual(spec['duration'], 4.0, delta=0.2); self.assertEqual((spec['width'], spec['height']), (320, 180)); self.assertTrue(spec['has_audio'])


class TextureOverlayTest(unittest.TestCase):
    def test_texture_overlays_are_deterministic_and_boil_between_steps(self):
        import hashlib
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / 'p'; subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'new_project.py'), str(d), '--title', 'tex', '--textures'], check=True, capture_output=True)
            (d / 'texture.js').write_text((SK / 'assets' / 'fx' / 'texture.js').read_text(encoding='utf-8'), encoding='utf-8')
            (d / 'index.html').write_text((d / 'index.html').read_text(encoding='utf-8').replace('<script src="scenes.js">', '<script src="texture.js"></script><script src="scenes.js">'), encoding='utf-8')
            p = json.loads((d / 'project.json').read_text(encoding='utf-8')); p['format'].update({'width': 480, 'height': 270, 'fps': 12}); p['voice']['engine'] = 'none'; p['music'] = {'generate': 'none'}
            p['scenes'] = [{'id': 's01', 'type': 'x', 'dur': 2, 'pad': 0.0, 'speed': 1.0, 'transition': 'cut', 'data': {}}]
            (d / 'project.json').write_text(json.dumps(p), encoding='utf-8')
            (d / 'scenes.js').write_text("AVS.scene('x', (o)=>{ TEX.paper(o.root); TEX.tape(o.root,{x:200,y:40,w:160,rot:-8}); TEX.dust(o.root,{op:.7}); TEX.grain(o.root,{kind:'film35',op:.3}) }, (o,lt)=>{ TEX.step(lt) })", encoding='utf-8')
            subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'timeline.py'), str(d)], check=True, capture_output=True)
            def shot(ts):
                r = subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'render.py'), str(d), '--stills', ts], capture_output=True, text=True, encoding='utf-8'); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                return [hashlib.md5(f.read_bytes()).hexdigest() for f in sorted((d / 'qa').glob('still_*.png'), key=lambda f: float(f.stem.split('_')[1]))]
            a = shot('0.5'); b = shot('0.5')
            self.assertEqual(a, b, 'same t must give identical pixels')
            c = shot('0.5,1.2'); self.assertNotEqual(c[0], c[1], 'grain / dust must move between steps')
            e = shot('0.5,0.54'); self.assertEqual(e[0], e[1], 'inside one step (rate 12/s) nothing may change')



class DramaMusicPolicyTest(unittest.TestCase):
    def _new(self, root, route, *extra):
        d = Path(root) / f'{route}_{len(list(Path(root).glob(route + "*")))}'
        r = subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'new_project.py'), str(d), '--title', 't', '--route', route, *extra], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stderr)
        return d, json.loads((d / 'project.json').read_text(encoding='utf-8'))

    def test_new_project_music_by_route(self):
        with tempfile.TemporaryDirectory() as t:
            for route in ('ai-comic-drama', 'ai-live-drama'):
                _, p = self._new(t, route); self.assertEqual(p['music'], {}, route)
                self.assertEqual(p['voice']['voice'], 'zh-CN-XiaoxiaoNeural'); self.assertEqual(p['voice']['rate'], '+12%')
            for route in ('promo', 'explainer', 'motion-graphics', 'hybrid'):
                _, p = self._new(t, route); self.assertEqual(p['music'], {'track': 'default'}, route)
            _, p = self._new(t, 'ai-comic-drama', '--music-style', 'comedy'); self.assertEqual(p['music'], {'style': 'comedy'})

    def test_bgm_resolve_rejects_empty_and_builtin_for_drama(self):
        import bgm
        for m in ({}, {'track': 'default'}):
            with self.assertRaises(ValueError): bgm.resolve(m, 'ai-comic-drama')
        self.assertEqual(bgm.resolve({'track': 'default', 'allowBuiltinTrack': True}, 'ai-comic-drama'), 'track')
        self.assertEqual(bgm.resolve({'file': 'assets/x.mp3'}, 'ai-comic-drama'), 'file')
        self.assertEqual(bgm.resolve({'style': 'workplace'}, 'ai-comic-drama'), 'style')
        self.assertEqual(bgm.resolve({'track': 'default'}, 'promo'), 'track')

    def test_lint_rejects_empty_or_builtin_drama_music(self):
        import lint
        with tempfile.TemporaryDirectory() as t:
            p = proj(t, route='ai-comic-drama', music={})
            issues = lint.check(json.loads((p / 'project.json').read_text(encoding='utf-8')), p)
            self.assertTrue(any(i['kind'] == 'drama_music' and i['level'] == 'warn' for i in issues))
        with tempfile.TemporaryDirectory() as t:
            p = proj(t, route='ai-comic-drama', music={'track': 'default'})
            issues = lint.check(json.loads((p / 'project.json').read_text(encoding='utf-8')), p)
            self.assertTrue(any(i['kind'] == 'drama_bgm' and i['level'] == 'error' for i in issues))
        with tempfile.TemporaryDirectory() as t:
            p = proj(t, route='ai-comic-drama', music={'track': 'default', 'allowBuiltinTrack': True})
            issues = lint.check(json.loads((p / 'project.json').read_text(encoding='utf-8')), p)
            self.assertTrue(any(i['kind'] == 'drama_bgm' and i['level'] == 'warn' for i in issues))

    def test_score_presets_are_atmosphere_only(self):
        import score
        for name in ('workplace', 'healing', 'comedy', 'hotblood'):
            self.assertIn(name, score.STYLES)
        self.assertEqual(score.pick_style('auto', 'ai-comic-drama'), 'workplace')
        self.assertEqual(score.pick_style('auto', 'ai-live-drama'), 'healing')
        self.assertEqual(score.pick_style('auto', 'documentary'), 'cinematic')

    def _audio(self, root, music):
        d = Path(root) / ('p' + str(len(list(Path(root).glob('p*')))))
        subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'new_project.py'), str(d), '--title', 'drama', '--route', 'ai-comic-drama'], check=True, capture_output=True)
        p = json.loads((d / 'project.json').read_text(encoding='utf-8'))
        p['format'].update({'width': 640, 'height': 360, 'fps': 10}); p['voice']['engine'] = 'none'; p['music'] = music
        if music.get('file'):
            import wave, numpy as np
            (d / music['file']).parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(d / music['file']), 'wb') as w:
                w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000); tt = np.arange(48000 * 2) / 48000
                w.writeframes((np.sin(2 * np.pi * 220 * tt) * .1 * 32767).astype('<i2').tobytes())
        for sc in p['scenes']: sc.pop('vo', None); sc['pad'] = 0.2
        (d / 'project.json').write_text(json.dumps(p, ensure_ascii=False), encoding='utf-8')
        subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'timeline.py'), str(d)], check=True, capture_output=True)
        r = subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'audio.py'), str(d)], capture_output=True, text=True, encoding='utf-8')
        return d, r

    def test_audio_rejects_empty_and_builtin_drama_music(self):
        with tempfile.TemporaryDirectory() as t:
            _, r = self._audio(t, {}); self.assertNotEqual(r.returncode, 0); self.assertIn('尚未选定配乐', r.stdout + r.stderr)
        with tempfile.TemporaryDirectory() as t:
            _, r = self._audio(t, {'track': 'default'}); self.assertNotEqual(r.returncode, 0); self.assertIn('内置 BGM', r.stdout + r.stderr)

    def test_audio_allows_explicit_builtin_and_file_music(self):
        import wave, numpy as np
        with tempfile.TemporaryDirectory() as t:
            d, r = self._audio(t, {'track': 'default', 'allowBuiltinTrack': True})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr); self.assertEqual(json.loads((d / 'audio/score_report.json').read_text(encoding='utf-8'))['style'], 'track:default')
        with tempfile.TemporaryDirectory() as t:
            d, r = self._audio(t, {'file': 'assets/music/x.wav', 'volume': .10})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            rep = json.loads((d / 'audio/mix_report.json').read_text(encoding='utf-8'))
            self.assertEqual(rep['source'], 'file'); self.assertEqual(rep['musicVolume'], .1); self.assertEqual(rep['duckRatio'], 8)


class VoicePronunciationTest(unittest.TestCase):
    def test_hints_and_pronounce_replacement(self):
        import voice
        hints = dict(voice.pronunciation_hints('重复的长度，银行还款，行业重庆，还有'))
        for w in ('重复', '长度', '银行', '还款', '行业', '重庆', '还有'): self.assertIn(w, hints)
        self.assertEqual(voice._norm_text('重復、長度、銀行、還是'), '重复长度银行还是')
        self.assertEqual(len(voice.pronunciation_hints('重復活')), 1)
        self.assertEqual(voice._say_text({'voice': {'pronounce': {'重复': '虫复'}}}, '重复'), '虫复')

    def test_voice_check_cli_prints_suggestions(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / 'p'; d.mkdir()
            p = {'title': 'v', 'voice': {'engine': 'none', 'pronounce': {}}, 'scenes': [{'id': 's01', 'vo': '这段重复活要重新做。'}]}
            (d / 'project.json').write_text(json.dumps(p, ensure_ascii=False), encoding='utf-8')
            r = subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'voice.py'), str(d), '--check'], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('建议 重复', r.stdout); self.assertIn('建议 重新', r.stdout)


class SummarySceneTest(unittest.TestCase):
    def test_summary_scene_has_continuous_micro_motion(self):
        import hashlib
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / 'p'; subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'new_project.py'), str(d), '--title', 'summary'], check=True, capture_output=True)
            p = json.loads((d / 'project.json').read_text(encoding='utf-8'))
            p['format'].update({'width': 640, 'height': 360, 'fps': 10}); p['voice']['engine'] = 'none'; p['music'] = {'generate': 'none'}
            p['scenes'] = [{'id': 's01', 'type': 'summary', 'dur': 8, 'pad': 0, 'transition': 'cut', 'data': {'heading': '本集小结', 'items': ['要点一', '要点二', '要点三']}}]
            (d / 'project.json').write_text(json.dumps(p, ensure_ascii=False), encoding='utf-8')
            subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'timeline.py'), str(d)], check=True, capture_output=True)
            r = subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'render.py'), str(d), '--stills', '2,5'], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            files = sorted((d / 'qa').glob('still_*.png'), key=lambda f: float(f.stem.split('_')[1]))
            self.assertEqual(len(files), 2)
            hashes = [hashlib.md5(f.read_bytes()).hexdigest() for f in files]
            self.assertNotEqual(hashes[0], hashes[1], 'summary page must keep moving; otherwise qa freeze check may fail')


class MusicScreenTest(unittest.TestCase):
    def test_music_screen_outputs_metrics_and_checks(self):
        try: import librosa  # noqa: F401
        except ImportError: self.skipTest('librosa not installed')
        import wave, numpy as np
        with tempfile.TemporaryDirectory() as t:
            d = Path(t); wav = d / 'tone.wav'
            with wave.open(str(wav), 'wb') as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050); tt = np.arange(22050 * 3) / 22050
                w.writeframes((np.sin(2 * np.pi * 440 * tt) * .2 * 32767).astype('<i2').tobytes())
            out = d / 'screen.json'
            r = subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'music_screen.py'), str(wav), '--json', str(out)], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            rep = json.loads(out.read_text(encoding='utf-8'))
            for k in ('bpm', 'key', 'mode', 'spectralCentroidHz', 'brightness', 'checks', 'pass'): self.assertIn(k, rep)


class AiDramaPreflightTest(unittest.TestCase):
    def test_skill_and_cli_discovery(self):
        import ai_drama_preflight as pf
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); (root / 'lingjing').mkdir(); (root / 'lingjing' / 'SKILL.md').write_text('x', encoding='utf-8')
            (root / 'lingjing-director').mkdir(); (root / 'lingjing-director' / 'SKILL.md').write_text('x', encoding='utf-8')
            cli = root / 'lingjing.exe'; cli.write_text('x', encoding='utf-8')
            self.assertEqual(pf.find_cli(str(cli)), str(cli))
            self.assertEqual(pf.find_skill('lingjing', [str(root)]), str(root / 'lingjing'))
            self.assertEqual(pf.find_skill('lingjing-director', [str(root)]), str(root / 'lingjing-director'))

    def test_missing_dependencies_stop_with_install_and_no_browser_fallback(self):
        with tempfile.TemporaryDirectory() as t:
            r = subprocess.run([sys.executable, '-X', 'utf8', str(SK / 'scripts' / 'ai_drama_preflight.py'), '--cli', str(Path(t) / 'missing.exe'), '--skill-root', t], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn('NOT READY', r.stdout); self.assertIn('lingjing-cli.zip', r.stdout); self.assertIn('不要把“浏览器自动化点灵境画布”当作兜底', r.stdout)


if __name__ == '__main__': unittest.main()
