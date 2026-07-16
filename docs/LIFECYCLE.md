# Pioneer Consultants Limited — Product Lifecycle

**Version**: 2.0 | **Date**: 2026-06-28 | **Author**: Alex (PM)
**Status**: Sprint 5 of 8 complete — Sprint 6 starting

---

## North Star Metric

**Qualified Inquiry Conversion Rate** — the percentage of form submissions that advance to `qualified` status within 14 days of receipt.

| Metric | Baseline | Target (Month 3) | Current |
|---|---|---|---|
| Qualified inquiry rate | 0% (nothing live) | ≥ 30% | — |
| Monthly inquiry submissions | 0 | ≥ 15 | — |
| Portfolio entries published | 0 | ≥ 8 | 0 (DB seeded; content pending from PCL) |
| Google-indexed pages | 0 | 100% of published pages | — |
| Time-to-email on inquiry | — | < 5 min (automated) | Built; untested in prod |

---

## Phase Overview

| Phase | Name | Status | Weeks | Key Deliverable |
|---|---|---|---|---|
| Phase 1 | Foundation | ✅ Complete | 1 | Django scaffold, settings, Celery, URL routing |
| Phase 2 | Core CMS Shell | ✅ Complete | 2 | SiteSettings singleton, context processor, base.html |
| Phase 3 | Services Catalog | ✅ Complete | 2 | 19 services seeded, buyer-type tabs, HTMX filter |
| Phase 4 | Portfolio Showcase | ✅ Complete | 3 | Project model, HTMX filter, admin publish/unpublish |
| Phase 5 | Lead Capture | ✅ Complete | 3 | Inquiry form, state machine, Celery emails |
| Phase 6 | SEO & i18n | 🔄 In Progress | 4 | Sitemap, per-page meta, JSON-LD, RTL architecture |
| Phase 7 | Frontend Polish | ⬜ Not Started | 5 | All Tailwind templates built and mobile-tested |
| Phase 8 | Tests & CI | ⬜ Not Started | 6 | pytest suite, ruff, pre-commit, staging deploy |
| Phase 9 | Launch | ⬜ Not Started | 7 | SES production, domain live, GSC submitted |

---

## Phase Detail

### Phase 1 — Foundation ✅

**What shipped**: `pyproject.toml` with all deps, `uv sync`-ready environment, `config/settings/` three-way split (base/local/production), `local.py` sets env defaults so no `.env` is needed in dev, Celery wired to Redis, root URL config with all app namespaces, `/robots.txt`.

**Key decisions locked**:
- `uv` only — no pip
- `HtmxMiddleware` in MIDDLEWARE stack
- `FIXTURE_DIRS = [BASE_DIR / "fixtures"]` so root-level fixtures are found
- `os.environ.setdefault()` in `local.py` before importing base — avoids `.env` requirement in dev

---

### Phase 2 — Core CMS Shell ✅

**What shipped**: `SiteSettings` singleton (pk always 1), `HeroSection`, `AboutSection`, `Testimonial`; Redis-cached context processor (`site` in every template, 1hr TTL, signal-cleared on save); `base.html` with HTMX loaded, CSRF injected via `hx-headers` on `<body>`.

**Critical design decisions**:
- Tailwind served self-hosted via `npm run css:build` — CDN removed (SRI compliance)
- CSRF token method: `hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'` on `<body>`, not a JS listener

**Known gap (GAP-4)**: Context processor uses `objects.first()` not `SiteSettings.load()` — `site` can be `None` on a fresh DB. Fix before launch.

---

### Phase 3 — Services Catalog ✅

**What shipped**: `BuyerType` TextChoices, `ServiceCategory`, `Service` with `get_absolute_url()`, SEO meta fallback via `effective_meta_title`/`effective_meta_desc` properties; `services_seed.json` fixture with all 3 categories + 19 services; `ServicesLandingView` with HTMX buyer-type tab pattern; `ServiceDetailView` with related projects.

---

### Phase 4 — Portfolio Showcase ✅

**What shipped**: `Project` with `HistoricalRecords`, `ProjectImage`, `Sector` TextChoices; `PortfolioListView` with combined sector + service slug filter; `ProjectDetailView` serving only published records (404 on unpublished); admin with `publish_selected`/`unpublish_selected` bulk actions.

**Known gap (GAP-3)**: Bulk publish via `queryset.update()` bypasses `simple_history` — no audit trail for bulk operations. Acceptable for v1; document for PCL team.

---

### Phase 5 — Lead Capture ✅

**What shipped**: `Inquiry` model with 5-state machine (`new → contacted → qualified → won/lost`), `transition_to()` guard, honeypot `website` field; `InquiryCreateView` with rate limiting (5 POST/hr/IP via Redis), HTMX swap on success/error, 422 on validation failure; `InquiryValidateView` for per-field blur validation; two Celery tasks (staff notification + visitor acknowledgement), both bind=True, max_retries=3, 60s delay.

**Known gaps**:
- **GAP-1 (High)**: `InquiryAdmin.save_model()` calls `inquiry.save()` directly — bypasses `transition_to()`. Admin operators can set any status without going through the state machine. Fix before launch.
- **GAP-2 (Medium)**: No try/except around `inquiry.save()` or `send_inquiry_notification.delay()`. If Redis is down at the moment of save, the inquiry is persisted but emails are never sent. Fix before launch.

---

### Phase 6 — SEO & i18n 🔄 (Tasks 23–26)

**Remaining work**:

