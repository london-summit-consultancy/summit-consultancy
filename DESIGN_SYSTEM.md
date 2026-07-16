# Pioneer Consultants — UI Design System (Neumorphic)

The site's visual language is **neumorphism**: a single low-contrast surface
carries the whole UI, and depth is created **only** by dual-directional shadows
(light top-left, dark bottom-right) — never by different background colors. The
accent is Pioneer **green**; type is **Inter** throughout; corners are a soft
**8px**. This document is the developer/design handoff reference.

**Source of truth:** `assets/css/input.css` (Tailwind v4, CSS-first `@theme`).
Rebuild the compiled stylesheet after any edit:

```bash
npm run css:build   # tailwindcss -i assets/css/input.css -o static/css/main.css --minify
```

All UI is **CSP-safe** (no inline JS, no external CDNs, self-hosted Inter) and
**theme-aware** — never hardcode a color that a semantic token already covers.

---

## 1. The one rule of this system

**Everything shares `--color-surface`.** Page, header, footer, hero, cards,
buttons, inputs and chips are all the *same* background color. Separation is
never a different fill — it is a shadow:

- **Raised** (`--neu-sm` … `--neu-2xl`): the element sits *above* the surface.
- **Pressed / inset** (`--neu-inset`): the element is stamped *into* the surface
  (inputs, active states, wells).

Prohibited: solid colored section backgrounds, alternating section colors, or
colored button/card/badge fills. Meaning and state are carried by **text/icon
color**, not background.

---

## 2. Design Tokens

Semantic CSS custom properties consumed by Tailwind utilities as `var(--color-*)`
(`bg-surface`, `text-ink`, `border-line`) and by the `.neu-*` utilities /
component classes for shadows. Dark mode overrides only what changes.

### Color — light / dark

| Token | Light | Dark | Use |
|---|---|---|---|
| `surface` (+ `-sunken`/`-raised`/`-soft`) | `#ecf0f3` | `#262833` | the **only** background |
| `brand` / `brand-strong` | `#128759` | `#20b27a` | brand green — **text/icon**, accessible links |
| `brand-hover` | `#0e6d47` | `#2ac78a` | link/hover green |
| `on-brand` | `#ffffff` | `#0b1a12` | text on the few brand fills (skip link, logo tile) |
| `secondary` | `#389dc6` | `#389dc6` | secondary icons / charts |
| `ink` | `#31344b` | `#ecf0f3` | headings |
| `ink-muted` | `#44476a` | `#93a5be` | body |
| `ink-subtle` | `#66799e` | `#7f8fa8` | subtle labels / placeholders |
| `line` / `line-strong` | `#d5dbe3` / `#c4ccd7` | `#33363f` / `#3d4049` | subtle borders |
| `positive` / `danger` | `#128759` / `#d1435b` | `#20b27a` / `#f2889b` | feedback (text only) |
| `night` / `night-2` | `#262833` / `#2b2e3a` | `#1c1e27` / `#20222c` | legacy tokens, kept dark for out-of-scope staff surfaces |

### Elevation — neumorphic shadow tokens

`--neu-2xs … --neu-2xl` (raised) and `--neu-inset` (pressed) are defined per
theme (dark mode shifts the shadow colors to darker/lighter variants of
`#262833`). Exposed as utilities `neu-2xs … neu-2xl`, `neu-inset` — use these,
**not** Tailwind's `shadow-*`, so a single class re-themes in dark mode.

| Elevation | Token |
|---|---|
| Subtle detail, active pills | `neu-2xs` / `neu-xs` |
| Buttons, interactive cards, chips, icon tiles | `neu-sm` |
| Standard cards, dropdowns | `neu-md` |
| Prominent / CTA cards | `neu-lg` |
| Modals, top-level emphasis (sparingly) | `neu-xl` / `neu-2xl` |
| Inputs, wells, pressed/active states | `neu-inset` |

### Typography / radius / motion

- **Font:** self-hosted **Inter** carries body, UI and headings (`--font-sans`;
  `--font-display`/`--font-mono` also map to Inter). Headings are semibold (600).
- **Radius:** **8px** for cards/buttons/inputs; `9999px` for pills, chips,
  icon tiles and the theme toggle.
- **Easing:** `--ease-out-expo` `cubic-bezier(0.16,1,0.3,1)`.

---

## 3. Components (in `@layer components`)

| Class | What |
|---|---|
| `.btn` + `.btn-primary` / `.btn-dark` / `.btn-ghost` | Buttons. All share the surface; variants differ only by text color. Raised (`neu-sm`) → hover `neu-md` → active `neu-inset`. Ghost is flat until hover. |
| `.card` (+ `.card-interactive`) | Extruded surface. Static = `neu-md`; interactive rests at `neu-sm`, lifts on hover, presses in on active. |
| `.neu-icon` (+ `.neu-icon-inset`) | Round icon tile — raised (or stamped-in) circle holding a brand-colored icon. |
| `.neu-index` | Small pressed-in "01 / 02 …" section badge. |
| `.chip` | Segmented pill filter. Raised idle; `.is-active` = pressed-in (`neu-inset`) + brand text. |
| `.kicker` | All-caps micro-label with a brand dot. |
| `.field-label` / `.field-input` (`.has-error`) | Form controls; inputs are **inset** (pressed into the surface), green focus ring. |
| `.theme-toggle` / `.theme-toggle-option` | Inset track holding raised option pills. |
| `.link-underline` | Animated left-origin underline. |
| `.rich-text` | Prose renderer for `body`/`linebreaks` content. |

The homepage hero (`templates/core/_hero_wireframe.html`) is a soft-surface
headline column beside an **extruded medallion** (raised rings + an inset well +
floating discipline chips) — no WebGL, fully server-rendered.

---

## 4. Dark mode

Driven by `data-theme="dark"` on `<html>`, set **pre-paint** by the nonce'd
inline script in `templates/base.html` (reads `localStorage['lsc-theme']` /
`['pcl-theme']`). `@custom-variant dark` binds Tailwind's `dark:` to the
attribute. Both the color tokens **and** the `--neu-*` shadow tokens are
re-declared under `[data-theme="dark"]` so the extruded illusion survives on the
dark surface.

---

## 5. Accessibility (WCAG 2.1 AA)

- **Contrast:** `ink` ~11:1, `ink-muted` ~6:1, `ink-subtle` ≥4.5:1, brand-green
  link ≥4.5:1, in both themes. Verify any new interactive text before merge.
- **Focus:** global `:focus-visible` → 2px brand outline, 2px offset.
- **Motion:** reveals gated behind `@media (prefers-reduced-motion: no-preference)`
  + `html.js`; no-JS / reduced-motion users always see full content.
- **Semantics:** one `<h1>` per page; `<button>` for actions, `<a>` for nav;
  decorative visuals are `aria-hidden`; skip-to-content link first in the body.

---

## 6. Contribution rules

1. **One surface.** Never introduce a second background color to separate
   elements — reach for a `neu-*` shadow instead.
2. Use semantic tokens, not raw hex.
3. Keep 8px radius and the `neu-*` elevation vocabulary; reuse an existing
   component (`.card`, `.btn`, `.chip`, `.neu-icon`) before writing new CSS.
4. New interactive text must clear **4.5:1** in both themes.
5. No inline JS / external assets (strict CSP). Rebuild CSS after edits.
