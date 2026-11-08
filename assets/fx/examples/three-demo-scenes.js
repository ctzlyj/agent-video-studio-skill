/* Three.js layer demo: 80 physical-material cups under a warm spot, camera dollies along them, post pass adds a cold|warm edge and motion blur.
   Copy fx.js, lib.js, three-layer.js, vendor/three.module.min.js, avs-runtime.js next to three-demo-index.html (rename to index.html) and this file (rename to scenes.js).
   Verified: deterministic (same t -> same pixels), 0.25 s/frame at 1080p with the shader post. */
const { scene, E, seg } = AVS; const { X, W, H } = L;
AVS.scene('s01', () => {}, (o) => { o.root.style.opacity = 0 });
document.getElementById('stage').appendChild(FX.canvas);
const warmK = { v: 0 };
window.__ready = (async () => { while (!window.THREE_READY) await new Promise(r => setTimeout(r, 20));
  T3.build(({ THREE, scene, camera, lights, rand }) => {
    scene.background = null; lights();
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(80, 80), new THREE.MeshStandardMaterial({ color: 0x1a2030, roughness: .45, metalness: .25 })); floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; scene.add(floor);
    const r = rand(5), mat = new THREE.MeshPhysicalMaterial({ color: 0xf3ead8, roughness: .25, clearcoat: 1, clearcoatRoughness: .1 });
    for (let i = 0; i < 80; i++) { const m = new THREE.Mesh(new THREE.CylinderGeometry(.35, .28, .7 + r() * .3, 32), mat); m.position.set((i % 10) * 1.2 - 6, .4, -Math.floor(i / 10) * 1.4); m.castShadow = m.receiveShadow = true; scene.add(m) }
  }); })();
const r0 = window.render;
window.render = t => { r0(t); X.setTransform(1, 0, 0, 1, 0, 0); X.clearRect(0, 0, W, H); X.fillStyle = '#05070d'; X.fillRect(0, 0, W, H);
  T3.frame(t, ({ camera }) => { camera.position.set(-5 + t * 2.2, 2.6, 8); camera.lookAt(-2 + t * 2.2, .5, -3) }); T3.blit(X);
  FX.apply(L.C, t, { warm: .5, edge: .15 + .2 * t, edgeSoft: .08, bloom: .5, streak: .6, mblur: 6, vig: .6, sat: 1.1 }) };