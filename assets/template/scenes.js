/* Starter scenes. One AVS.scene per scene id (or per scene "type" for reuse).
   build(o, data): create DOM once.  render(o, lt, dur, t): set state from scene-local time lt (1x seconds). */
const { scene, el, add, set, enter, seg, E, FMT } = AVS;

scene('title', (o, d) => {
  o.t = add(o.root, el('div', 'abs', d.title || '', `left:0;width:${FMT.w}px;top:${FMT.h * .40}px;text-align:center;font-size:${FMT.w * .05}px;font-weight:800`));
  o.s = add(o.root, el('div', 'abs', d.subtitle || '', `left:0;width:${FMT.w}px;top:${FMT.h * .55}px;text-align:center;font-size:${FMT.w * .022}px;color:var(--muted)`));
}, (o, lt) => { enter(o.t, lt, .2, 1.0, { dy: 40 }); enter(o.s, lt, .8, 1.6, { dy: 20 }) });

scene('bullets', (o, d) => {
  o.h = add(o.root, el('div', 'abs', d.heading || '', `left:${FMT.w * .08}px;top:${FMT.h * .14}px;font-size:${FMT.w * .036}px;font-weight:800`));
  o.items = (d.items || []).map((x, i) => add(o.root, el('div', 'abs', x, `left:${FMT.w * .08}px;top:${FMT.h * (.32 + i * .11)}px;font-size:${FMT.w * .022}px`)));
}, (o, lt) => { enter(o.h, lt, .1, .7); o.items.forEach((e, i) => enter(e, lt, .6 + i * .45, 1.1 + i * .45, { dx: -40, dy: 0 })) });
