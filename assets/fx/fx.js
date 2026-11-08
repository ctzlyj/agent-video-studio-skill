/* FX: full-screen WebGL2 post-processing, deterministic (pure function of uniforms set per frame).
   Pipeline: DOM/Canvas2D scene layers are composed into one 2D canvas "src"; this shader then adds
   chromatic aberration, multi-tap bloom, anamorphic streak, light-sweep transition, glitch slices,
   vignette, film grain and a cold->warm grade driven by a single "warmth" uniform. */
(function () {
  const W = AVS.FMT.w, H = AVS.FMT.h;
  const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  cv.style.cssText = `position:absolute;left:0;top:0;width:${W}px;height:${H}px;z-index:50;pointer-events:none`;
  const gl = cv.getContext('webgl2', { premultipliedAlpha: false, alpha: true, antialias: false, preserveDrawingBuffer: true });
  const VS = `#version 300 es
  in vec2 p; out vec2 uv; void main(){ uv = p*.5+.5; uv.y = 1.-uv.y; gl_Position = vec4(p,0,1); }`;
  const FS = `#version 300 es
  precision highp float; in vec2 uv; out vec4 o;
  uniform sampler2D src; uniform vec2 R; uniform float t;
  uniform float warm;      // 0 cold-blue grade .. 1 warm-gold grade
  uniform float ca;        // chromatic aberration px
  uniform float bloom;     // bloom strength
  uniform float sweep;     // light sweep progress 0..1 (<0 = off)
  uniform float glitch;    // glitch amount
  uniform float shake;     // screen shake px
  uniform float vig;       // vignette
  uniform float flash;     // white flash
  uniform float sat;       // saturation multiplier
  uniform float streak;    // anamorphic streak strength
  float h(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
  float n(vec2 p){ vec2 i=floor(p),f=fract(p); f=f*f*(3.-2.*f); return mix(mix(h(i),h(i+vec2(1,0)),f.x),mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x),f.y); }
  vec3 S(vec2 u){ return texture(src, clamp(u, vec2(0.001), vec2(.999))).rgb; }
  void main(){
    vec2 u = uv; vec2 px = 1./R;
    // screen shake (deterministic from t)
    u += vec2(sin(t*91.)+sin(t*53.+1.), cos(t*77.)+cos(t*61.+2.)) * .5 * shake * px;
    // glitch: horizontal slice displacement
    if (glitch > 0.){
      float band = floor(u.y*38. + floor(t*24.)*7.);
      float g = step(.72, h(vec2(band, floor(t*24.)))) * glitch;
      u.x += (h(vec2(band, 3.))-.5) * .09 * g;
    }
    // chromatic aberration (radial)
    vec2 d = (u-.5); float r2 = dot(d,d);
    vec2 off = d * (ca*px.x*1.0) * (.4 + r2*3.);
    vec3 c = vec3(S(u+off).r, S(u).g, S(u-off).b);
    // bloom: 12-tap golden-angle disc, two radii
    vec3 b = vec3(0.); float tw = 0.;
    for (int i=0;i<12;i++){
      float a = float(i)*2.39996; float rr = sqrt(float(i)+.5)/3.4;
      vec2 o1 = vec2(cos(a),sin(a))*rr*px*34.;
      vec3 s1 = S(u+o1); vec3 s2 = S(u+o1*2.6);
      s1 = max(s1-.55, 0.); s2 = max(s2-.5, 0.);
      b += s1*1.0 + s2*.8; tw += 1.8;
    }
    b /= tw; c += b * bloom * 2.6;
    // anamorphic horizontal streak (bright pixels smear sideways)
    if (streak > 0.){
      vec3 sk = vec3(0.);
      for (int i=-8;i<=8;i++){ float w = exp(-abs(float(i))*.28); sk += max(S(u+vec2(float(i)*px.x*26., 0.))-.62, 0.)*w; }
      c += sk * streak * vec3(.55,.75,1.) * .22;
    }
    // light sweep: diagonal warm band wiping across, revealing via additive glow
    if (sweep >= 0.){
      float pos = mix(-.35, 1.35, sweep); float dd = (u.x*.55 + u.y*.45) - pos;
      float band = exp(-dd*dd*70.); c += band * vec3(1.,.82,.45) * 1.6 + exp(-dd*dd*8.)*vec3(.5,.34,.12)*.35;
    }
    // grade: cold(teal/blue, desaturated, crushed) <-> warm(gold, rich)
    float L = dot(c, vec3(.299,.587,.114));
    vec3 cold = mix(vec3(L), c, .55) * vec3(.82,.95,1.12);
    vec3 warmc = c * vec3(1.08,1.0,.86) + vec3(.02,.01,0.);
    c = mix(cold, warmc, warm);
    c = mix(vec3(dot(c,vec3(.299,.587,.114))), c, sat);
    // filmic curve
    c = c/(c+vec3(.66)) * 1.62;
    c = pow(c, vec3(.94));
    // vignette
    c *= 1. - vig * smoothstep(.28, .95, length((uv-.5)*vec2(R.x/R.y,1.)*1.15));
    // film grain
    c += (h(uv*R + fract(t*7.)*100.) - .5) * .045;
    c += flash;
    o = vec4(clamp(c, 0., 1.), 1.);
  }`;
  function sh(ty, s){ const x = gl.createShader(ty); gl.shaderSource(x, s); gl.compileShader(x); if (!gl.getShaderParameter(x, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(x)); return x }
  const pr = gl.createProgram(); gl.attachShader(pr, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, FS)); gl.linkProgram(pr); gl.useProgram(pr);
  const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,3,-1,-1,3]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(pr, 'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const tex = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  const U = {}; for (const k of ['src','R','t','warm','ca','bloom','sweep','glitch','shake','vig','flash','sat','streak']) U[k] = gl.getUniformLocation(pr, k);
  gl.uniform1i(U.src, 0); gl.uniform2f(U.R, W, H); gl.viewport(0, 0, W, H);
  const D = { warm: .5, ca: 0, bloom: .35, sweep: -1, glitch: 0, shake: 0, vig: .55, flash: 0, sat: 1, streak: 0 };
  function apply(srcCanvas, t, o) {
    const v = Object.assign({}, D, o || {});
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, srcCanvas);
    gl.uniform1f(U.t, t); for (const k of ['warm','ca','bloom','sweep','glitch','shake','vig','flash','sat','streak']) gl.uniform1f(U[k], v[k]);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }
  window.FX = { canvas: cv, apply, W, H };
})();