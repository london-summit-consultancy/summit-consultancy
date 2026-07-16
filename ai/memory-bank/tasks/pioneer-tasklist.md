# Pioneer Consultants Limited — Development Task List

## Specification Summary
**Original Requirements**: Construction consultancy marketing site with portfolio showcase, service catalog (19 services, 3 buyer types), and structured lead capture with email notifications.
**Technical Stack**: Python 3.12+ / Django 5.1+ / HTMX 2.x / Tailwind CSS v4 / PostgreSQL / Redis / Celery / Amazon SES / S3
**Target Timeline**: 6 weeks to staging-ready

---

## Sprint 1 — Project Foundation (Week 1)

### [x] Task 1: Initialise project with uv
**Description**: Create pyproject.toml, install dependencies, create .env.example and .gitignore.
**Acceptance Criteria**:
- `uv sync` installs all deps without errors
- `.env.example` documents every required env var
- `.gitignore` excludes `.env`, `media/`, `staticfiles/`, `__pycache__/`

**Files**: `pyproject.toml`, `.env.example`, `.gitignore`
**Reference**: Section 6 Dependencies

---

### [x] Task 2: Django settings layout
**Description**: Create `config/settings/` split (base / local / production). Base uses django-environ.
**Acceptance Criteria**:
- `DJANGO_SETTINGS_MODULE=config.settings.local python manage.py check` returns no errors
- `HtmxMiddleware` is in `MIDDLEWARE`
- Tailwind CDN, HTMX loaded from base.html not settings
- `CELERY_BROKER_URL` reads from env

**Files**: `config/settings/base.py`, `config/settings/local.py`, `config/settings/production.py`
**Reference**: Section 5.9

---

### [x] Task 3: Celery configuration
**Description**: Wire Celery to Django settings with Redis broker. `app.autodiscover_tasks()` for inquiries.
**Acceptance Criteria**:
- `celery -A config worker` starts without errors
- Tasks from `apps.inquiries.tasks` are discovered

**Files**: `config/celery.py`, `config/__init__.py`

---

### [x] Task 4: Root URL configuration + robots.txt
**Description**: Wire all app namespaces into `config/urls.py`. Add robots.txt view that blocks /admin/.
**Acceptance Criteria**:
- All namespaced URL patterns resolve correctly
- `/robots.txt` returns 200 with `Disallow: /admin/`
- `/sitemap.xml` returns 200 (empty is fine before content exists)

**Files**: `config/urls.py`, `apps/core/sitemaps.py`

---

## Sprint 2 — Core App + CMS Shell (Week 2)

### [x] Task 5: `core` app models
**Description**: `SiteSettings` (singleton), `HeroSection`, `AboutSection`, `Testimonial`. Singleton pattern enforces `pk=1` on save. `post_save` signal clears Redis cache.
**Acceptance Criteria**:
- `python manage.py makemigrations core` produces a clean migration
- `SiteSettings.load()` returns the singleton, creating it if absent
- Saving SiteSettings clears the `site_settings` cache key

**Files**: `apps/core/models.py`
**Reference**: Section 5.3

---

### [x] Task 6: `core` admin
**Description**: Register all 4 core models. SiteSettings admin: no add button (singleton), redirects changelist to edit. AboutSection admin: same singleton guard.
**Acceptance Criteria**:
- Visiting `/admin/core/sitesettings/` redirects to the edit page (not a list)
- Cannot add a second SiteSettings
- Testimonial list has inline `display_order` edit

**Files**: `apps/core/admin.py`

---

### [x] Task 7: `core` context processor
**Description**: `site_settings` context processor injects `site` variable into every template. Redis-cached for 1 hour. Cache cleared by signal on SiteSettings save.
**Acceptance Criteria**:
- `{{ site.brand_name }}` renders in any template without additional view code
- Cache miss fetches from DB; subsequent requests serve from cache

**Files**: `apps/core/context_processors.py`

---

### [x] Task 8: `base.html` template
**Description**: Full page shell with sticky nav (PCL brand, desktop + mobile), footer (3 columns: brand, links, contact), HTMX loaded (pinned version), CSRF token injected via `hx-headers` attribute on `<body>`.
**Acceptance Criteria**:
- All HTMX POST requests include `X-CSRFToken` header automatically
- Mobile hamburger menu opens/closes with vanilla JS (no Alpine)
- `{% block title %}`, `{% block content %}`, `{% block extra_js %}` slots defined
- OG tags rendered per-page via block variables

**Files**: `templates/base.html`
**Reference**: Section 5.7

---

## Sprint 3 — Services App (Week 2)

