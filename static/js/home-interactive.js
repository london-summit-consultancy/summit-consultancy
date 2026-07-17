// Home page interactivity: BIM layer switcher, fee/scope estimator, and the
// client testimonial tabs.
// This lives in a static file rather than an inline <script> because production
// enforces script-src 'self' + nonce (CONTENT_SECURITY_POLICY in
// config/settings/production.py). Inline `onclick=` handlers cannot be nonced —
// a nonce authorises a <script> element, never an event-handler attribute — so
// every binding below is addEventListener over a data-* hook. Adding handlers
// back to the markup will silently kill these controls in production while
// leaving them working in dev, where no CSP is enforced.
(function () {
  "use strict";

  // ---- 1. BIM wireframe & layer swap ------------------------------------

  const LAYERS = {
    bim: {
      svgId: "svg-layer-bim",
      btnId: "btn-layer-bim",
      numId: "layer-num-bim",
      deliverable: "3D CAD Wireframe Schema",
    },
    qs: {
      svgId: "svg-layer-qs",
      btnId: "btn-layer-qs",
      numId: "layer-num-qs",
      deliverable: "Real-Time Bill of Quantities",
    },
    timeline: {
      svgId: "svg-layer-timeline",
      btnId: "btn-layer-timeline",
      numId: "layer-num-timeline",
      deliverable: "RICS Delivery Timeline Path",
    },
  };

  // Class strings are swapped wholesale (rather than toggling single utilities)
  // to match how the template authors the active/idle states inline.
  const LAYER_BTN_ACTIVE =
    "w-full text-left p-4 rounded-xl transition-all flex items-center gap-4 border border-brand bg-brand-soft/50 text-brand-strong font-semibold shadow-sm";
  const LAYER_BTN_IDLE =
    "w-full text-left p-4 rounded-xl transition-all flex items-center gap-4 border border-line bg-surface-raised hover:border-brand-strong/30 hover:shadow-xs";
  const LAYER_NUM_ACTIVE =
    "w-8 h-8 rounded-full bg-brand text-on-brand flex items-center justify-center text-xs font-mono font-bold shadow-sm";
  const LAYER_NUM_IDLE =
    "w-8 h-8 rounded-full bg-surface-sunken flex items-center justify-center text-xs font-mono text-ink-subtle border border-line/50";

  function switchBimLayer(activeKey) {
    Object.keys(LAYERS).forEach(function (key) {
      const config = LAYERS[key];
      const isActive = key === activeKey;
      const svg = document.getElementById(config.svgId);
      const btn = document.getElementById(config.btnId);
      const num = document.getElementById(config.numId);

      if (svg) {
        svg.classList.toggle("opacity-100", isActive);
        svg.classList.toggle("scale-100", isActive);
        svg.classList.toggle("opacity-0", !isActive);
        svg.classList.toggle("scale-95", !isActive);
        svg.classList.toggle("pointer-events-none", !isActive);
        svg.classList.toggle("absolute", !isActive);
      }
      if (btn) {
        btn.className = isActive ? LAYER_BTN_ACTIVE : LAYER_BTN_IDLE;
        btn.setAttribute("aria-pressed", String(isActive));
      }
      if (num) num.className = isActive ? LAYER_NUM_ACTIVE : LAYER_NUM_IDLE;

      if (!isActive) return;

      const deliverable = document.getElementById("span-active-deliverable");
      if (deliverable) deliverable.innerText = config.deliverable;

      const status = document.getElementById("hud-status-active");
      if (status) {
        status.innerText =
          "SYS: MODEL_LOADED // LAYER_" + key.toUpperCase() + "_ENGAGED";
      }
    });
  }

  document.querySelectorAll("[data-bim-layer]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      switchBimLayer(btn.dataset.bimLayer);
    });
  });

  // Blueprint HUD coordinate readout. Pointer events (not mouse) so the readout
  // also tracks stylus/touch drags on the board.
  const board = document.getElementById("canvas-drawing-board");
  const coords = document.getElementById("hud-coordinates");
  if (board && coords) {
    board.addEventListener("pointermove", function (e) {
      const rect = board.getBoundingClientRect();
      const x = (e.clientX - rect.left).toFixed(2);
      const y = (e.clientY - rect.top).toFixed(2);
      coords.innerText = "X: " + x + " / Y: " + y;
    });
  }

  // ---- 2. Project fee & scope estimator ---------------------------------

  const SECTOR_WEIGHTS = {
    infra: { feePercent: 0.012, label: "Infrastructure & Civils", baseMonths: 18 },
    comm: { feePercent: 0.018, label: "Commercial Developments", baseMonths: 14 },
    res: { feePercent: 0.022, label: "High-End Residential", baseMonths: 10 },
  };

  // Index maps 1:1 onto the slider's 1-10 range (offset by one).
  const SLIDER_SCALES = [
    500000, 1000000, 2500000, 5000000, 7500000, 10000000, 15000000, 20000000,
    35000000, 50000000,
  ];

  const SERVICE_LABELS = {
    qs: "Quantity Surveying & Cost Audits",
    bim: "BIM & 3D Coordination",
    pm: "Project Management & Employer Agent",
    proc: "Tendering & Procurement Administration",
  };

  const SECTOR_BTN_ACTIVE =
    "py-3 px-4 rounded-xl text-xs font-semibold border transition-all text-on-brand bg-brand border-brand shadow-sm";
  const SECTOR_BTN_IDLE =
    "py-3 px-4 rounded-xl text-xs font-semibold border transition-all text-ink-muted border-line bg-surface-raised hover:border-line-strong hover:text-ink";
  const CHECK_LBL_ACTIVE =
    "flex items-center gap-3 p-3.5 rounded-xl border border-brand bg-brand-soft/50 text-brand-strong cursor-pointer shadow-sm transition-all";
  const CHECK_LBL_IDLE =
    "flex items-center gap-3 p-3.5 rounded-xl border border-line bg-surface-raised cursor-pointer hover:border-brand-strong/30 hover:shadow-xs transition-all";

  const card = document.getElementById("estimator-interactive-card");
  const slider = document.getElementById("slider-budget");
  let activeSector = "infra";

  function checkedServices() {
    const state = {};
    Object.keys(SERVICE_LABELS).forEach(function (key) {
      const input = document.getElementById("check-service-" + key);
      state[key] = Boolean(input && input.checked);
    });
    return state;
  }

  function formatCurrency(val) {
    if (val >= 1000000) return "£" + (val / 1000000).toFixed(2) + "M";
    if (val >= 1000) return "£" + (val / 1000).toFixed(0) + "k";
    return "£" + val.toFixed(0);
  }

  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.innerText = text;
  }

  function updateEstimator() {
    if (!slider) return;

    const index = parseInt(slider.value, 10) - 1;
    const rawBudget = SLIDER_SCALES[index];
    if (rawBudget === undefined) return;

    setText(
      "slider-budget-value",
      rawBudget >= 1000000
        ? "£" + (rawBudget / 1000000).toFixed(1).replace(".0", "") + "M"
        : "£" + (rawBudget / 1000).toFixed(0) + "k",
    );

    const checks = checkedServices();
    Object.keys(checks).forEach(function (srv) {
      const lbl = document.getElementById("lbl-check-" + srv);
      if (lbl) lbl.className = checks[srv] ? CHECK_LBL_ACTIVE : CHECK_LBL_IDLE;
    });

    const activeCount = Object.keys(checks).filter(function (k) {
      return checks[k];
    }).length;

    const config = SECTOR_WEIGHTS[activeSector];
    const calculatedRate = config.feePercent * (0.4 + 0.15 * activeCount);
    const feeMid = rawBudget * calculatedRate;

    setText(
      "output-fee-range",
      activeCount === 0
        ? "Select services"
        : formatCurrency(feeMid * 0.85) + " - " + formatCurrency(feeMid * 1.15),
    );

    let estMonths = config.baseMonths;
    if (index > 4) estMonths += Math.floor((index - 4) * 1.5);
    if (checks.pm) estMonths = Math.round(estMonths * 1.1);

    setText(
      "output-timeline-duration",
      activeCount === 0
        ? "Select services"
        : Math.round(estMonths * 0.9) + " - " + Math.round(estMonths * 1.15) + " Mos",
    );

    setText("output-meta-scope", config.label);
  }

  function setEstimatorSector(sector) {
    if (!SECTOR_WEIGHTS[sector]) return;
    activeSector = sector;

    document.querySelectorAll("[data-sector]").forEach(function (btn) {
      const isActive = btn.dataset.sector === sector;
      btn.className = isActive ? SECTOR_BTN_ACTIVE : SECTOR_BTN_IDLE;
      btn.setAttribute("aria-pressed", String(isActive));
    });

    updateEstimator();
  }

  document.querySelectorAll("[data-sector]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      setEstimatorSector(btn.dataset.sector);
    });
  });

  if (slider) slider.addEventListener("input", updateEstimator);

  Object.keys(SERVICE_LABELS).forEach(function (key) {
    const input = document.getElementById("check-service-" + key);
    if (input) input.addEventListener("change", updateEstimator);
  });

  // ---- 3. Copy scope blueprint ------------------------------------------

  const COPY_ICON_IDLE =
    '<path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />';
  const COPY_ICON_DONE =
    '<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />';

  function buildScopeBody() {
    const index = parseInt(slider.value, 10) - 1;
    const rawBudget = SLIDER_SCALES[index];
    const budgetStr =
      rawBudget >= 1000000
        ? "£" + rawBudget / 1000000 + "M"
        : "£" + rawBudget / 1000 + "k";

    const checks = checkedServices();
    const selected = Object.keys(SERVICE_LABELS)
      .filter(function (key) {
        return checks[key];
      })
      .map(function (key) {
        return " - [x] " + SERVICE_LABELS[key];
      });

    // Brand comes from the DOM (SiteSettings.brand_name) so this text follows a
    // rebrand instead of drifting, as the hardcoded predecessor did.
    const brand = (card && card.dataset.brand) || "London Summit Consultancy";

    return [
      "--- " + brand.toUpperCase() + " SCOPE BLUEPRINT ---",
      "Sector Focus: " + SECTOR_WEIGHTS[activeSector].label,
      "Anticipated Construction Budget: " + budgetStr,
      "Professional Services Configured:",
      selected.length ? selected.join("\n") : " - None selected",
      "",
      "Estimated Consultancy Fee Bracket: " +
        document.getElementById("output-fee-range").innerText,
      "Target Project Cycle Duration: " +
        document.getElementById("output-timeline-duration").innerText,
      "Timestamp: " + new Date().toLocaleDateString(),
      "------------------------------------------",
      "Please share this blueprint with your team or submit it directly during our consultation.",
    ].join("\n");
  }

  function flashCopyFeedback(message, icon) {
    const btnText = document.getElementById("btn-copy-text");
    const btnIcon = document.getElementById("svg-copy-icon");
    if (!btnText || !btnIcon) return;

    btnText.innerText = message;
    btnIcon.innerHTML = icon;
    window.setTimeout(function () {
      btnText.innerText = "Copy Scope Blueprint";
      btnIcon.innerHTML = COPY_ICON_IDLE;
    }, 2500);
  }

  const copyBtn = document.getElementById("btn-copy-scope");
  if (copyBtn && slider) {
    copyBtn.addEventListener("click", function () {
      const body = buildScopeBody();

      // navigator.clipboard needs a secure context and can still reject if the
      // permission is denied; fall back to a hidden textarea + execCommand so the
      // button never appears to do nothing.
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(body).then(
          function () {
            flashCopyFeedback("Blueprint Copied!", COPY_ICON_DONE);
          },
          function () {
            legacyCopy(body);
          },
        );
      } else {
        legacyCopy(body);
      }
    });
  }

  function legacyCopy(body) {
    const area = document.createElement("textarea");
    area.value = body;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();

    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch (err) {
      ok = false;
    }
    document.body.removeChild(area);

    flashCopyFeedback(
      ok ? "Blueprint Copied!" : "Copy failed — select manually",
      ok ? COPY_ICON_DONE : COPY_ICON_IDLE,
    );
  }

  // ---- 4. Client testimonial tabs ---------------------------------------

  const TESTIMONIAL_BTN_ACTIVE =
    "w-full text-left p-3.5 rounded-xl transition-all flex items-center gap-3 border border-brand bg-brand-soft/50 text-brand-strong font-bold shadow-sm";
  const TESTIMONIAL_BTN_IDLE =
    "w-full text-left p-3.5 rounded-xl transition-all flex items-center gap-3 border border-line bg-surface-raised text-ink-muted hover:border-brand/30 hover:text-ink";

  function switchTestimonial(activeIndex) {
    document
      .querySelectorAll("[data-testimonial-index]")
      .forEach(function (btn) {
        const index = parseInt(btn.dataset.testimonialIndex, 10);
        const isActive = index === activeIndex;
        const figure = document.getElementById("testimonial-figure-" + index);

        btn.className = isActive
          ? TESTIMONIAL_BTN_ACTIVE
          : TESTIMONIAL_BTN_IDLE;
        btn.setAttribute("aria-pressed", String(isActive));

        if (!figure) return;
        figure.classList.toggle("opacity-100", isActive);
        figure.classList.toggle("scale-100", isActive);
        figure.classList.toggle("relative", isActive);
        figure.classList.toggle("z-10", isActive);
        figure.classList.toggle("opacity-0", !isActive);
        figure.classList.toggle("scale-95", !isActive);
        figure.classList.toggle("pointer-events-none", !isActive);
        figure.classList.toggle("absolute", !isActive);
      });
  }

  document
    .querySelectorAll("[data-testimonial-index]")
    .forEach(function (btn) {
      btn.addEventListener("click", function () {
        switchTestimonial(parseInt(btn.dataset.testimonialIndex, 10));
      });
    });

  // ---- Bootstrap --------------------------------------------------------
  // This file is loaded with `defer`, so the DOM is already parsed here — no
  // DOMContentLoaded wrapper needed (and one would be a no-op risk if the event
  // had already fired).
  updateEstimator();
})();
