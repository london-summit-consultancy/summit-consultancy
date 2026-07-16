// Shared procedural material factories. No image textures anywhere — surface
// character comes from shader math (triplanar noise, fresnel) so the bundle
// stays self-contained and the production CSP (default-src 'none') is never
// asked to fetch an asset.
import * as THREE from "three";

// --- Particles ------------------------------------------------------------
// Soft round sprites with size attenuation, per-particle two-tone colouring,
// breathing, and a pointer attractor evaluated in the vertex shader.
export function makeParticleMaterial() {
  return new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    blending: THREE.NormalBlending,
    uniforms: {
      uTime: { value: 0 },
      uSize: { value: 1.6 },
      uPixelRatio: { value: 1 },
      uOpacity: { value: 1 },
      uColorA: { value: new THREE.Color(0x1f2937) },
      uColorB: { value: new THREE.Color(0xf59e0b) },
      uGlowMix: { value: 0.2 }, // fraction of particles taking the accent colour
      uPointer: { value: new THREE.Vector3(0, 0, 0) },
      uPointerStrength: { value: 0 },
    },
    vertexShader: /* glsl */ `
      attribute float aRand;
      uniform float uTime;
      uniform float uSize;
      uniform float uPixelRatio;
      uniform vec3 uPointer;
      uniform float uPointerStrength;
      varying float vRand;
      varying float vDepthFade;
      void main() {
        vRand = aRand;
        vec3 p = position;
        // Cursor attraction: nearby particles lean gently toward the pointer.
        vec3 toPointer = uPointer - p;
        float d = length(toPointer);
        float pull = smoothstep(9.0, 0.0, d) * uPointerStrength;
        p += normalize(toPointer + 0.0001) * pull * 1.6;
        // Idle breathing so the system always feels alive.
        p += 0.10 * vec3(
          sin(uTime * 0.6 + aRand * 31.0),
          sin(uTime * 0.5 + aRand * 47.0),
          sin(uTime * 0.7 + aRand * 17.0)
        );
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        float breathe = 0.85 + 0.3 * sin(uTime * 0.9 + aRand * 40.0);
        gl_PointSize = uSize * uPixelRatio * breathe * (14.0 + 26.0 * aRand) / max(1.0, -mv.z);
        vDepthFade = smoothstep(140.0, 30.0, -mv.z);
        gl_Position = projectionMatrix * mv;
      }
    `,
    fragmentShader: /* glsl */ `
      uniform vec3 uColorA;
      uniform vec3 uColorB;
      uniform float uOpacity;
      uniform float uGlowMix;
      varying float vRand;
      varying float vDepthFade;
      void main() {
        vec2 uv = gl_PointCoord - 0.5;
        float r = length(uv);
        float alpha = smoothstep(0.5, 0.08, r);
        vec3 col = mix(uColorA, uColorB, step(1.0 - uGlowMix, vRand));
        // Accent particles get a hot core so bloom picks them up.
        col += uColorB * step(1.0 - uGlowMix, vRand) * smoothstep(0.22, 0.0, r) * 0.9;
        gl_FragColor = vec4(col, alpha * uOpacity * vDepthFade);
        if (gl_FragColor.a < 0.004) discard;
      }
    `,
  });
}

// --- Line network -----------------------------------------------------------
// Polylines with a draw-on front: fragments past uDraw are discarded and the
// draw head glows slightly, reading as a pen sketching the geometry.
export function makeLineMaterial() {
  return new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    uniforms: {
      uDraw: { value: 0 },
      uColor: { value: new THREE.Color(0x475569) },
      uHead: { value: new THREE.Color(0xf59e0b) },
      uOpacity: { value: 1 },
    },
    vertexShader: /* glsl */ `
      attribute float aProgress;
      varying float vProgress;
      void main() {
        vProgress = aProgress;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: /* glsl */ `
      uniform float uDraw;
      uniform vec3 uColor;
      uniform vec3 uHead;
      uniform float uOpacity;
      varying float vProgress;
      void main() {
        if (vProgress > uDraw) discard;
        float head = smoothstep(0.06, 0.0, uDraw - vProgress) * step(uDraw, 0.999);
        vec3 col = mix(uColor, uHead, head);
        float fade = smoothstep(0.0, 0.02, uDraw - vProgress) * 0.9 + 0.1;
        gl_FragColor = vec4(col, uOpacity * fade);
      }
    `,
  });
}

// --- Architectural masses ---------------------------------------------------
// One shared MeshPhysicalMaterial whose colour/roughness/metalness are tweened
// between chapter states. onBeforeCompile injects triplanar concrete noise and
// a fresnel rim so surfaces read as material, not flat shading.
export function makeMassMaterial() {
  const mat = new THREE.MeshPhysicalMaterial({
    color: 0xf5f4f1,
    roughness: 0.92,
    metalness: 0.0,
    emissive: 0x000000,
  });
  mat.onBeforeCompile = (shader) => {
    shader.uniforms.uNoiseAmp = { value: 0.0 };
    shader.uniforms.uRim = { value: 0.0 };
    shader.uniforms.uRimColor = { value: new THREE.Color(0xf59e0b) };
    mat.userData.shader = shader;
    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        "#include <common>\nvarying vec3 vWorldPos;\nvarying vec3 vWorldNormal;"
      )
      .replace(
        "#include <worldpos_vertex>",
        `#include <worldpos_vertex>
        vec4 expWP = vec4(transformed, 1.0);
        vec3 expN = objectNormal;
        #ifdef USE_INSTANCING
          expWP = instanceMatrix * expWP;
          expN = mat3(instanceMatrix) * expN;
        #endif
        vWorldPos = (modelMatrix * expWP).xyz;
        vWorldNormal = normalize(mat3(modelMatrix) * expN);`
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
        varying vec3 vWorldPos;
        varying vec3 vWorldNormal;
        uniform float uNoiseAmp;
        uniform float uRim;
        uniform vec3 uRimColor;
        float mhash(vec3 p) {
          p = fract(p * 0.3183099 + 0.1);
          p *= 17.0;
          return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
        }
        float mnoise(vec3 x) {
          vec3 i = floor(x); vec3 f = fract(x);
          f = f * f * (3.0 - 2.0 * f);
          return mix(
            mix(mix(mhash(i), mhash(i + vec3(1,0,0)), f.x),
                mix(mhash(i + vec3(0,1,0)), mhash(i + vec3(1,1,0)), f.x), f.y),
            mix(mix(mhash(i + vec3(0,0,1)), mhash(i + vec3(1,0,1)), f.x),
                mix(mhash(i + vec3(0,1,1)), mhash(i + vec3(1,1,1)), f.x), f.y),
            f.z);
        }`
      )
      .replace(
        "#include <color_fragment>",
        `#include <color_fragment>
        // Triplanar-ish aggregate: two octaves of value noise in world space.
        float grain = mnoise(vWorldPos * 2.4) * 0.6 + mnoise(vWorldPos * 9.0) * 0.4;
        diffuseColor.rgb *= 1.0 - uNoiseAmp * (grain - 0.5);`
      )
      .replace(
        "#include <emissivemap_fragment>",
        `#include <emissivemap_fragment>
        // Fresnel rim — a whisper of accent light along silhouettes.
        vec3 viewDir = normalize(cameraPosition - vWorldPos);
        float fres = pow(1.0 - abs(dot(viewDir, normalize(vWorldNormal))), 3.0);
        totalEmissiveRadiance += uRimColor * fres * uRim;`
      );
  };
  return mat;
}

