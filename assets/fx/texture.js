/* texture.js: paper / grain / dust / washi-tape overlays for DOM scenes. Deterministic: every offset is a pure function of t.
   Needs assets/textures/ in the project (new_project.py --textures). Load after avs-runtime.js:
     <script src="assets/textures/../texture.js"></script>   (copy this file next to index.html)

   const T = TEX;                                  // window.TEX
   T.paper(root, {tone:'#f4e9d0', k:.9})           // paper ground (multiply over a tint); call in build()
   T.grain(root, {kind:'fine'|'film35', op:.12, rate:12})   // film/tooth grain, re-seated `rate` times per second (boil), call in build()
   T.dust(root, {op:.5, rate:8, ink:'#1c1613'})   // specks and scratches, a different plate every 1/rate s
   T.tape(root, {x, y, w, rot, kind:12|14, tint})  // washi tape strip (returns the element; animate it yourself)
   T.step(t)                                       // call once per frame from your scene render(): moves every overlay
   The step time is quantised (`rate`), so the grain "boils" like hand-made animation instead of crawling every frame. */
(function () {
  const base = 'assets/textures/';
  // Preload every plate: dust/washi images are switched in during render(), so they must already be decoded before
  // the runtime sets window.READY, otherwise a frame can be captured before the new background paints.
  const ASSETS = ['paper_2048.jpg', 'grain_fine_2048.jpg', 'grain_film35_2048.jpg',
    'dust_01_1920.png', 'dust_02_1920.png', 'dust_03_1920.png', 'dust_04_1920.png',
    'washi_solid_12.png', 'washi_solid_14.png'];
  for (const f of ASSETS) { const im = new Image(); im.src = base + f; im.style.display = 'none'; document.body.appendChild(im); }
  const hash = (n) => { let h = (n | 0) * 374761393 + 668265263; h = (h ^ (h >>> 13)) * 1274126177; return ((h ^ (h >>> 16)) >>> 0) / 4294967296 };
  const LIVE = [];
  const mk = (parent, css) => { const e = document.createElement('div'); e.style.cssText = 'position:absolute;inset:0;pointer-events:none;' + css; parent.appendChild(e); return e };
  function paper(root, { tone = '#f4e9d0', k = 0.9, z = 0 } = {}) {
    const e = mk(root, `z-index:${z};background:${tone}`); const t = mk(root, `z-index:${z};background:url(${base}paper_2048.jpg) center/cover;mix-blend-mode:multiply;opacity:${k}`); return t;
  }
  function grain(root, { kind = 'fine', op = 0.12, rate = 12, z = 90, mode = 'multiply' } = {}) {
    const file = kind === 'film35' ? 'grain_film35_2048.jpg' : 'grain_fine_2048.jpg';
    const e = mk(root, `z-index:${z};background:url(${base}${file}) 0 0/1024px 1024px;mix-blend-mode:${mode};opacity:${op}`); LIVE.push({ e, rate, kind: 'grain', seed: LIVE.length + 1 }); return e;
  }
  function dust(root, { op = 0.5, rate = 8, ink = null, z = 91 } = {}) {
    const e = mk(root, `z-index:${z};background:center/cover;opacity:${op}`); if (ink) e.style.cssText += `;filter:brightness(0.2)`; LIVE.push({ e, rate, kind: 'dust', seed: LIVE.length + 1 }); return e;
  }
  function tape(root, { x = 0, y = 0, w = 420, rot = 0, kind = 12, tint = null, z = 20 } = {}) {
    const e = document.createElement('div'); const h = Math.round(w * 300 / 1600);
    e.style.cssText = `position:absolute;left:${x}px;top:${y}px;width:${w}px;height:${h}px;transform:rotate(${rot}deg);z-index:${z};pointer-events:none;background:url(${base}washi_solid_${kind}.png) center/100% 100%;opacity:.92`;
    if (tint) e.style.cssText += `;background-blend-mode:multiply;background-color:${tint}`; root.appendChild(e); return e;
  }
  function step(t) {
    for (const L of LIVE) {
      const i = Math.floor(t * L.rate + 1e-6);
      if (L.kind === 'grain') L.e.style.backgroundPosition = `${-Math.floor(hash(i * 3 + L.seed) * 1024)}px ${-Math.floor(hash(i * 7 + L.seed) * 1024)}px`;
      else { const k = 1 + (Math.floor(hash(i + L.seed * 31) * 4) % 4); L.e.style.backgroundImage = `url(${base}dust_0${k}_1920.png)`; L.e.style.transform = hash(i * 5 + L.seed) > .5 ? 'scaleX(-1)' : 'none' }
    }
  }
  window.TEX = { paper, grain, dust, tape, step };
})();