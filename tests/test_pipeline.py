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

if __name__ == '__main__': unittest.main()
