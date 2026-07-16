# What Changed on Your Website — Plain-English Summary

This round of work was about making the Pioneer Consultants website **safer,
faster, and easier for you to update yourself** — without changing how it looks
to visitors. Here is what was done, and why it matters to the business.

---

### 1. Fixed how the site stores its files
The website was using an old setting that the current version of our software
quietly ignores. That meant images and design files could have failed to load
correctly once the site went live. This is now fixed and set up properly for the
live server, so styling and images stay reliable.

### 2. The site no longer depends on Google or outside services to load its fonts
Previously, the fonts and one small piece of behaviour code were loaded from
Google's and another company's servers. Now they're hosted on our own site. That
means:
- **Faster loading** (fewer outside connections).
- **Better privacy** for visitors (nothing is quietly pinged to Google).
- **No breakage** if one of those outside services has an outage.

### 3. Added a strong security shield ("Content Security Policy")
Think of this as a bouncer for the website: it only allows code and content from
approved sources to run. This protects visitors from a common class of attacks
where a bad actor tries to inject malicious code into a page. It's now switched
**on and enforced** on the live site.

### 4. Proper "Page Not Found" and "Something Went Wrong" pages
If a visitor hits a broken link or the site has a hiccup, they now see a branded,
professional page (in Pioneer's colours and style) with a friendly message and a
way back home — instead of an ugly technical error screen.

### 5. You can now edit company details yourself
Your **Companies House registration number** and **year founded** can now be
edited from the admin area, no developer needed. The founding year also feeds the
data that Google reads about your business.

### 6. Made client enquiries safe from a rare glitch
When your team updates the status of a contact enquiry (e.g. "New" → "Contacted"),
the system now saves everything in one safe step. If something invalid is
attempted, nothing is half-saved — it cleanly refuses and tells the user, so your
enquiry records can't end up in a confusing in-between state.

### 7. Google now understands you as a professional services firm
The hidden information that search engines read has been upgraded so Google
recognises Pioneer as a **professional consultancy serving Saudi Arabia**. This
supports how your business appears in search results.

### 8. Richer text editing for your content — safely
The **About** section and **project case studies** now have a proper rich-text
editor (bold, headings, bullet lists, links) instead of a plain box. Anything
pasted in is automatically **cleaned of unsafe code**, so a copy-paste from Word
or a website can't introduce a security problem. Project and logo images are also
automatically resized to the right dimensions for the page they appear on.

### 9. You can now edit the site's wording without a developer
Text that used to be locked inside the code — the footer line, and the little
description snippets Google shows under each page — can now be edited from the
admin area. Your existing wording was carried over exactly, so nothing looks
different until you choose to change it.

### 10. Removed an unused, empty feature
An empty "blog" placeholder that was never used has been removed to keep the
project clean.

---

## Looking ahead — Phase 2 (planned, not yet built)

A separate planning document (`PHASE_2.md`) outlines two future projects:
- **An Arabic (right-to-left) version of the site** for the Saudi/GCC market.
- **An internal tool to track construction tenders** and their deadlines.

These are scoped and ready to discuss — nothing has been built yet, so you can
decide priorities and budget first.

---

## One thing the developer needs from you / your host

Before the next deployment, three settings for the live file storage need to be
added to the server's secure configuration (your developer knows where):
`AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`, and `AWS_S3_CUSTOM_DOMAIN`.

*(Technical note for the developer: the automated test suite passes in full, but
the local database user lacks permission to create the temporary test database on
this machine. Grant `CREATEDB` to the `pioneer` role — `ALTER ROLE pioneer
CREATEDB;` as a database superuser — to run the suite against PostgreSQL. It has
been verified passing 26/26 against an equivalent database.)*

---

# Phase 2B — Internal Tender Management Tool (developer changelog)

Staff-only tender/bid pipeline with a versioned, private document store. **No
public exposure** — everything lives under `/internal/` and is gated behind
login + `is_staff`.

## Highlights
- **Custom user model** (`core.User`, email login, UUID `public_id`) swapped in
  for Django's default `auth.User`, with a new `TimeStampedUUIDModel` base.
  *The database was reset as part of this swap (approved), so re-create your
  superuser: `python manage.py createsuperuser`.*
- **Staff authentication via django-allauth** — email/password **and Google SSO**.
  Registration is disabled; Google only signs in staff an admin has already
  created (locked-down adapters in `apps/core/adapters.py`).
- **Cloudflare R2** (not AWS S3) for confidential tender documents — a *private*
  bucket serving short-lived **signed URLs**, kept separate from public media.
- **Uploads never block the request**: the browser POSTs multipart → the file is
  staged locally → a **Celery** task moves it to R2, sniffs its MIME type
  (python-magic), records its size, and supersedes prior revisions. One code path
  works on the local filesystem (dev/test) and R2 (prod).
- **State-machine** tender status (`draft → submitted → won/lost/withdrawn`, reset
  to draft) with atomic, row-locked transitions and `simple_history` audit trail.
- Email notifications to assignees on status change via **SES + Celery**.

## Files added
- `apps/tenders/` — `models.py`, `views.py`, `urls.py`, `admin.py`, `tasks.py`,
  `forms.py`, `storage.py`, `apps.py`, `migrations/0001_initial.py`
- `apps/core/adapters.py` — allauth account/social adapters
- `apps/core/migrations/0006_user.py`, `0007_default_site.py`
- `templates/account/login.html` — branded staff login (email + Google)
- `templates/tenders/…` — `list.html`, `detail.html`, `form.html`, partials
  (`_tender_list`, `_status_block`, `_status_badge`, `_document_row`),
  `email/status_change.txt`
- `static/js/tenders.js` — vanilla-JS assignee search + upload-form reset
  (Alpine.js avoided: the site's strict CSP forbids the `unsafe-eval` it needs)
- `tests/tenders/` — factories + pytest coverage (reference generation, illegal
  transition → `PermissionDenied`, upload 202/400 paths, supersede task, access
  control)

## Files changed
- `config/settings/base.py` — `AUTH_USER_MODEL`, allauth apps/middleware/backends,
  `django.contrib.sites` + `humanize`, R2 `tender_documents` storage alias,
  upload limits, `LOGIN_URL`
- `config/settings/production.py` — private **R2** storage for `tender_documents`
- `config/urls.py` — mount `allauth.urls` and `apps.tenders.urls` (`/internal/`)
- `apps/core/models.py`, `apps/core/admin.py` — custom `User`, manager, `UserAdmin`
- `pyproject.toml` / `uv.lock` — `django-allauth`, `python-magic`

## New environment variables (production)
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — Google OAuth for staff SSO
- `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_ACCESS_KEY_SECRET`/`R2_SECRET_ACCESS_KEY`,
  `R2_TENDER_BUCKET_NAME` — private Cloudflare R2 bucket for tender documents
- `SITE_DOMAIN`, `SITE_NAME` — canonical host for `sitemap.xml` (sites framework)

## Deployment notes
- Web and Celery worker must share the `TENDER_UPLOAD_STAGING_DIR` volume
  (single-node / shared mount) so staged uploads reach the worker.
- `python-magic` requires the system `libmagic` library (present on the build host).

---

# Phase 2C — Realtime, AI, Analytics & Transactional Email (developer changelog)

Layered onto the staff tender tool (all features are staff-internal; clients
receive outbound email only — no client login/portal).

## Highlights
- **SMTP2GO** is now the transactional email provider in production (allauth
  **mandatory** email verification, a welcome/invite email on staff creation,
  and warm client "we're on it" / status-update emails). Local dev still uses
  the console backend. New staff created in the admin get an allauth
  verification email + a branded welcome (best-effort, never blocks the save).
- **Local DeepSeek 7B AI** (on-prem, OpenAI-compatible endpoint — Ollama by
  default) powering four features, each degrading gracefully when unconfigured:
  document summarisation (Celery, after upload), client-email drafting, a tender
  Q&A assistant grounded in the tender + document summaries, and description
  drafting on the form. **Runs entirely on-prem for data privacy — no tender or
  client data is sent to any third-party AI provider.**
- **Ably realtime**: per-tender live chat (append-only `TenderMessage`, fanned
  out server-side via Celery) and staff toast notifications on status changes,
  new documents, and new messages. Browsers authenticate with short-lived,
  capability-scoped tokens from a staff-gated endpoint. Chat bodies are rendered
  as `textContent` on the client (XSS-safe).
- **Analytics dashboard** (`/internal/dashboard/`) with self-hosted **Chart.js**
  (status doughnut, sector-value bar) and **Plotly** (created-over-time line).
  Only server-**aggregated** figures reach the browser — never raw rows or PII —
  passed via `json_script` (auto-escaped).
- **CSP stays strict on the public site.** The extra allowances the tools need —
  `connect-src` for Ably WebSockets, and `'unsafe-eval'` for Plotly — are scoped
  to the specific `/internal/` views via per-view `csp_update`, so the marketing
  site's hardened policy is untouched.
- **Production runs on Oracle Cloud (OCI)** compute behind an OCI load balancer;
  added `SECURE_PROXY_SSL_HEADER` for TLS-terminating proxy awareness. Tender
  documents remain on Cloudflare R2.

## Files added
- `apps/core/ai.py` (Gemini), `apps/core/realtime.py` (Ably), `apps/core/tasks.py`
  (welcome + realtime-publish tasks)
- `apps/tenders/` — `TenderMessage` model; dashboard, Ably-token, chat-message,
  and AI (draft-description / draft-email / ask) views; summary + client-email
  Celery tasks; migrations `0002`–`0003`
- `templates/tenders/dashboard.html`, `partials/_message.html`,
  `templates/core/email/welcome.txt`, `templates/tenders/email/client_ack.txt`,
  `client_status.txt`
- `static/js/dashboard.js`; self-hosted `static/js/{chart.umd.min.js,plotly.min.js,ably.min.js}`
- `tests/tenders/test_2c.py` (dashboard, AI endpoints, chat, token, client email)

## Files changed
- `apps/tenders/{views,urls,tasks,admin,models,forms}.py`, `templates/tenders/{detail,list,form}.html`,
  `static/js/tenders.js` (AI + realtime), `config/settings/{base,production}.py`,
  `apps/core/admin.py` (verification + welcome on user creation)
- `pyproject.toml` / `uv.lock` — `ably`, `httpx`, `pypdf`

## New environment variables (production)
- `SMTP2GO_USERNAME`, `SMTP2GO_PASSWORD` (and optional `SMTP2GO_HOST`/`SMTP2GO_PORT`)
- `DEEPSEEK_BASE_URL` (default `http://localhost:11434/v1`), optional
  `DEEPSEEK_MODEL` (default `deepseek-r1:7b`), `DEEPSEEK_API_KEY`, `DEEPSEEK_TIMEOUT`
- `ABLY_API_KEY`
- `SEND_CLIENT_EMAILS` (default true; set false to mute client emails)

## Notes
- AI runs on a **locally hosted DeepSeek 7B** model (OpenAI-compatible endpoint,
  Ollama/vLLM/LM Studio) for data privacy — the earlier cloud Gemini integration
  was removed. The AI layer is isolated in `apps/core/ai.py`, so the endpoint/model
  is a settings change. R1 `<think>…</think>` blocks are stripped from replies.
- **All AI runs in Celery, never the request path (ADR-002, accepted).** The
  interactive endpoints (Q&A / client-email / description) enqueue a durable,
  pollable `AIJob` and return `202` + a poll URL; the browser polls until the job
  is `ready`/`failed`. This keeps a slow local model off the WSGI workers, so it
  can never degrade the public marketing site. Jobs are visible in the admin, and
  polling is scoped to the requesting user.
- Ably chat fan-out runs through Celery (keeping the request non-blocking), so
  live delivery latency tracks worker throughput.

---

# Phase 3A — Rebrand to London Summit Consultancy Limited (developer changelog)

Full rebrand from "Pioneer Consultants" to **London Summit Consultancy
Limited** (legal name) / **London Summit Consultancy** (brand). Positioning:
UK/London consultancy serving clients across the Gulf (`areaServed: "Saudi
Arabia"` retained in JSON-LD).

## Highlights
- **Data migrations, not edits**: `core/0008` (brand_name default),
  `core/0009_rebrand_site_copy` (reversible `RunPython` — swaps SiteSettings
  copy only where it still equals the exact 0005 literals, renames the
  `sites.Site`, clears the `site_settings` cache). Applied migrations were
  never touched.
- **Tender references now use the full legal name** —
  `London Summit Consultancy Limited-2026-001`. `Tender.reference` widened
  20 → 60 chars (`tenders/0007`, non-destructive AlterField). Legacy `PCL-…`
  rows are unaffected: the year-prefix query isolates new-format references.
- Templates: all `|default:"Pioneer Consultants"` fallbacks, titles, JSON-LD,
  nav monogram (`P` → `LS`), footer, body copy ("West Midlands" → London/Gulf
  framing); email subjects + signatures (inquiries, welcome, tender client/
  status emails).
- Theme storage key `pcl-theme` → `lsc-theme` with a read-fallback so visitors
  keep their chosen theme; `window.PCLMotion` → `window.LSMotion`;
  `Celery("london_summit")`; package names in `package.json`/`pyproject.toml`.
- Admin header/title, allauth subject prefix, AI email-drafting prompt, test
  factories (`@londonsummit.test`) all rebranded.

## Action needed
- `.env.example` could not be modified from this environment — update the
  `INQUIRY_NOTIFICATION_EMAIL` / `DEFAULT_FROM_EMAIL` placeholders to the
  new `@londonsummit.co.uk` addresses manually (and the real values in
  production `.env`).

---

# Phase 3B — Procedural whole-site experience (developer changelog)

An award-grade, fully procedural Three.js + Anime.js experience: **one
persistent sculpture** that evolves through seven chapters (Spark → Discovery
→ Design Thinking → Refinement → Visualization → Human Experience → Impact)
as the homepage scroll film, with an ambient resting variant of the same
sculpture on every other page's hero. No textures, models, videos or external
assets — everything is generated from seeded code.

## Architecture
- **Build**: esbuild bundles `assets/js/experience/main.js` → self-hosted IIFE
  `static/js/experience.min.js` (`npm run js:build` / `js:watch`, checked in
  like `main.css`). three ^0.182, animejs ^4. Production CSP is untouched:
  no workers, no CDN, no inline JS, no data-URI loads (FXAA instead of SMAA
  for exactly that reason).
- **One sculpture, seven states**: particles (CPU spring-morph between
  precomputed per-state target buffers with per-particle stagger), a two-layer
  line network (outgoing state retracts while the incoming draws itself),
  instanced masses/glass/windows/trees with fixed slot ordering — the chapter-3
  exploded massing study *is* the tower of chapters 4-7; context slabs grow
  into the chapter-7 district. Nothing resets, everything transforms.
- **Rendering**: ACES tone mapping, procedural RoomEnvironment PMREM env map,
  UnrealBloom + FXAA via EffectComposer (tiered), `onBeforeCompile` triplanar
  noise + fresnel rim on one shared physical material, shader ground with a
  radially-revealed engineering grid, emissive instanced windows (index-ordered
  so the night cascade climbs floor by floor).
- **Scroll**: critically damped (τ≈0.12s) progress from the 1000vh track;
  equal 1/7 chapter ranges; env + morph blend eased inside each chapter;
  continuous CatmullRom camera (two keys per chapter — a single unbroken shot);
  anime.js only for discrete chapter-entry copy accents. Cursor feeds a
  particle attractor + camera parallax; strength decays when idle.
- **Progressive enhancement**: chapter copy is server-rendered
  (`[data-chapter]`); no JS / no WebGL2 / `prefers-reduced-motion` → the page
  renders as a stacked narrative with chapter 1 as the conventional hero. The
  engine flips `html[data-experience-on]` only after it has booted.
- **Quality tiers**: high (DPR≤1.75, bloom+FXAA, 12k particles), medium
  (DPR 1.25, bloom, 7k), low (DPR 1, no composer, 4k); ambient mode always
  runs one tier lower, composer off, transparent canvas.

## Files added
- `assets/js/experience/` — `main.js`, `core/{quality,renderer,scroll,camera,
  pointer,overlay,journey}.js`, `sculpture/{sculpture,particles,lines,
  instances,ground}.js`, `sculpture/states/{composition,curves,spark,discovery,
  thinking,refinement,visualization,human,impact,index}.js`,
  `materials/materials.js`, `utils/maths.js`, `ambient/ambient.js`
- `static/js/experience.min.js` (bundled artifact)
- `tests/test_home.py` — journey mount, 7 chapters, rebrand assertions,
  ambient mounts per page/variant

## Files changed
- `templates/core/home.html` — rewritten as the 7-chapter journey (sticky
  stage + fallback narrative), followed by the retained conventional sections
  (stats, services, stakeholders, sectors, portfolio, testimonials, CTA)
- `templates/{core/about,services/landing,services/detail,portfolio/list,
  portfolio/detail,inquiries/contact}.html` — ambient motif mounts
  (`data-experience="ambient"` + per-page `data-variant`) + bundle include
- `assets/css/input.css` — experience layer (fallback narrative styles,
  engine-on film styles, ambient canvas), rebuilt `static/css/main.css`
- `package.json` — three/animejs/esbuild devDeps + `js:build`/`js:watch`

## Deployment notes
- Run `python manage.py migrate` (core 0008/0009 + tenders 0007) and
  `collectstatic` (new `experience.min.js`, updated `main.css`).
- No CSP changes required.