| Task | Description | Status |
|---|---|---|
| 23 | Sitemaps: `ServiceSitemap`, `ProjectSitemap`, `StaticSitemap` | ⬜ |
| 24 | Per-page SEO meta: `page_title` + `page_meta_desc` context vars, OG tags | ⬜ |
| 25 | JSON-LD `LocalBusiness` block in `base.html` | ⬜ |
| 26 | RTL/i18n: `USE_I18N`, `LANGUAGES`, `LOCALE_PATHS`, `dir` attribute on `<html>` | ⬜ |

---

### Phase 7 — Frontend Polish ⬜ (Tasks 27–30)

**Remaining work**:

| Task | Description | Depends on |
|---|---|---|
| 27 | `templates/core/home.html` — hero, featured services (3), featured portfolio (4), testimonials | Phase 6 meta |
| 28 | `templates/services/landing.html`, `detail.html`, `partials/_service_list.html` | — |
| 29 | `templates/portfolio/list.html`, `detail.html`, `partials/_project_cards.html` | — |
| 30 | `templates/core/about.html`, `core/privacy.html` | — |

**Non-negotiable UI requirements**:
- All layouts use logical CSS properties (`padding-inline-start` not `padding-left`) for RTL readiness
- Every image carries explicit `width` and `height` attributes (CLS prevention)
- `loading="lazy"` on all non-LCP images
- Hamburger menu via vanilla JS — no Alpine, no extra deps

---

### Phase 8 — Tests & CI ⬜ (Tasks 31–34)

| Task | Description |
|---|---|
| 31 | `pytest.ini`, `tests/conftest.py` with factories |
| 32 | Inquiry tests (state machine, form, HTMX, honeypot, rate limit) |
| 33 | Portfolio + services tests (filter, partial, 404 on unpublished) |
| 34 | `ruff check` + `ruff format` in `pyproject.toml`, `.pre-commit-config.yaml` |

---

### Phase 9 — Launch ⬜

**Prerequisites** (all must be green before production deploy):

| Gate | Owner | Status |
|---|---|---|
| Domain decision confirmed | Eng. Mohammed Bashir | ⬜ |
| Logo / brand assets provided | PCL | ⬜ |
| SES production access requested and granted | Eng | ⬜ |
| ≥ 8 portfolio project briefs submitted by PCL | PCL | ⬜ |
| Contact details (email, phone) confirmed | PCL | ⬜ |
| GAP-1 (admin bypass) fixed | Eng | ⬜ |
| GAP-4 (context processor None) fixed | Eng | ⬜ |
| `python manage.py check --deploy` passes (production settings) | Eng | ⬜ |
| SES email delivery confirmed on staging | Eng | ⬜ |
| Mobile + JS-disabled smoke test passed | Eng + PCL | ⬜ |
| Sitemap submitted to Google Search Console | Eng | ⬜ |

**Rollback criteria**: If SES delivery fails in production and cannot be resolved within 2 hours → revert email backend to SMTP fallback and redeploy. If inquiry form errors exceed 1% → revert to previous deploy.

---

## What We're Not Building in v1 (and Why)

| Request | Reason | Revisit condition |
|---|---|---|
| Client portal / project status dashboard | No validated demand yet; needs 10 paying clients first | When first 3 clients explicitly ask for it |
| Arabic locale content | Architecture is ready; PCL needs to supply translated copy | When PCL confirms Arabic-speaking target market and provides copy |
| Blog / insights section | `apps.blog` is scaffolded; activating trivial once content strategy is confirmed | When PCL confirms blog ownership (who writes posts, how often) |
| E-commerce / payment | All services are bespoke-quoted; no fixed SKUs exist | When at least one repeatable fixed-price service is defined |
| JavaScript framework | HTMX + server-rendered templates cover all interaction requirements at this scale | When client portal requires component-level state |
| Live chat | Adds third-party JS weight; email + form sufficient at < 50 inquiries/month | When inquiry volume exceeds 50/month and < 24h SLA is missed |
| CAPTCHA | Honeypot + ratelimit cover current risk; CAPTCHA adds UX friction | When spam volume exceeds 50/day after launch |

---

## v2 Roadmap (Month 2–4)

| Initiative | Hypothesis | Confidence | Signal needed |
|---|---|---|---|
| Arabic (AR) locale | GCC visitors convert better in Arabic | Medium | PCL confirms GCC market and provides translated copy |
| Blog / Insights | Thought leadership drives organic SEO | Medium | PCL commits to publishing cadence (2+ posts/month) |
| HTMX inquiry pipeline dashboard | Team wants pipeline visibility in-app, not just Django admin | High | Confirmed by Eng. Mohammed Bashir after using admin for 30 days |
| Client portal (read-only project status) | Reduces PM email load | Low | 3+ clients explicitly request it |

---

## Known Technical Debt (to address before v2)

| Debt | File | Priority | Fix |
|---|---|---|---|
| GAP-1: Admin bypasses state machine | `apps/inquiries/admin.py` | High | Override `save_model()` to call `transition_to()` |
| GAP-2: No error handling on task enqueue | `apps/inquiries/views.py` | Medium | Wrap `inquiry.save()` + `.delay()` in try/except |
| GAP-3: Bulk publish skips history | `apps/portfolio/admin.py` | Low | Iterate + `.save()` per instance, or document trade-off |
| GAP-4: Context processor `objects.first()` | `apps/core/context_processors.py` | Low | Replace with `SiteSettings.load()` |
| No EMAIL_TIMEOUT in settings | `config/settings/base.py` | Low | Add `EMAIL_TIMEOUT = 30` to prevent hung SMTP connections |
| No sitemap caching | `apps/core/sitemaps.py` | Low | Wrap sitemap view with `cache_page(86400)` |
