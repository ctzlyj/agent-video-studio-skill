/* AVS runtime: deterministic, frame-accurate HTML video engine. Style-free by design:
   every project writes its own styles (style.css) and scenes (scenes.js).
   Contract: the page is a pure function of time. window.render(t) draws output second t. */
(function () {
  const TL = window.TL, P = window.PROJECT || {}, FMT = { w: TL.width, h: TL.height };
  const stage = document.getElementById('stage'), subEl = document.getElementById('sub');
  const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  const lerp = (a, b, t) => a + (b - a) * t;
  const seg = (t, a, b) => clamp((t - a) / (b - a));
  const E = {
    linear: t => clamp(t), smooth: t => { t = clamp(t); return t * t * (3 - 2 * t) },
    out: t => 1 - Math.pow(1 - clamp(t), 3), in: t => Math.pow(clamp(t), 3),
    inOut: t => { t = clamp(t); return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2 },
    back: t => { t = clamp(t); const c = 1.70158; return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2) },
    spring: t => { t = clamp(t); return 1 - Math.cos(t * Math.PI * 4.5) * Math.exp(-t * 6) }
  };
  /* hold(t, rate): quantise time to ate steps per second (animate on twos: hold(t, 12) at 24-30fps gives stepped, hand-made motion) */
  const hold = (t, rate = 12) => Math.floor(t * rate + 1e-6) / rate;
  const el = (tag, cls = '', html = '', style = '') => { const e = document.createElement(tag); if (cls) e.className = cls; if (html) e.innerHTML = html; if (style) e.style.cssText = style; return e };
  const add = (parent, e) => (parent.appendChild(e), e);
  function set(e, o = {}) {
    if (!e) return; const s = e.style;
    if (o.op !== undefined) s.opacity = o.op;
    let tr = '';
    if (o.x || o.y) tr += `translate(${o.x || 0}px,${o.y || 0}px) `;
    if (o.s !== undefined) tr += `scale(${o.s}) `;
    if (o.r) tr += `rotate(${o.r}deg) `;
    if (tr || o.reset) s.transform = tr;
    if (o.blur !== undefined) s.filter = `blur(${o.blur}px)`;
    if (o.clip !== undefined) s.clipPath = o.clip;
  }
  /* animate entrance: progress k in [0,1] from local time window */
  const enter = (e, lt, a, b, { dx = 0, dy = 30, s0 = 1, ease = 'out', blur = 0 } = {}) => {
    const k = E[ease](seg(lt, a, b)); set(e, { op: k, x: dx * (1 - k), y: dy * (1 - k), s: lerp(s0, 1, k), blur: blur ? blur * (1 - k) : undefined }); return k;
  };
  const count = (from, to, k, dec = 0) => (from + (to - from) * clamp(k)).toFixed(dec).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  const typeText = (text, k) => text.slice(0, Math.floor(clamp(k) * [...text].length));
  /* seeded PRNG: same seed -> same numbers on every frame */
  const rand = seed => { let s = (seed >>> 0) || 1; return () => (s = (s * 16807) % 2147483647) / 2147483647 };

  /* video: pre-extracted frames (scripts/prep_video.py) drawn on a canvas -> deterministic */
  const VID = {}; const videoMeta = window.VIDEOS || {};
  function video(parent, name, x, y, w, h, style = '') {
    const m = videoMeta[name]; if (!m) throw new Error('unknown video ' + name + ' (run prep_video.py)');
    const c = add(parent, el('canvas', 'avs-video', '', `position:absolute;left:${x}px;top:${y}px;width:${w}px;height:${h}px;${style}`));
    c.width = m.w; c.height = m.h; c._v = name; return c;
  }
  function drawVideo(c, vt, { loop = false } = {}) {
    const m = videoMeta[c._v], frames = VID[c._v]; let i = Math.floor(vt * m.fps);
    i = loop ? ((i % m.count) + m.count) % m.count : clamp(i, 0, m.count - 1);
    const f = frames[i]; if (f && f.complete && f.naturalWidth > 0) c.getContext('2d').drawImage(f, 0, 0, m.w, m.h);
  }

  const SCENES = {}, ORDER = [];
  function scene(id, build, render) { SCENES[id] = { id, build, render }; ORDER.push(id) }

  function fade(o, lt, dur, tr) {
    const a = tr === 'cut' ? 1 : Math.min(E.smooth(lt / .5), E.smooth((dur - lt) / .5));
    o.root.style.opacity = a; o.root.style.visibility = a > .001 ? 'visible' : 'hidden';
  }
  const LIVE = {};
  function mount() {
    for (const s of TL.scenes) {
      const def = SCENES[s.id] || SCENES[(P.scenes || []).find(x => x.id === s.id)?.type];
      if (!def) throw new Error('no scene renderer for ' + s.id + ' (define AVS.scene("' + s.id + '", ...))');
      const root = add(stage, el('div', 'avs-scene')); root.dataset.id = s.id;
      const data = ((P.scenes || []).find(x => x.id === s.id) || {}).data || {};
      const o = { root, data, id: s.id }; def.build(o, data); LIVE[s.id] = { o, def, tl: s };
    }
  }
  window.render = t => {
    for (const id in LIVE) {
      const { o, def, tl } = LIVE[id]; const lt = (t - tl.ns) * tl.speed;
      if (lt < -0.6 || lt > tl.dur + 0.6) { o.root.style.visibility = 'hidden'; o.root.style.opacity = 0; continue }
      fade(o, lt, tl.dur, tl.transition); def.render(o, lt, tl.dur, t);
    }
    const s = TL.subs.find(x => t >= x.s && t <= x.e);
    if (subEl) { subEl.textContent = s ? s.text : ''; subEl.style.opacity = s ? Math.min(E.smooth((t - s.s) / .12), E.smooth((s.e - t) / .12)) : 0 }
  };
  window.DUR = TL.duration;

  async function preload() {
    const imgs = [...document.images].map(i => i.complete ? i.decode().catch(() => 0) : new Promise(r => { i.onload = i.onerror = r }));
    const vids = Object.entries(videoMeta).map(([name, m]) => {
      VID[name] = [];
      return Promise.all(Array.from({ length: m.count }, (_, k) => new Promise(r => {
        const im = new Image(); let tries = 0; const src = m.dir + '/f_' + String(k + 1).padStart(5, '0') + '.jpg';
        im.onload = () => im.decode().then(r, r); im.onerror = () => tries++ < 4 ? setTimeout(() => im.src = src + '?r=' + tries, 200) : r();
        im.src = src; VID[name][k] = im;
      })));
    });
    await Promise.all([...imgs, ...vids]); await document.fonts.ready;
  }
  window.AVS = { hold, scene, el, add, set, enter, seg, lerp, clamp, E, count, typeText, rand, video, drawVideo, FMT, P, TL };
  window.addEventListener('load', async () => {
    try { mount(); await preload(); window.render(0); window.READY = true } catch (e) { window.AVS_ERROR = String(e && e.stack || e); console.error(e) }
  });
})();
