// Theme manager — light / dark / system.
// No-FOUC: the inline <head> script in base.html resolves and applies the
// concrete data-theme attribute before first paint. This file owns the
// interactive toggle, persistence, and reacting to OS changes in "system" mode.
(function () {
  "use strict";

  const STORAGE_KEY = "lsc-theme"; // stores the user *choice*: light | dark | system
  const LEGACY_STORAGE_KEY = "pcl-theme"; // pre-rebrand key; still honoured on read
  const root = document.documentElement;
  const mql = window.matchMedia("(prefers-color-scheme: dark)");

  function getChoice() {
    return (
      localStorage.getItem(STORAGE_KEY) || localStorage.getItem(LEGACY_STORAGE_KEY) || "system"
    );
  }

  function resolve(choice) {
    if (choice === "system") {
      return mql.matches ? "dark" : "light";
    }
    return choice;
  }

  function apply(choice) {
    const resolved = resolve(choice);
    root.setAttribute("data-theme", resolved);
    if (choice === "system") {
      localStorage.removeItem(STORAGE_KEY);
    } else {
      localStorage.setItem(STORAGE_KEY, choice);
    }
    syncToggle(choice);
  }

  function syncToggle(choice) {
    document.querySelectorAll(".theme-toggle-option").forEach(function (btn) {
      btn.setAttribute("aria-checked", String(btn.dataset.theme === choice));
    });
  }

  function initToggle() {
    document.querySelectorAll(".theme-toggle").forEach(function (group) {
      group.addEventListener("click", function (e) {
        const btn = e.target.closest(".theme-toggle-option");
        if (btn) apply(btn.dataset.theme);
      });
    });
    syncToggle(getChoice());
  }

  // Mobile nav toggle — moved out of an inline onclick so a strict CSP
  // (script-src 'self') can allow it without 'unsafe-inline'.
  function initMobileNav() {
    const btn = document.getElementById("mobile-nav-toggle");
    const nav = document.getElementById("mobile-nav");
    if (!btn || !nav) return;
    btn.addEventListener("click", function () {
      const isHidden = nav.classList.toggle("hidden");
      btn.setAttribute("aria-expanded", String(!isHidden));
    });
  }

  // React to OS theme changes only while the user is on "system".
  mql.addEventListener("change", function () {
    if (getChoice() === "system") apply("system");
  });

  // Account dropdown is a native <details> (CSP-safe, no inline JS). Native
  // <details> doesn't close on outside click or Escape, so wire that here.
  function initAccountMenu() {
    const menu = document.querySelector("details.account-menu");
    if (!menu) return;
    document.addEventListener("click", function (e) {
      if (menu.open && !menu.contains(e.target)) menu.open = false;
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && menu.open) menu.open = false;
    });
  }

  function init() {
    initToggle();
    initMobileNav();
    initAccountMenu();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Re-sync the toggle after HTMX swaps that replace the header (defensive).
  document.body.addEventListener("htmx:afterSwap", function () {
    syncToggle(getChoice());
  });
})();
