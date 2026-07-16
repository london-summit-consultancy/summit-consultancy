# Pioneer Consultants — Phase 2 Planning

> **Status: planning document only.** Nothing in this file has been built. It
> scopes the two Phase 2 workstreams so they can be estimated, sequenced, and
> approved before any code is written. Phase 1 (production hardening) is
> complete; this builds on that foundation.

---

## Phase 2A — Arabic / RTL Bilingual Site

### Why

The business is repositioning toward the Saudi/GCC market (already reflected in
the JSON-LD `areaServed: "Saudi Arabia"`). Arabic-speaking clients, contractors,
and government tender committees expect a first-class Arabic experience — not a
machine-translated afterthought. Arabic is right-to-left, which touches layout,
typography, and every directional CSS value on the site.

### What already exists (Phase 1 groundwork)

- `USE_I18N = True`, `LocaleMiddleware` installed, `LANGUAGES = [("en", …), ("ar", …)]`,
  and `LOCALE_PATHS = [BASE_DIR / "locale"]` are already configured.
- Editorial copy now lives in `SiteSettings` (Action 9), so translatable content
  is centralised rather than hardcoded in templates.

### Scope

1. **URL i18n**
   - Wrap `config/urls.py` public routes in `i18n_patterns(...)` so Arabic is
     served under `/ar/…` and English under the default prefix (or `/en/…`).
   - Keep `/admin/`, `/robots.txt`, and webhook/inquiry POST endpoints **outside**
     `i18n_patterns` — they must not gain a language prefix.
   - Add a `set_language` redirect view + a language switcher in the nav/footer.

2. **String extraction & translation**
   - Mark every template literal with `{% translate %}` / `{% blocktranslate %}`
     and every Python string with `gettext_lazy`.
   - `makemessages -l ar`, hand off `locale/ar/LC_MESSAGES/django.po` for
     professional translation (not machine), then `compilemessages`.
   - Decide policy for **model content** (project titles, service descriptions,
     About body): the current models are single-language. Two options:
     - **(a)** `django-modeltranslation` / `django-parler` — per-field Arabic
       columns, admin renders both languages side by side. Cleaner content model;
       adds a dependency and a migration per translated model.
     - **(b)** Duplicate nullable `*_ar` fields on each model. No dependency, more
       template branching. Not recommended beyond a handful of fields.
   - **Recommendation:** `django-modeltranslation` for `Service`, `ServiceCategory`,
     `Project`, `AboutSection`, `HeroSection`, and the `SiteSettings` copy fields.

3. **RTL layout & typography**
   - Audit the Tailwind v4 layer: replace physical properties (`ml-*`, `pr-*`,
     `left-*`, `text-left`) with **logical** equivalents (`ms-*`, `pe-*`,
     `start-*`, `text-start`). Tailwind v4 supports logical utilities natively.
   - Set `dir="rtl"` and `lang="ar"` on `<html>` when the active language is
     Arabic (drive from `{{ LANGUAGE_CODE }}` / `get_language`).
   - Add an Arabic UI font (e.g. self-hosted **IBM Plex Sans Arabic** or **Cairo**)
     as a `woff2` alongside the existing self-hosted Latin fonts, wired through an
     `@font-face` + a `[lang="ar"]` font-family override in `assets/css/input.css`.
     Playfair Display has no Arabic coverage — Arabic headings need a display face.
   - Mirror directional iconography (chevrons, the lightbox prev/next arrows in
     `portfolio/detail.html`, the mobile-nav slide direction).

