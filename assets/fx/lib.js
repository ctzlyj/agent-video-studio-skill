/* lib.js: Canvas2D scene compositor. One shared 2D canvas "C" is drawn each frame from all live scenes,
   then handed to FX (WebGL) for post. Everything is a pure function of (t, lt). */
(function () {
  const { FMT, E, seg, lerp, clamp, rand } = AVS; const W = FMT.w, H = FMT.h;
  const C = document.createElement('canvas'); C.width = W; C.height = H; const X0 = C.getContext('2d'); let X = X0;   // X can be swapped to draw text on a sharp overlay canvas (L.useCtx)
  function useCtx(c) { X = c || X0; if (window.L) window.L.X = X }
  const IMG = {};  // name -> HTMLImageElement
  const load = names => Promise.all(names.map(n => new Promise(r => { const i = new Image(); i.onload = () => i.decode().then(r, r); i.onerror = r; i.src = `assets/gen/${n}.png`; IMG[n] = i })));
  const tau = Math.PI * 2;
  /* cover-fit draw with Ken Burns: z zoom, (px,py) pan in [-1,1] of the slack */
  function plate(name, z = 1.12, px = 0, py = 0, alpha = 1, rot = 0) {
    const im = IMG[name]; if (!im || !im.naturalWidth) return;
    const s = Math.max(W / im.naturalWidth, H / im.naturalHeight) * z; const w = im.naturalWidth * s, h = im.naturalHeight * s;
    X.save(); X.globalAlpha = alpha; X.translate(W / 2, H / 2); if (rot) X.rotate(rot);
    X.drawImage(im, -w / 2 + px * (w - W) / 2, -h / 2 + py * (h - H) / 2, w, h); X.restore();
  }
  function glow(x, y, r, col = '255,200,87', a = 1) {
    const g = X.createRadialGradient(x, y, 0, x, y, r); g.addColorStop(0, `rgba(${col},${a})`); g.addColorStop(.35, `rgba(${col},${a * .35})`); g.addColorStop(1, `rgba(${col},0)`);
    X.save(); X.globalCompositeOperation = 'lighter'; X.fillStyle = g; X.fillRect(x - r, y - r, r * 2, r * 2); X.restore();
  }
  function text(str, x, y, o = {}) {
    const { size = 90, weight = 900, fam = 'var(--serif)', col = '#FFF4DC', a = 1, align = 'center', ls = 0, glow: gl = 0, glowCol = 'rgba(255,200,87,.9)', stroke = 0, sc = 1, rot = 0, blur = 0, skew = 0, local = false } = o;
    X.save(); X.globalAlpha = a; /* default: draw under the CURRENT transform (inside the camera the text lives in the world); screen:true = glued to the screen */
    if (o.screen) X.setTransform(1, 0, 0, 1, 0, 0); X.translate(x, y); if (rot) X.rotate(rot); if (sc !== 1 || skew) X.transform(sc, 0, skew, sc, 0, 0);
    const family = fam.startsWith('var(') ? getComputedStyle(document.body).getPropertyValue(fam.slice(4, -1)) : fam;
    X.font = `${weight} ${size}px ${family}`; X.textAlign = align; X.textBaseline = 'middle'; if ('letterSpacing' in X) X.letterSpacing = ls + 'px';
    if (blur) X.filter = `blur(${blur}px)`;
    if (gl) { X.shadowColor = glowCol; X.shadowBlur = gl; }
    if (stroke) { X.lineWidth = stroke; X.strokeStyle = 'rgba(0,0,0,.6)'; X.strokeText(str, 0, 0); }
    X.fillStyle = col; X.fillText(str, 0, 0); X.restore();
  }
  function measure(str, size, weight = 900, fam = 'var(--serif)', ls = 0) {
    const family = fam.startsWith('var(') ? getComputedStyle(document.body).getPropertyValue(fam.slice(4, -1)) : fam;
    X.save(); X.font = `${weight} ${size}px ${family}`; if ('letterSpacing' in X) X.letterSpacing = ls + 'px'; const w = X.measureText(str).width; X.restore(); return w;
  }
  function line(x1, y1, x2, y2, o = {}) {
    const { w = 4, col = 'rgba(255,200,87,1)', a = 1, glow: gl = 0, cap = 'round', dash = null } = o;
    X.save(); X.globalAlpha = a; X.strokeStyle = col; X.lineWidth = w; X.lineCap = cap; if (dash) X.setLineDash(dash); if (gl) { X.shadowColor = col; X.shadowBlur = gl }
    X.beginPath(); X.moveTo(x1, y1); X.lineTo(x2, y2); X.stroke(); X.restore();
  }
  function rect(x, y, w, h, col, a = 1, r = 0) {
    X.save(); X.globalAlpha = a; X.fillStyle = col; if (r && X.roundRect) { X.beginPath(); X.roundRect(x, y, w, h, r); X.fill() } else X.fillRect(x, y, w, h); X.restore();
  }
  function dim(a, col = '0,0,0') { X.save(); X.fillStyle = `rgba(${col},${a})`; X.fillRect(0, 0, W, H); X.restore(); }
  /* dust / ember particles: precomputed once per seed, drawn as a pure function of t */
  const PS = {};
  function particles(key, n, t, o = {}) {
    const { col = '255,214,130', size = 3, speed = 40, drift = 30, a = .8, rise = true, seed = 11 } = o;
    if (!PS[key]) { const r = rand(seed); PS[key] = Array.from({ length: n }, () => ({ x: r() * W, y: r() * H, z: .3 + r() * .9, ph: r() * tau, s: .4 + r() })); }
    X.save(); X.globalCompositeOperation = 'lighter';
    for (const p of PS[key]) {
      const y = ((p.y + (rise ? -1 : 1) * t * speed * p.z) % H + H) % H; const x = p.x + Math.sin(t * .6 * p.s + p.ph) * drift * p.z;
      const tw = .55 + .45 * Math.sin(t * 2.2 * p.s + p.ph); X.globalAlpha = a * tw * p.z; X.fillStyle = `rgba(${col},1)`;
      X.beginPath(); X.arc(x, y, size * p.z, 0, tau); X.fill();
    }
    X.restore();
  }
  window.L = { C, X, useCtx, W, H, IMG, load, plate, glow, text, measure, line, rect, dim, particles, tau };
})();