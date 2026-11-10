/* Starter scenes. One AVS.scene per scene id (or per scene "type" for reuse).
   build(o, data): create DOM once.  render(o, lt, dur, t): set state from scene-local time lt (1x seconds). */
const { scene, el, add, set, enter, seg, E, FMT, video, drawVideo } = AVS;

scene('title', (o, d) => {
  o.t = add(o.root, el('div', 'abs', d.title || '', `left:0;width:${FMT.w}px;top:${FMT.h * .40}px;text-align:center;font-size:${FMT.w * .05}px;font-weight:800`));
  o.s = add(o.root, el('div', 'abs', d.subtitle || '', `left:0;width:${FMT.w}px;top:${FMT.h * .55}px;text-align:center;font-size:${FMT.w * .022}px;color:var(--muted,#9a9a9a)`));
}, (o, lt) => { enter(o.t, lt, .2, 1.0, { dy: 40 }); enter(o.s, lt, .8, 1.6, { dy: 20 }) });

scene('bullets', (o, d) => {
  o.h = add(o.root, el('div', 'abs', d.heading || '', `left:${FMT.w * .08}px;top:${FMT.h * .14}px;font-size:${FMT.w * .036}px;font-weight:800`));
  o.items = (d.items || []).map((x, i) => add(o.root, el('div', 'abs', x, `left:${FMT.w * .08}px;top:${FMT.h * (.32 + i * .11)}px;font-size:${FMT.w * .022}px`)));
}, (o, lt) => { enter(o.h, lt, .1, .7); o.items.forEach((e, i) => enter(e, lt, .6 + i * .45, 1.1 + i * .45, { dx: -40, dy: 0 })) });


/* Teaching/training summary page: 3-4 takeaways, with continuous micro-motion so QA does not report a >6s freeze.
   project.json scene: {"type":"summary","data":{"heading":"本集小结","items":["...","...","..."]}} */
scene('summary', (o, d) => {
  o.bg = add(o.root, el('div', 'abs', '', 'inset:0;background:linear-gradient(120deg,#0f172a,#1e293b 55%,#0b1220)'));
  o.h = add(o.root, el('div', 'abs', d.heading || '本集小结', `left:${FMT.w * .08}px;top:${FMT.h * .12}px;font-size:${FMT.w * .036}px;font-weight:800`));
  o.items = (d.items || []).slice(0, 4).map((x, i) => add(o.root, el('div', 'abs', x, `left:${FMT.w * .10}px;top:${FMT.h * (.28 + i * .12)}px;font-size:${FMT.w * .022}px;max-width:${FMT.w * .80}px`)));
  o.bar = add(o.root, el('div', 'abs', '', `left:${FMT.w * .08}px;bottom:${FMT.h * .10}px;width:${FMT.w * .84}px;height:6px;background:var(--accent,#7aa2ff);transform-origin:left;border-radius:3px`));
  o.dot = add(o.root, el('div', 'abs', '', `left:${FMT.w * .08}px;bottom:${FMT.h * .085}px;width:14px;height:14px;border-radius:50%;background:#fff;box-shadow:0 0 18px var(--accent,#7aa2ff)`));
}, (o, lt, dur) => {
  const breath = Math.sin(lt * .9) * 8;
  o.bg.style.background = `linear-gradient(${120 + breath}deg,#0f172a,#1e293b 55%,#0b1220)`;
  o.bar.style.transform = `scaleX(${Math.max(.06, Math.min(.98, seg(lt, .8, Math.max(2.2, dur - 1))))})`;
  o.dot.style.transform = `translateX(${Math.sin(lt * 1.4) * 22}px)`;
  enter(o.h, lt, .1, .7); o.items.forEach((e, i) => enter(e, lt, .5 + i * .3, 1.0 + i * .3, { dx: -30, dy: 0 }));
});

/* End card: title + optional credit. Continuous gradient drift + breathing glow keeps the final hold alive. */
scene('endcard', (o, d) => {
  o.bg = add(o.root, el('div', 'abs', '', 'inset:0;background:linear-gradient(120deg,#111827,#1f2937 55%,#0b1220)'));
  o.t = add(o.root, el('div', 'abs', d.title || '', `left:0;width:${FMT.w}px;top:${FMT.h * .38}px;text-align:center;font-size:${FMT.w * .05}px;font-weight:800`));
  o.s = add(o.root, el('div', 'abs', d.subtitle || '', `left:0;width:${FMT.w}px;top:${FMT.h * .52}px;text-align:center;font-size:${FMT.w * .020}px;color:var(--muted,#9a9a9a)`));
  o.c = add(o.root, el('div', 'abs', d.credit || '', `left:0;width:${FMT.w}px;top:${FMT.h * .84}px;text-align:center;font-size:${FMT.w * .016}px;color:var(--muted,#9a9a9a)`));
}, (o, lt) => {
  const a = Math.sin(lt * .65) * 10;
  o.bg.style.background = `linear-gradient(${125 + a}deg,#111827,#1f2937 55%,#0b1220)`;
  o.t.style.transform = `translateY(${Math.sin(lt * .9) * 3}px)`; o.t.style.filter = `drop-shadow(0 0 ${16 + 8 * Math.sin(lt * 1.1)}px rgba(122,162,255,.35))`;
  enter(o.s, lt, .8, 1.5, { dy: 14 }); enter(o.c, lt, 1.3, 2.0, { dy: 10 });
});

/* Clip scene: if the generated clip is shorter than the narration, play it forward then backward instead of freezing.
   project.json: {"type":"clip","data":{"video":"clip1","clipDur":8.0,"x":0,"y":0,"w":1920,"h":1080}} */
function pingPong(t, dur) {
  const d = Math.max(.05, Number(dur) || .05); const p = ((t % (2 * d)) + 2 * d) % (2 * d);
  return p <= d ? p : 2 * d - p;
}
scene('clip', (o, d) => {
  if (!d.video) return;
  o.clipDur = Number(d.clipDur) || 0;
  o.v = video(o.root, d.video, d.x || 0, d.y || 0, d.w || FMT.w, d.h || FMT.h, d.style || '');
}, (o, lt, dur) => {
  if (!o.v) return;
  drawVideo(o.v, pingPong(lt, o.clipDur || dur));
});
