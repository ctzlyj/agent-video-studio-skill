/* world.js: ONE continuous world drawn entirely in code (no full-screen photos), and ONE camera that travels through it.
   World coordinates: x grows to the right over the whole film; y=0 is the ground line; units are px at zoom 1 (1920x1080 view).
   Every function is a pure function of (t); seeded generators are built once. */
(function () {
  const { rand, E, seg, lerp, clamp } = AVS; const { X, W, H } = L; const tau = Math.PI * 2;
  /* ---------- camera: monotone-cubic (Fritsch-Carlson) interpolation through keys, so no overshoot and no stop-start ---------- */
  function track(keys, field) {
    const n = keys.length, ts = keys.map(k => k.t), vs = keys.map(k => k[field]); const d = [], m = new Array(n).fill(0);
    for (let i = 0; i < n - 1; i++) d[i] = (vs[i + 1] - vs[i]) / (ts[i + 1] - ts[i]);
    m[0] = d[0]; m[n - 1] = d[n - 2]; for (let i = 1; i < n - 1; i++) m[i] = d[i - 1] * d[i] <= 0 ? 0 : (d[i - 1] + d[i]) / 2;
    for (let i = 0; i < n - 1; i++) { if (d[i] === 0) { m[i] = m[i + 1] = 0; continue } const a = m[i] / d[i], b = m[i + 1] / d[i], s = a * a + b * b; if (s > 9) { const k = 3 / Math.sqrt(s); m[i] = k * a * d[i]; m[i + 1] = k * b * d[i] } }
    return t => { if (t <= ts[0]) return vs[0]; if (t >= ts[n - 1]) return vs[n - 1]; let i = 0; while (t > ts[i + 1]) i++; const h = ts[i + 1] - ts[i], u = (t - ts[i]) / h, u2 = u * u, u3 = u2 * u;
      return (2 * u3 - 3 * u2 + 1) * vs[i] + (u3 - 2 * u2 + u) * h * m[i] + (-2 * u3 + 3 * u2) * vs[i + 1] + (u3 - u2) * h * m[i + 1] };
  }
  const CAM = { fx: () => 0, fy: () => 0, fz: () => 1, fr: () => 0 };
  function setCamera(keys) { CAM.fx = track(keys, 'x'); CAM.fy = track(keys, 'y'); CAM.fz = track(keys, 'z'); CAM.fr = track(keys, 'r') }
  const cam = t => ({ x: CAM.fx(t), y: CAM.fy(t), z: CAM.fz(t), r: CAM.fr(t) });
  function camSpeed(t) { const a = cam(t - .04), b = cam(t + .04); return Math.hypot(b.x - a.x, (b.y - a.y) * .5) / .08 }
  /* apply camera to the 2D context: world (wx,wy) -> screen. parallax p: 0 = glued to screen, 1 = world, <1 = far, >1 = near */
  function withCam(t, p, draw) { const c = cam(t); X.save(); X.translate(W / 2, H * .62); const z = lerp(1, c.z, Math.min(1, p) * .9 + .1 * Math.min(1, p)); X.scale(z, z); if (c.r) X.rotate(c.r * p);
    X.translate(-c.x * p, -c.y * p + 0); draw(c, z); X.restore() }
  const toScreen = (t, wx, wy, p = 1) => { const c = cam(t); const z = lerp(1, c.z, Math.min(1, p) * .9 + .1 * Math.min(1, p)); return [W / 2 + (wx - c.x * p) * z, H * .62 + (wy - c.y * p) * z, z] };

  /* ---------- procedural scenery (all seeded, built once) ---------- */
  const R1 = rand(5), R2 = rand(17), R3 = rand(29), R4 = rand(41);
  // far skyline silhouettes, 3 depth layers; each building has window rows that "light up" at a time given by the film's progress
  function buildSkyline(r, n, x0, x1, hmin, hmax, wmin, wmax) { const a = []; let x = x0; while (x < x1) { const w = wmin + r() * (wmax - wmin), h = hmin + r() * (hmax - hmin); a.push({ x, w, h, win: r(), stack: r() < .25, chimney: r() < .12 }); x += w * (.7 + r() * .5) } return a }
  const SKY = [buildSkyline(R1, 0, -600, 16000, 120, 380, 120, 260), buildSkyline(R2, 0, -600, 16000, 90, 260, 90, 200), buildSkyline(R3, 0, -600, 16000, 60, 170, 70, 150)];
  const STARS = Array.from({ length: 160 }, () => ({ x: R4() * 2400, y: R4() * 640, s: .5 + R4() * 1.6, p: R4() * tau }));
  const DUST = Array.from({ length: 90 }, () => ({ x: R4() * 2000, y: R4() * 1100, z: .3 + R4() * .9, p: R4() * tau }));

  /* sky: vertical gradient interpolated between night-cold and dawn-warm by 'warmth' (0..1); returns nothing */
  function sky(t, warmth, horizonY) {
    const cold0 = [10, 16, 34], cold1 = [30, 48, 78], warm0 = [34, 28, 62], warm1 = [255, 176, 92];
    const mix = (a, b, k) => a.map((v, i) => Math.round(lerp(v, b[i], k))); const top = mix(cold0, warm0, warmth), bot = mix(cold1, warm1, warmth * warmth);
    const g = X.createLinearGradient(0, 0, 0, horizonY); g.addColorStop(0, `rgb(${top})`); g.addColorStop(1, `rgb(${bot})`); X.fillStyle = g; X.fillRect(0, 0, W, horizonY + 2);
    // stars fade as it gets warm
    X.save(); X.globalCompositeOperation = 'lighter'; for (const s of STARS) { const a = (1 - warmth) * (.4 + .6 * Math.sin(t * 1.3 + s.p) ** 2) * .8; if (a < .02) continue; X.fillStyle = `rgba(210,225,255,${a})`; X.fillRect((s.x % W), s.y % (horizonY - 30), s.s, s.s) } X.restore();
    if (warmth > .05) { const sg = X.createRadialGradient(W * .78, horizonY, 0, W * .78, horizonY, W * .9); sg.addColorStop(0, `rgba(255,214,140,${.9 * warmth})`); sg.addColorStop(.25, `rgba(255,160,80,${.45 * warmth})`); sg.addColorStop(1, 'rgba(255,120,60,0)'); X.fillStyle = sg; X.fillRect(0, 0, W, horizonY + 2) }
  }
  /* skyline layer in world space. 'lit' returns 0..1 window brightness for a building at world x. */
  function drawSkyline(t, layer, p, base, tint, lit) {
    const arr = SKY[layer], c = cam(t); const left = c.x * p - W, right = c.x * p + W * 1.3;
    for (const b of arr) { if (b.x + b.w < left || b.x > right) continue; const wl = lit(b.x, b.win);
      X.fillStyle = tint; X.fillRect(Math.round(b.x), Math.round(base - b.h), Math.round(b.w), Math.round(b.h + 400)); if (b.stack) X.fillRect(b.x + b.w * .7, base - b.h - 90, 16, 90);
      if (wl > .02) { const cols = Math.max(2, Math.floor(b.w / 26)), rows = Math.floor(b.h / 30); X.save(); X.globalCompositeOperation = 'lighter';
        for (let j = 1; j < rows; j++) for (let i = 0; i < cols; i++) { const k = (i * 7 + j * 13 + (b.x | 0)) % 11 / 11; if (k > wl) continue; X.fillStyle = `rgba(255,${190 + (k * 50) | 0},${100 + (k * 60) | 0},${.75 * wl})`; X.fillRect(Math.round(b.x + 8 + i * ((b.w - 16) / cols)), Math.round(base - b.h + j * 30), 11, 15) } X.restore() } }
  }
  function ground(t, warmth, y0) {
    const g = X.createLinearGradient(0, y0, 0, H); const c0 = [8, 12, 22], c1 = [60, 42, 30]; const m = c0.map((v, i) => Math.round(lerp(v, c1[i], warmth)));
    g.addColorStop(0, `rgb(${m})`); g.addColorStop(1, 'rgb(4,6,12)'); X.fillStyle = g; X.fillRect(0, y0, W, H - y0 + 2);
  }
  function dust(t, a, col = '255,236,200') { X.save(); X.globalCompositeOperation = 'lighter'; for (const d of DUST) { const x = ((d.x - t * 14 * d.z) % W + W) % W, y = ((d.y - t * 8 * d.z) % H + H) % H; X.fillStyle = `rgba(${col},${a * d.z * (.5 + .5 * Math.sin(t * 2 + d.p))})`; X.beginPath(); X.arc(x, y, 1.2 + d.z * 1.4, 0, tau); X.fill() } X.restore() }

  /* ---------- the particle pool: ONE set of N lights that morphs between target formations ---------- */
  const N = 3000, PR = rand(777);
  const P = Array.from({ length: N }, (_, i) => ({ i, u: PR(), v: PR(), w: PR(), s: 1.8 + PR() * 3 }));
  const FORM = {};   // name -> function(i, p, t) -> [x, y] in WORLD coords (or screen coords if formation is flagged 'screen')
  function formation(name, fn, o = {}) { FORM[name] = { fn, ...o } }
  function drawParticles(t, stages, o = {}) {
    // stages: [{ form, a, b, c }]  : particles interpolate from form a to form b with progress c (eased by caller)
    const { col = [255, 205, 120], alpha = 1, scale = 1, sx = 0, sy = 0 } = o; X.save(); X.globalCompositeOperation = 'lighter';
    for (const p of P) { const fa = FORM[stages.a], fb = FORM[stages.b || stages.a]; const A = fa.fn(p.i, p, t), B = fb.fn(p.i, p, t); const k = stages.c === undefined ? 0 : clamp(stages.c);
      const kk = clamp((k * 1.4 - p.u * .4)); const e = kk * kk * (3 - 2 * kk); const x = lerp(A[0], B[0], e) + sx, y = lerp(A[1], B[1], e) + sy; const fade = (A[2] === undefined ? 1 : A[2]) * (1 - e) + (B[2] === undefined ? 1 : B[2]) * e; if (fade < .02) continue;
      const tw = .65 + .35 * Math.sin(t * 3.1 + p.w * 40); const hue = p.w; X.fillStyle = `rgba(${col[0]},${(col[1] + 40 * hue) | 0},${(col[2] + 70 * hue) | 0},${alpha * tw * fade})`; const r = p.s * scale * (1 + .5 * Math.sin(e * Math.PI)); X.beginPath(); X.arc(x, y, r, 0, tau); X.fill() }
    X.restore();
  }
  
    /* ---------- object library: small drawn goods with outline, rim light and soft shadow. Every function draws at (0,0) facing up. ---------- */
    function rr(x, y, w, h, r) { X.beginPath(); if (X.roundRect) X.roundRect(x, y, w, h, r); else X.rect(x, y, w, h) }
    const GOODS = {
      bottle(w, h, c) { rr(-w / 2, -h * .8, w, h * .8, w * .22); X.fill(); rr(-w * .22, -h, w * .44, h * .22, 3); X.fill(); X.save(); X.globalCompositeOperation = 'source-atop'; X.restore() },
      box(w, h, c) { rr(-w / 2, -h, w, h, 4); X.fill() },
      cup(w, h, c) { X.beginPath(); X.moveTo(-w / 2, -h); X.lineTo(w / 2, -h); X.lineTo(w * .36, 0); X.lineTo(-w * .36, 0); X.closePath(); X.fill() },
      bag(w, h, c) { X.beginPath(); X.moveTo(-w / 2, 0); X.quadraticCurveTo(-w * .62, -h * .55, -w * .4, -h * .9); X.lineTo(w * .4, -h * .9); X.quadraticCurveTo(w * .62, -h * .55, w / 2, 0); X.closePath(); X.fill(); X.fillRect(-w * .32, -h, w * .64, h * .12) },
      bowl(w, h, c) { X.beginPath(); X.moveTo(-w / 2, -h * .75); X.quadraticCurveTo(-w * .46, 0, 0, 0); X.quadraticCurveTo(w * .46, 0, w / 2, -h * .75); X.closePath(); X.fill() },
    };
    /* draw one good: base colour, a lighter rim on the lit side, a dark underside, and a soft contact shadow. lit: 0..1 how strongly the key light hits it. */
    function good(kind, x, y, w, h, col, lit, a = 1, flip = 1) {
      X.save(); X.translate(x, y); X.scale(flip, 1); X.globalAlpha = a * .35; X.fillStyle = '#000'; X.beginPath(); X.ellipse(0, 3, w * .62, 7, 0, 0, tau); X.fill(); X.globalAlpha = a;
      X.fillStyle = col; GOODS[kind](w, h, col);
      X.globalCompositeOperation = 'source-atop'; const g = X.createLinearGradient(-w / 2, 0, w / 2, 0); g.addColorStop(0, `rgba(255,255,255,${.28 * lit})`); g.addColorStop(.45, 'rgba(255,255,255,0)'); g.addColorStop(1, 'rgba(0,0,0,.38)'); X.fillStyle = g; X.fillRect(-w, -h * 1.2, w * 2, h * 1.3);
      X.restore();
    }
    /* mirror-floor: draw the world once more, flipped, faded, over the ground (cheap planar reflection). 'fn' draws the world; call between save/restore. */
    function reflect(t, groundY, alpha, fn) { X.save(); X.translate(0, groundY * 2); X.scale(1, -1); X.globalAlpha = alpha; fn(); X.restore();
      const g = X.createLinearGradient(0, groundY, 0, groundY + 260); g.addColorStop(0, 'rgba(5,8,16,0)'); g.addColorStop(1, 'rgba(5,8,16,.92)'); X.save(); X.fillStyle = g; X.fillRect(-4000, groundY, 20000, 320); X.restore() }
  
  window.WORLD = { good, reflect, GOODS, rr, track, setCamera, cam, camSpeed, withCam, toScreen, sky, drawSkyline, ground, dust, SKY, P, N, FORM, formation, drawParticles, tau };
})();