### [x] Task 9: `services` app models
**Description**: `BuyerType` TextChoices, `ServiceCategory`, `Service` with slug, is_featured, display_order, meta fields. `get_absolute_url()` on Service.
**Acceptance Criteria**:
- `python manage.py makemigrations services` clean
- `Service.objects.filter(is_featured=True)` works
- Ordering: `['category__display_order', 'display_order']`

**Files**: `apps/services/models.py`

---

### [x] Task 10: `services` admin
**Description**: `ServiceCategoryAdmin` with `ServiceInline`. `ServiceAdmin` with `SimpleHistoryAdmin`, prepopulated slug, fieldsets.
**Acceptance Criteria**:
- Adding a Service from the Category inline works
- Slug auto-populates from name in admin
- `list_editable` includes `is_featured` and `display_order`

**Files**: `apps/services/admin.py`

---

### [x] Task 11: `services` views + HTMX tab partial
**Description**: `ServicesLandingView` returns full page or `partials/_service_list.html` partial when `request.htmx` is truthy. `ServiceDetailView` with prefetch on `projects`.
**Acceptance Criteria**:
- `GET /services/?buyer=contractor` with `HX-Request: true` header returns only the service list fragment
- Same URL without the header returns the full page
- No N+1: single query fetches all services per category

**Files**: `apps/services/views.py`, `apps/services/urls.py`

---

### [x] Task 12: Services seed fixture
**Description**: JSON fixture with all 3 ServiceCategory records and 19 Service records. `python manage.py loaddata services_seed` runs without errors.
**Acceptance Criteria**:
- All 19 services load with correct category assignments
- 3 services marked `is_featured=True` (BIM Modelling, Structural Design, 3D Visualisation)
- Each service has a non-empty `short_desc`

**Files**: `fixtures/services_seed.json`

---

## Sprint 4 — Portfolio App (Week 3)

### [x] Task 13: `portfolio` app models
**Description**: `Sector` TextChoices, `Project` (with `HistoricalRecords`), `ProjectImage`. M2M to services, `get_absolute_url()`.
**Acceptance Criteria**:
- `python manage.py makemigrations portfolio` clean
- `Project.objects.filter(is_published=True).prefetch_related('services_used', 'images')` — no N+1

**Files**: `apps/portfolio/models.py`

---

### [x] Task 14: `portfolio` admin
**Description**: `ProjectAdmin` with `ProjectImageInline`, `publish_selected` / `unpublish_selected` actions, `filter_horizontal` for services_used.
**Acceptance Criteria**:
- Bulk publish/unpublish actions appear in admin actions dropdown
- Image inline allows adding multiple images with drag-to-reorder via `display_order`
- History tab visible on project change page (SimpleHistoryAdmin)

**Files**: `apps/portfolio/admin.py`

---

### [x] Task 15: `portfolio` views + HTMX filter
**Description**: `PortfolioListView` filters by `?sector=` and `?service=`. Returns `_project_cards.html` partial on HTMX request with `hx-push-url="true"`. `ProjectDetailView` with prefetch on `images` and `services_used`.
**Acceptance Criteria**:
- Filtering by sector via HTMX does not reload the page
- Browser URL updates to `/portfolio/?sector=construction` after filter
- JS-disabled fallback: same URL returns a full page with the same filter applied

**Files**: `apps/portfolio/views.py`, `apps/portfolio/urls.py`

---

### [x] Task 16: Portfolio templates
**Description**: `portfolio/list.html` with filter bar and `#project-grid` target. `portfolio/detail.html` with image gallery (vanilla JS lightbox — open/close/prev/next). `_project_cards.html` partial renders the grid only.
**Acceptance Criteria**:
- Filter tabs send HTMX requests; `#project-grid` swaps content without page reload
- Gallery lightbox works keyboard-accessible (Escape closes)
- "No projects found" empty state renders when queryset is empty

**Files**: `templates/portfolio/list.html`, `templates/portfolio/detail.html`, `templates/partials/_project_cards.html`

---

## Sprint 5 — Inquiries App (Week 3)

### [x] Task 17: `inquiries` app models + state machine
**Description**: `InquiryStatus` TextChoices, `Inquiry` model with `transition_to()` that enforces valid transitions. Honeypot `website` field. Module-level `_ALLOWED_TRANSITIONS` dict.
**Acceptance Criteria**:
- `inquiry.transition_to('contacted')` from 'new' succeeds and saves
- `inquiry.transition_to('won')` from 'new' raises `ValueError`
- `website` field exists and is not rendered in the visible form

**Files**: `apps/inquiries/models.py`

---

