// Site motion — GSAP + ScrollTrigger choreography for the homepage scroll.
// Self-hosted (bundled by esbuild → static/js/motion.min.js) so it runs under
// the strict CSP (script-src 'self'); GSAP core + ScrollTrigger need no eval.
//
// Declarative: templates opt in with data-attributes and this module wires the
// scroll behaviour. Nothing here is required for content — under reduced motion
// or no-JS every target is fully visible; we only add the entrances.
//
//   [data-animate="rise|fade|mask|scale|left|right"]  reveal on enter
//   [data-animate-group] + data-stagger="ms"          stagger children's reveal
//   [data-animate-delay="ms"]                          per-element offset
//   [data-draw]                                        hairline draws in (scaleX)
//   [data-parallax="0.15"]                             scrub parallax (yPercent)
//   [data-count] data-to data-suffix data-prefix       counter on enter
//   [data-pin-steps]                                    pin block; steps advance
//   [data-sheet-progress]                              chapter-spine fill bar
//   [data-chapter-node]                                lights when its chapter is reached
import gsap from "gsap";
import ScrollTrigger from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

const EASE = "expo.out";
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function q(sel, root = document) {
  return Array.from(root.querySelectorAll(sel));
}

// ---------------------------------------------------------------------------
// Reveals — rise/fade/mask/scale/left/right, singly or staggered in a group.
const HIDDEN = {
  rise: { autoAlpha: 0, y: 40 },
  fade: { autoAlpha: 0 },
  mask: { autoAlpha: 0, y: 30 },
  scale: { autoAlpha: 0, scale: 0.94 },
  left: { autoAlpha: 0, x: -48 },
  right: { autoAlpha: 0, x: 48 },
};

function revealTo(kind) {
  return {
    rise: { autoAlpha: 1, y: 0 },
    fade: { autoAlpha: 1 },
    mask: { autoAlpha: 1, y: 0 },
    scale: { autoAlpha: 1, scale: 1 },
    left: { autoAlpha: 1, x: 0 },
    right: { autoAlpha: 1, x: 0 },
  }[kind];
}

function setupReveals() {
  // Grouped reveals — children animate together with a stagger. The `aInit`
  // guard makes this safe to call repeatedly (e.g. on every htmx:afterSwap):
  // already-wired elements are skipped, so a partial swap never re-hides copy
  // that is already on screen — only genuinely new nodes get set up.
  q("[data-animate-group]").forEach((group) => {
    if (group.dataset.aInit) return;
    group.dataset.aInit = "1";
    const stagger = (parseInt(group.dataset.stagger || "120", 10) || 120) / 1000;
    const items = q("[data-animate]", group).filter((el) => el.closest("[data-animate-group]") === group);
    if (!items.length) return;
    items.forEach((el) => gsap.set(el, HIDDEN[el.dataset.animate] || HIDDEN.rise));
    ScrollTrigger.create({
      trigger: group,
      start: "top 82%",
      once: true,
      onEnter: () => {
        items.forEach((el, i) => {
          gsap.to(el, {
            ...revealTo(el.dataset.animate || "rise"),
            duration: 1.15,
            ease: EASE,
            delay: i * stagger,
          });
        });
      },
    });
  });

  // Standalone reveals (not inside a group).
  q("[data-animate]")
    .filter((el) => !el.parentElement.closest("[data-animate-group]"))
    .forEach((el) => {
      if (el.dataset.aInit) return;
      el.dataset.aInit = "1";
      const kind = el.dataset.animate || "rise";
      gsap.set(el, HIDDEN[kind] || HIDDEN.rise);
      const delay = (parseInt(el.dataset.animateDelay || "0", 10) || 0) / 1000;
      ScrollTrigger.create({
        trigger: el,
        start: "top 84%",
        once: true,
        onEnter: () =>
          gsap.to(el, { ...revealTo(kind), duration: 1.15, ease: EASE, delay }),
      });
    });
}

// ---------------------------------------------------------------------------
// Hairline draw-in — datum rules and dividers draw left→right on enter.
function setupDraw() {
  q("[data-draw]").forEach((el) => {
    if (el.dataset.dInit) return;
    el.dataset.dInit = "1";
    gsap.set(el, { transformOrigin: "left center", scaleX: 0 });
    ScrollTrigger.create({
      trigger: el,
      start: "top 88%",
      once: true,
      onEnter: () => gsap.to(el, { scaleX: 1, duration: 1.3, ease: EASE }),
    });
  });
}

// ---------------------------------------------------------------------------
// Parallax — light scrub drift for depth (index numbers, decorative marks).
function setupParallax() {
  q("[data-parallax]").forEach((el) => {
    const amount = parseFloat(el.dataset.parallax) || 0.15;
    gsap.to(el, {
      yPercent: -amount * 100,
      ease: "none",
      scrollTrigger: {
        trigger: el,
        start: "top bottom",
        end: "bottom top",
        scrub: true,
      },
    });
  });
}

// ---------------------------------------------------------------------------
// Counters — tick up once when the stat scrolls in.
function setupCounters() {
  q("[data-count], [data-counter]").forEach((el) => {
    if (el.dataset.cInit) return;
    el.dataset.cInit = "1";
    const to = parseFloat(el.dataset.to || "0");
    const suffix = el.dataset.suffix || "";
    const prefix = el.dataset.prefix || "";
    const set = (v) => (el.textContent = prefix + Math.round(v).toLocaleString() + suffix);
    set(0);
    ScrollTrigger.create({
      trigger: el,
      start: "top 88%",
      once: true,
      onEnter: () => {
        const obj = { v: 0 };
        gsap.to(obj, { v: to, duration: 1.8, ease: "power2.out", onUpdate: () => set(obj.v) });
      },
    });
  });
}

