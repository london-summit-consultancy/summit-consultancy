// London Summit experience — boot. Self-booting IIFE bundle (esbuild): scans
// for [data-experience] mounts, gates on reduced-motion and WebGL2, then runs
// either the journey (homepage film) or the ambient motif. Without JS, WebGL
// or with reduced motion, the server-rendered page stands entirely on its own
// — this file simply never flips `data-experience-on`.
import { Ambient } from "./ambient/ambient.js";
import { Journey } from "./core/journey.js";
import { detectTier, webgl2Available } from "./core/quality.js";
import { mountHero } from "./hero/hero.js";

function bootExperience() {
  const root = document.querySelector("[data-experience]");
  if (!root) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  if (!webgl2Available()) return;

  const mode = root.getAttribute("data-experience");
  const tier = detectTier(mode);

  let app;
  try {
    app = mode === "journey" ? new Journey(root, tier) : new Ambient(root, tier);
  } catch {
    return; // context creation can still fail (blocklisted drivers) — fall back
  }
  document.documentElement.setAttribute("data-experience-on", "");

  let last = performance.now();
  let rafId = 0;
  // The scene renders only while it is both on-screen and the tab is visible.
  // On the homepage the wireframe hero sits above this film; parking the loop
  // when the journey scrolls out of view keeps the two WebGL scenes from ever
  // burning frames at the same time.
  let onScreen = true;
  let docVisible = !document.hidden;

  const loop = (now) => {
    rafId = requestAnimationFrame(loop);
    const dt = Math.min((now - last) / 1000, 0.05);
    last = now;
    app.update(dt, now / 1000);
  };

  const sync = () => {
    const shouldRun = onScreen && docVisible;
    if (shouldRun && !rafId) {
      last = performance.now();
      rafId = requestAnimationFrame(loop);
    } else if (!shouldRun && rafId) {
      cancelAnimationFrame(rafId);
      rafId = 0;
    }
  };
  rafId = requestAnimationFrame(loop);

  if ("IntersectionObserver" in window) {
    new IntersectionObserver(
      (entries) => {
        onScreen = entries[0].isIntersecting;
        sync();
      },
      { threshold: 0 }
    ).observe(root);
  }

  document.addEventListener("visibilitychange", () => {
    docVisible = !document.hidden;
    sync();
  });

  let resizeTimer = 0;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => app.resize(), 150);
  });
}

function boot() {
  // The hero self-gates (no-ops without its mount) and owns its own loop.
  mountHero();
  bootExperience();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}
