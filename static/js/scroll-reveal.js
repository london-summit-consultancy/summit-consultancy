// Refined scroll-motion engine: reveal-on-scroll, staggered groups,
// animated stat counters, and a subtle hero parallax.
// Fully disabled when the user prefers reduced motion. Re-runnable after
// HTMX swaps via window.LSMotion.init().
(function () {
  "use strict";

  const reduceMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)",
  ).matches;

  // ---- Reveal on scroll -------------------------------------------------
  let revealObserver = null;

  function setupReveals() {
    const items = document.querySelectorAll("[data-reveal]:not(.is-visible)");
    if (!items.length) return;

    // Stagger children within any [data-reveal-group]; an authored
    // data-reveal-delay on a child overrides its computed position so a
    // specific beat (e.g. a CTA) can be timed deliberately.
    document.querySelectorAll("[data-reveal-group]").forEach(function (group) {
      const step = parseInt(group.dataset.revealGroup, 10) || 200;
      group
        .querySelectorAll("[data-reveal]:not([data-reveal-delay-set])")
        .forEach(function (el, i) {
          const authored = el.getAttribute("data-reveal-delay");
          const delay = authored !== null ? parseInt(authored, 10) : i * step;
          el.style.setProperty("--reveal-delay", delay + "ms");
          el.setAttribute("data-reveal-delay-set", "");
        });
    });

    // Standalone reveals (outside any group) with an authored delay.
    document
      .querySelectorAll(
        "[data-reveal][data-reveal-delay]:not([data-reveal-delay-set])",
      )
      .forEach(function (el) {
        el.style.setProperty(
          "--reveal-delay",
          parseInt(el.getAttribute("data-reveal-delay"), 10) + "ms",
        );
        el.setAttribute("data-reveal-delay-set", "");
      });

    if (reduceMotion) {
      items.forEach(function (el) {
        el.classList.add("is-visible");
      });
      return;
    }

    if (!revealObserver) {
      revealObserver = new IntersectionObserver(
        function (entries) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting) {
              entry.target.classList.add("is-visible");
              revealObserver.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.12, rootMargin: "0px 0px -8% 0px" },
      );
    }
    items.forEach(function (el) {
      revealObserver.observe(el);
    });
  }

  // ---- Animated counters ------------------------------------------------
  function animateCounter(el) {
    const target = parseFloat(el.dataset.to || "0");
    const suffix = el.dataset.suffix || "";
    const prefix = el.dataset.prefix || "";
    const duration = parseInt(el.dataset.duration || "1600", 10);
    const start = performance.now();

    function tick(now) {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3); // easeOutCubic
      const value = Math.round(target * eased);
      el.textContent = prefix + value.toLocaleString() + suffix;
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  function setupCounters() {
    const counters = document.querySelectorAll(
      "[data-counter]:not([data-counted])",
    );
    if (!counters.length) return;

    if (reduceMotion) {
      counters.forEach(function (el) {
        el.setAttribute("data-counted", "");
        el.textContent =
          (el.dataset.prefix || "") +
          parseFloat(el.dataset.to || "0").toLocaleString() +
          (el.dataset.suffix || "");
      });
      return;
    }

    const obs = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.setAttribute("data-counted", "");
            animateCounter(entry.target);
            obs.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.6 },
    );
    counters.forEach(function (el) {
      obs.observe(el);
    });
  }

  // ---- Subtle parallax --------------------------------------------------
  let parallaxEls = [];
  let ticking = false;

  function onScroll() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function () {
      const vh = window.innerHeight;
      parallaxEls.forEach(function (el) {
        const rect = el.getBoundingClientRect();
        if (rect.bottom < 0 || rect.top > vh) return;
        const speed = parseFloat(el.dataset.parallax) || 0.15;
        const offset = (rect.top + rect.height / 2 - vh / 2) * speed;
        el.style.transform = "translate3d(0," + offset.toFixed(1) + "px,0)";
      });
      ticking = false;
    });
  }

  function setupParallax() {
    if (reduceMotion) return;
    parallaxEls = Array.prototype.slice.call(
      document.querySelectorAll("[data-parallax]"),
    );
    if (!parallaxEls.length) return;
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  function init() {
    setupReveals();
    setupCounters();
    setupParallax();
  }

  window.LSMotion = { init: init };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Re-scan after HTMX swaps (portfolio / services filtering).
  document.body.addEventListener("htmx:afterSwap", function () {
    setupReveals();
    setupCounters();
  });
})();
