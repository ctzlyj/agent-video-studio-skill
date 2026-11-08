/* three-layer.js: a deterministic Three.js 3D layer that composites into the shared 2D canvas (L.C), so it goes through the same
   WebGL post pass (FX.apply: bloom, grade, motion blur, cold|warm edge) as everything else.
   Usage (module script in index.html, BEFORE scenes.js):
     <script type="module">
       import * as THREE from './vendor/three.module.min.js';
       import { makeLayer } from './three-layer.js';
       window.T3 = makeLayer(THREE, { w: 1920, h: 1080 });          // creates renderer + scene + camera
       window.THREE_READY = true;
     </script>
   Then in scenes.js:  T3.build(({ THREE, scene, camera }) => { ...add meshes once... });   // call once, at load
                       T3.frame(t, ({ scene, camera, THREE }) => { ...set transforms from t... }); T3.blit(L.X);
   Rules: no Math.random / Date.now; every transform is a pure function of t; shadow maps and fog are fine; avoid >100k triangles. */
export function makeLayer(THREE, { w = 1920, h = 1080, bg = 0x070b14, fogNear = 10, fogFar = 40, exposure = 1.0 } = {}) {
  const canvas = document.createElement('canvas'); canvas.width = w; canvas.height = h;
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: true, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
  renderer.setSize(w, h, false); renderer.setPixelRatio(1); renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = exposure; renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene(); scene.fog = new THREE.Fog(bg, fogNear, fogFar);
  const camera = new THREE.PerspectiveCamera(40, w / h, .1, 200);
  /* deterministic seeded random for building scenes (Math.random is forbidden) */
  const rand = seed => { let s = (seed >>> 0) || 1; return () => (s = (s * 16807) % 2147483647) / 2147483647 };
  /* helper: a soft key light + ambient fill (warm key, cool fill) */
  const lights = (key = 0xffc878, fill = 0x304060) => { const k = new THREE.SpotLight(key, 400, 60, .6, .5); k.position.set(4, 10, 6); k.castShadow = true; k.shadow.mapSize.set(1024, 1024); k.shadow.bias = -0.0004; scene.add(k); const a = new THREE.AmbientLight(fill, .6); scene.add(a); return { key: k, amb: a } };
  return {
    THREE, canvas, renderer, scene, camera, rand, lights,
    build(fn) { fn({ THREE, scene, camera, rand, lights }) },
    frame(t, fn) { fn && fn({ THREE, scene, camera, t, rand }); renderer.render(scene, camera); return canvas },
    /* draw the 3D frame onto a 2D context (same size), optionally with alpha 0..1 */
    blit(ctx, a = 1) { ctx.save(); ctx.globalAlpha = a; ctx.drawImage(canvas, 0, 0); ctx.restore() },
  };
}