### [x] Task 18: `InquiryForm` 
**Description**: ModelForm with all user-facing fields. `website` uses `HiddenInput`. Tailwind-friendly widget attrs.
**Acceptance Criteria**:
- Form renders without the website field visible to users
- `project_desc` textarea renders with 5 rows
- All required fields validated correctly

**Files**: `apps/inquiries/forms.py`

---

### [x] Task 19: `inquiries` views (HTMX form swap + field validation)
**Description**: `InquiryCreateView` — on success: returns `_inquiry_success.html` (HTMX) or redirects (plain POST). On error: returns `_inquiry_form.html` with status 422. `InquiryValidateView` — per-field blur validation. `@ratelimit` decorator (5/h per IP) on POST.
**Acceptance Criteria**:
- Submitting valid form via HTMX: form div swaps to success message (no page reload)
- Submitting invalid form via HTMX: form re-renders in place with field errors (status 422)
- Honeypot filled: silently discards without saving to DB
- More than 5 submissions/hour from same IP: 429 response

**Files**: `apps/inquiries/views.py`, `apps/inquiries/urls.py`

---

### [x] Task 20: Celery tasks for email
**Description**: Two tasks — `send_inquiry_notification` (to PCL team) and `send_inquiry_acknowledgement` (to submitter). Both use `render_to_string` for email bodies. Max 3 retries, 60s delay.
**Acceptance Criteria**:
- Tasks are imported by `app.autodiscover_tasks()`
- Missing `Inquiry.pk` raises no error (early return)
- Retries on `smtplib.SMTPException` (test with `self.retry()`)

**Files**: `apps/inquiries/tasks.py`, `templates/inquiries/email/notification.txt`, `templates/inquiries/email/acknowledgement.txt`

---

### [x] Task 21: `inquiries` admin
**Description**: `InquiryAdmin` with colour-coded status badge, date hierarchy, search, readonly metadata fields. Status field saves via `transition_to()` — not raw field edit.
**Acceptance Criteria**:
- Status badge shows colour per state in list view
- `source_page`, `ip_address`, `website`, `created_at` are read-only
- Bulk transition actions available for common moves

**Files**: `apps/inquiries/admin.py`

---

### [x] Task 22: Inquiry templates
**Description**: `_inquiry_form.html` partial with `hx-post`, `hx-target`, `hx-swap` and spinner. `_inquiry_success.html` partial with thank-you message. `contact.html` full page wrapping the form partial. `sent.html` non-HTMX fallback success page. Per-field `hx-post="/contact/validate/"` on blur.
**Acceptance Criteria**:
- Spinner shows during HTMX request and hides on response
- Each field triggers blur validation pointing to `next .field-error`
- Page works correctly with JS disabled (normal POST to `/contact/`)

**Files**: `templates/inquiries/contact.html`, `templates/partials/_inquiry_form.html`, `templates/partials/_inquiry_success.html`, `templates/inquiries/sent.html`

---

## Sprint 6 — SEO, RTL, Polish (Week 4)

### [ ] Task 23: Sitemaps
**Description**: `ServiceSitemap`, `ProjectSitemap`, `StaticSitemap`. Wire into `config/urls.py`. Celery beat task to regenerate daily.
**Acceptance Criteria**:
- `/sitemap.xml` returns valid XML listing all published projects and all services
- Static pages (home, about, services, portfolio, contact) appear with correct `priority`

**Files**: `apps/core/sitemaps.py`

---

### [ ] Task 24: Per-page SEO meta
**Description**: Every view passes `page_title` and `page_meta_desc` to context. Base template uses these with fallback chain to `site.meta_description`. OG image fallback to site logo.
**Acceptance Criteria**:
- `/services/bim-modelling/` has `<title>BIM Modelling | Pioneer Consultants</title>`
- `<meta name="description">` uses service's `meta_desc` or `short_desc`
- OG tags populated on all pages

**Reference**: Section 5.8

---

### [ ] Task 25: JSON-LD LocalBusiness structured data
**Description**: Add `LocalBusiness` JSON-LD block in `base.html` using `site` context variable.
**Acceptance Criteria**:
- Google Rich Results Test validates the output
- Uses `site.email`, `site.phone`, `site.address`

**Files**: `templates/base.html` (addition)

---

### [ ] Task 26: RTL/i18n architecture
**Description**: `USE_I18N = True`, `LANGUAGES = [('en', 'English'), ('ar', 'العربية')]`, `LOCALE_PATHS`. Base template: `<html lang="{% get_current_language %}" dir="{% if LANGUAGE_CODE == 'ar' %}rtl{% else %}ltr{% endif %}">`.
**Acceptance Criteria**:
- `python manage.py makemessages -l ar` runs without errors
- Switching to AR locale via URL doesn't break layout (logical CSS properties used in custom styles)