4. **Formatting & content**
   - Numbers/dates: rely on Django's `l10n` with `USE_I18N`; verify Arabic-Indic
     numeral preference with the client (often Western numerals are preferred in
     KSA business contexts — confirm, don't assume).
   - Localise the JSON-LD `name`/`description` per active language.
   - Confirm the contact form (`apps/inquiries`) accepts and stores Arabic input
     (already UTF-8/Postgres-safe) and that notification emails render RTL.

### Explicit non-goals for 2A

- No auto-translation. Arabic copy is professionally translated and reviewed.
- No currency conversion engine (this is a marketing site, not commerce).

### Risks / decisions to confirm before building

- **Content translation library choice** (modeltranslation vs. parler) — migration
  and admin-UX implications differ.
- **Numeral convention** (Western vs. Arabic-Indic) — client preference.
- **Arabic display font licensing** for self-hosting.

---

## Phase 2B — Internal Tender / Bid Management Tool

### Why

Pioneer responds to construction tenders. Today that pipeline lives in
spreadsheets and email. An internal tool would track each tender opportunity from
discovery through submission to award/loss, with documents and deadlines in one
place. This is **staff-only**, behind authentication — a different audience and
trust boundary from the public marketing site.

### Architecture stance

- **Separate concern, same project or new service?** Recommend a **new Django app**
  (`apps.tenders`) inside this project initially — it reuses auth, admin, Celery,
  SES, and deployment. If it grows into a multi-user product with its own SLAs,
  extract later. Do **not** expose any of it through the public URLconf.
- **Access control:** staff-only. Gate every view with `LoginRequiredMixin` +
  a group/permission check (`PermissionRequiredMixin`). No anonymous access, no
  inclusion in `sitemap`/`robots`.

### Data model (state-machine driven, per engineering standards)

- `Tender`
  - `reference`, `title`, `client_name`, `sector` (reuse `portfolio.Sector`),
    `estimated_value` (Decimal), `currency` (default SAR), `source`.
  - `status` — **`TextChoices` state machine**, not booleans:
    `IDENTIFIED → QUALIFYING → BID_NO_BID → PREPARING → SUBMITTED →`
    `(AWARDED | LOST | WITHDRAWN)`. Explicit `_ALLOWED_TRANSITIONS` map +
    a `transition_to()` method, mirroring the existing `Inquiry` pattern so the
    admin/save path stays atomic (`transaction.atomic` + `select_for_update`).
  - Key dates: `published_at`, `questions_deadline`, `submission_deadline`,
    `decision_expected_at`.
- `TenderDocument` — FK to `Tender`, `file` (S3 via the Phase 1 `STORAGES`
  default), `kind` (RFP, addendum, our-submission, correspondence), `uploaded_by`,
  `uploaded_at`. Append-only; never overwrite an uploaded document.
- `TenderEvent` — immutable audit log of status transitions and note entries
  (who, when, from→to). Append-only, consistent with the "money/state is
  append-only" standard.
- `TenderTask` — checklist items with `assignee`, `due_at`, `done_at`.

### Workflow / async

- **Deadline reminders** via **Celery Beat**: a periodic task scans upcoming
  `submission_deadline`/`questions_deadline` and enqueues SES reminder emails
  (T-7, T-2, T-1 days). Never send inline in a request.
- **No third-party call blocks a request** — email, document virus-scan hooks,
  and any export generation run as Celery tasks.
- Idempotent reminders (store `last_reminder_sent_stage`) so a re-run of Beat
  cannot double-send.

### UI

- Server-rendered Django templates + **HTMX** for the board/list interactions
  (status changes, inline task toggles) — consistent with the marketing site's
  stack; no SPA. Alpine.js for local UI state.
- A kanban-style board grouped by `status`, plus a per-tender detail page with
  documents, timeline (`TenderEvent`), and tasks.

### Reporting

- Win-rate and pipeline-value rollups derived from `TenderEvent`/`status`
  (computed, never stored as denormalised counters).

### Explicit non-goals for 2B

- Not a public feature — zero exposure on the marketing site.
- No e-signature or payment integration in the first cut.
- No document collaboration/versioning beyond append-only uploads.

### Risks / decisions to confirm before building

- **Auth model:** Django admin-only, or a bespoke staff UI? (Recommend bespoke
  read/write views for daily use; admin as a fallback.)
- **Document storage bucket:** same S3 bucket as public media, or a separate
  private bucket with stricter ACLs? (Recommend separate private bucket — tender
  documents are confidential and must never be world-readable.)
- **Multi-user scale / notifications channel:** email only, or also in-app?

---

## Suggested sequencing

1. **2A first** if the immediate goal is winning GCC clients through the public
   site (marketing/SEO value, customer-facing).
2. **2B first** if the internal bottleneck (losing track of tender deadlines) is
   the more urgent business pain.

These are independent; either can ship without the other.