// --- Glass -------------------------------------------------------------------
// Envmap-driven ultra-clear structural glazing (no transmission pass — too
// costly for a 60fps budget with hundreds of panels; fresnel + reflections
// carry the read). Near-neutral tint so panels read as 92-95% clarity.
export function makeGlassMaterial() {
  return new THREE.MeshPhysicalMaterial({
    color: 0xd3dce1,
    roughness: 0.04,
    metalness: 0.0,
    transparent: true,
    opacity: 0.22,
    envMapIntensity: 2.0,
    side: THREE.DoubleSide,
    depthWrite: false,
  });
}

// --- Windows ------------------------------------------------------------------
// Pure emissive quads; per-instance intensity comes through instanceColor so a
// warm cascade can sweep the facade. Bloom does the rest.
export function makeWindowMaterial() {
  return new THREE.MeshBasicMaterial({
    color: 0xffffff,
    toneMapped: false,
  });
}

// --- Ground --------------------------------------------------------------------
// Radial-gradient void with an engineering grid that reveals from the centre
// (chapter 1) and dissolves again at the end (chapter 7).
export function makeGroundMaterial() {
  return new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    uniforms: {
      uColor: { value: new THREE.Color(0xffffff) },
      uEdgeColor: { value: new THREE.Color(0xf1f2f3) },
      uGridColor: { value: new THREE.Color(0xb8b8c0) },
      uGrid: { value: 0 }, // grid line intensity
      uReveal: { value: 0 }, // radial reveal distance
      uOpacity: { value: 1 },
    },
    vertexShader: /* glsl */ `
      varying vec2 vUv;
      varying vec3 vPos;
      void main() {
        vUv = uv;
        vPos = position;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: /* glsl */ `
      uniform vec3 uColor;
      uniform vec3 uEdgeColor;
      uniform vec3 uGridColor;
      uniform float uGrid;
      uniform float uReveal;
      uniform float uOpacity;
      varying vec2 vUv;
      varying vec3 vPos;
      void main() {
        float r = length(vPos.xy);
        vec3 col = mix(uColor, uEdgeColor, smoothstep(20.0, 110.0, r));
        // 2m engineering grid, anti-aliased, revealed radially.
        vec2 g = abs(fract(vPos.xy / 2.0) - 0.5);
        float lineW = fwidth(vPos.x) * 0.9 + 0.012;
        float line = 1.0 - smoothstep(0.0, lineW * 2.0, min(g.x, g.y) * 2.0);
        float reveal = smoothstep(uReveal, uReveal * 0.72, r);
        col = mix(col, uGridColor, line * uGrid * reveal * smoothstep(90.0, 18.0, r));
        gl_FragColor = vec4(col, uOpacity);
      }
    `,
  });
}

// --- Water ----------------------------------------------------------------------
// A pale reflecting pool — gallery daylight, not night water.
export function makeWaterMaterial() {
  return new THREE.MeshPhysicalMaterial({
    color: 0xb6c5ce,
    roughness: 0.05,
    metalness: 0.55,
    envMapIntensity: 1.6,
    transparent: true,
    opacity: 0.94,
  });
}

// --- Vegetation --------------------------------------------------------------------
// Desaturated sage, like the model trees of a museum architectural maquette.
export function makeTreeMaterial() {
  return new THREE.MeshStandardMaterial({
    color: 0x7e8b7c,
    roughness: 0.85,
    metalness: 0.0,
    flatShading: true,
  });
}