---

## Sprint 7 — Frontend Polish (Week 5)

### [ ] Task 27: Homepage template
**Description**: Hero section (full-width, overlaid headline + CTA), 3 featured service cards, 4 featured portfolio cards, testimonials carousel, final CTA band.
**Acceptance Criteria**:
- Renders correctly on mobile (375px) and desktop (1280px)
- All content pulled from DB — no hardcoded copy
- Hero renders even if `HeroSection` is None (fallback text)

**Files**: `templates/core/home.html`

---

### [ ] Task 28: Services page templates
**Description**: `services/landing.html` with buyer-type tab bar and `#service-list` HTMX target. `services/detail.html` with service body, related projects grid, and inline contact CTA. `partials/_service_list.html` renders the filtered category + service cards.
**Acceptance Criteria**:
- Clicking a buyer-type tab swaps service list without page reload
- Active tab is visually highlighted based on `selected_buyer`
- Service detail page: "Related Projects" section hidden if no related projects exist

**Files**: `templates/services/landing.html`, `templates/services/detail.html`, `templates/partials/_service_list.html`

---

### [ ] Task 29: Portfolio page templates
**Acceptance Criteria**: See Task 16 (done in Sprint 4)

---

### [ ] Task 30: About + Privacy + static pages
**Description**: `core/about.html` with about section and image. `core/privacy.html` basic privacy policy layout.
**Acceptance Criteria**:
- About renders even if `AboutSection` is None
- Privacy page is readable and linked from footer

**Files**: `templates/core/about.html`, `templates/core/privacy.html`

---

## Sprint 8 — Tests & CI (Week 6)

### [ ] Task 31: pytest configuration
**Description**: `pytest.ini` / `pyproject.toml` section with `DJANGO_SETTINGS_MODULE=config.settings.local`. `conftest.py` with model factories.
**Acceptance Criteria**:
- `uv run pytest` runs the full test suite without errors

**Files**: `pytest.ini`, `tests/conftest.py`

---

### [ ] Task 32: Inquiry tests
**Description**: Test `InquiryForm` validation, `transition_to()` state machine (valid and invalid transitions), `InquiryCreateView` (HTMX + plain POST, honeypot discard, rate limit), `InquiryValidateView`.
**Acceptance Criteria**:
- All happy paths + failure paths covered
- Celery tasks tested with `@override_settings(CELERY_TASK_ALWAYS_EAGER=True)` or mocked
- State machine `ValueError` tested for all illegal transitions

**Files**: `tests/test_inquiries.py`

---

### [ ] Task 33: Portfolio + Services tests
**Description**: Test `PortfolioListView` filtering (sector + service slug), HTMX partial response, `ProjectDetailView` 404 on unpublished, `ServicesLandingView` buyer-type filter.
**Acceptance Criteria**:
- Filter by `?sector=construction` returns only construction projects
- HTMX request (with `HX-Request` header) returns partial template, not full page
- Unpublished project returns 404

**Files**: `tests/test_portfolio.py`, `tests/test_services.py`

---

### [ ] Task 34: ruff + pre-commit
**Description**: Configure `ruff` in `pyproject.toml`. Add `.pre-commit-config.yaml` with ruff check + ruff format hooks.
**Acceptance Criteria**:
- `uv run ruff check .` passes on all project Python files
- `pre-commit run --all-files` passes

**Files**: `pyproject.toml` (ruff section), `.pre-commit-config.yaml`

---

## Quality Checklist

- [ ] All HTMX POSTs include `X-CSRFToken` (via `hx-headers` on `<body>`)
- [ ] Every list view uses `select_related`/`prefetch_related` — no N+1
- [ ] Inquiry state transitions go through `transition_to()` only — no raw status writes
- [ ] Both Celery tasks are fire-and-forget (view never awaits them)
- [ ] Honeypot field is hidden from users but present in the DOM
- [ ] All HTMX interactions degrade gracefully without JavaScript
- [ ] `ruff check` and `ruff format` pass on all files
- [ ] No secrets in source — all credentials via `.env`
- [ ] `python manage.py check --deploy` passes (production settings)
- [ ] Media storage: `MEDIA_ROOT` for local, S3 for production

## Technical Notes
**Development Stack**: Django 5.1+, HTMX 2.x, Tailwind CSS v4 (CDN for dev, standalone CLI for prod), PostgreSQL, Redis, Celery
**No background process commands** — assume `python manage.py runserver`, `celery worker`, and Redis are already running
**Images**: Use real project images from PCL — no placeholder images in production
**Domain**: Pending decision from Eng. Mohammed Bashir (see Open Questions in spec)
