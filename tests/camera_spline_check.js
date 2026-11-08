// Extracted from assets/fx/world.js by the test: the camera spline must pass through every key and never overshoot.
%%TRACK%%
const keys=[{t:0,x:0},{t:2,x:1000},{t:2.5,x:1010},{t:6,x:3000},{t:9,x:3000},{t:10,x:4000}]; const f=track(keys,'x'); let ok=true, msg='';
for (const k of keys) if (Math.abs(f(k.t)-k.x)>1e-6) { ok=false; msg+='miss@'+k.t+' ' }
let mn=1e9, mx=-1e9; for (let t=0;t<=10;t+=.01){ const v=f(t); mn=Math.min(mn,v); mx=Math.max(mx,v) }
if (mn<-1e-6 || mx>4000+1e-6) { ok=false; msg+='range '+mn+'..'+mx+' ' }
for (let t=6;t<=9;t+=.05) if (Math.abs(f(t)-3000)>1e-6) { ok=false; msg+='hold-moves@'+t+' '; break }
let last=f(0), mono=true; for (let t=.01;t<=10;t+=.01){ const v=f(t); if (v<last-1e-6) mono=false; last=v }
if (!mono) { ok=false; msg+='not monotone ' }
console.log(ok?'OK':'FAIL '+msg);