// ---------------------------------------------------------------------------
// Pinned step block — pins a section and cross-fades its "steps" as you scroll
// (used for the process / who-we-work-with panel). Steps: [data-step] items,
// with matching [data-step-media] visuals keyed by index.
function setupPinnedSteps() {
  q("[data-pin-steps]").forEach((block) => {
    const steps = q("[data-step]", block);
    const medias = q("[data-step-media]", block);
    if (steps.length < 2) return;

    block.classList.add("is-pinned"); // enables the JS-only step dimming
    const setActive = (idx) => {
      steps.forEach((s, i) => s.classList.toggle("is-active", i === idx));
      medias.forEach((m, i) => gsap.to(m, { autoAlpha: i === idx ? 1 : 0, duration: 0.4, ease: "power2.out" }));
    };
    setActive(0);

    ScrollTrigger.create({
      trigger: block,
      start: "top top",
      end: "+=" + steps.length * 55 + "%",
      pin: true,
      scrub: 0.5,
      onUpdate: (self) => {
        const idx = Math.min(steps.length - 1, Math.floor(self.progress * steps.length));
        setActive(idx);
      },
    });
  });
}

// ---------------------------------------------------------------------------
// Chapter spine — the storyteller thread. One orange datum fills top→reader as
// the drawing sheet is travelled, and each chapter's numbered node lights the
// moment its section is reached, so the whole page reads as one connected
// narrative rather than a stack of independent blocks.
function setupSpine() {
  const bar = document.querySelector("[data-sheet-progress]");
  const sheet = document.querySelector(".sheet");
  if (bar && sheet) {
    gsap.set(bar, { transformOrigin: "top center", scaleY: 0 });
    gsap.to(bar, {
      scaleY: 1,
      ease: "none",
      scrollTrigger: {
        trigger: sheet,
        start: "top 55%",
        end: "bottom bottom",
        scrub: 0.3,
      },
    });
  }

  q("[data-chapter-node]").forEach((node) => {
    const chapter = node.closest(".chapter") || node;
    ScrollTrigger.create({
      trigger: chapter,
      start: "top 72%",
      once: true,
      onEnter: () => node.classList.add("is-reached"),
    });
  });
}

// ---------------------------------------------------------------------------
// Scroll reveals (IntersectionObserver)
// For elements using [data-reveal] and [data-reveal-group]
const revealObserver = new IntersectionObserver((entries, observer) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      const target = entry.target;
      if (target.dataset.revealGroup !== undefined || target.getAttribute("data-reveal-group") !== null) {
        const items = q("[data-reveal]", target).filter((el) => el.closest("[data-reveal-group]") === target);
        items.forEach((item) => {
          item.classList.add("is-visible");
        });
      } else {
        target.classList.add("is-visible");
      }
      observer.unobserve(target);
    }
  });
}, {
  root: null,
  rootMargin: "0px 0px -10% 0px", // Trigger slightly inside the viewport
  threshold: 0.05
});

function setupScrollReveals() {
  // 1. Grouped reveals
  q("[data-reveal-group]").forEach((group) => {
    if (group.dataset.rgInit) return;
    group.dataset.rgInit = "1";
    
    // Get stagger speed (default 100ms)
    const stagger = parseInt(group.getAttribute("data-reveal-group") || "100", 10) || 100;
    
    // Get immediate children that need reveal
    const items = q("[data-reveal]", group).filter((el) => el.closest("[data-reveal-group]") === group);
    
    // Set custom reveal delay property on children
    items.forEach((item, index) => {
      item.style.setProperty("--reveal-delay", `${index * stagger}ms`);
    });
    
    revealObserver.observe(group);
  });

  // 2. Standalone reveals (not nested in a group)
  q("[data-reveal]").forEach((el) => {
    if (el.dataset.rInit) return;
    const parentGroup = el.parentElement && el.parentElement.closest("[data-reveal-group]");
    if (parentGroup) return; // handled by group
    
    el.dataset.rInit = "1";
    revealObserver.observe(el);
  });
}

// ---------------------------------------------------------------------------
function boot() {
  if (reduceMotion) {
    // Make sure nothing GSAP would have hidden stays hidden, and show the
    // chapter nodes in their final (reached) state.
    q("[data-animate], [data-draw]").forEach((el) => gsap.set(el, { clearProps: "all" }));
    q("[data-chapter-node]").forEach((el) => el.classList.add("is-reached"));
    q("[data-reveal]").forEach((el) => el.classList.add("is-visible"));
    return;
  }
  setupReveals();
  setupScrollReveals();
  setupDraw();
  setupParallax();
  setupCounters();
  setupPinnedSteps();
  setupSpine();
  // HTMX may swap section content (portfolio/services filters) — re-scan.
  document.body.addEventListener("htmx:afterSwap", () => {
    setupReveals();
    setupScrollReveals();
    setupDraw();
    ScrollTrigger.refresh();
  });
  window.addEventListener("load", () => ScrollTrigger.refresh());
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}
