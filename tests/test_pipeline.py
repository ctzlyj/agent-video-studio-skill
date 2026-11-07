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

if __name__ == '__main__': unittest.main()
