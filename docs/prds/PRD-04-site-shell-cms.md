# PRD-04: Site Shell & Content Management System

**Status**: Approved — Built (v1 complete; templates pending in Phase 7)
**Author**: Alex (PM) | **Last Updated**: 2026-06-28 | **Version**: 1.0
**Stakeholders**: Eng. Mohammed Bashir (PCL), Backend Engineer
**Workflow spec**: `docs/workflows/WORKFLOW-site-settings-cache.md`

---

## 1. Problem Statement

PCL needs to own their content. An agency or engineer should not be needed to update a phone number, change the hero headline, or publish a testimonial. Operationally, PCL must be self-sufficient from day one — every content change that requires engineering involvement is a drag on momentum and creates a single point of failure.

**Evidence**:
- PCL founder explicitly stated zero Django admin experience — the interface must be intuitive enough to use without training documentation
- Contact details, tagline, and social links are expected to change as the business evolves; these cannot require code deploys

---

## 2. Goals & Success Metrics

| Goal | Metric | Baseline | Target | Window |
|---|---|---|---|---|
| Content autonomy | % of content edits done by PCL without Eng | 0% | 100% | 30 days post-launch |
| CMS confidence | Time for Mohammed Bashir to publish a new portfolio project | — | < 15 min | First use |
| Page load performance | LCP on homepage | — | < 2.5 s | Launch |
| Site settings cache efficiency | % of requests served from Redis cache vs DB | — | > 95% (within 1hr of cold start) | Ongoing |

---

## 3. Non-Goals

- No custom user roles in v1 — all admin users have full Django staff access
- No visual page builder — Django admin is the CMS; no Wagtail/CMS framework
- No draft/preview workflow for content — publish is immediate (except portfolio `is_published` flag)
- No version history on SiteSettings / HeroSection — only `Project` has `HistoricalRecords`

---

## 4. User Personas & Stories

### Primary — Eng. Mohammed Bashir (PCL Operator)

**Story 1**: As the PCL operator, I want to update the company phone number and email address once, and have it reflect everywhere on the site.

**Acceptance Criteria**:
- [x] Given I update `SiteSettings.phone` and `SiteSettings.email` in admin and click Save, the footer and contact page reflect the new values on the next page load
- [x] Given I save SiteSettings, the Redis cache is invalidated immediately — no stale data shown to the next visitor

**Story 2**: As the PCL operator, I want to change the hero headline and CTA without touching code.

**Acceptance Criteria**:
- [x] `HeroSection` is editable in admin with a rich text body and an optional background image
- [x] Multiple hero sections can exist, but only the one with `is_active=True` renders (or the first, if none are explicitly set)

**Story 3**: As the PCL operator, I want to add, edit, or reorder client testimonials without Eng involvement.

**Acceptance Criteria**:
- [x] `Testimonial` records are editable in admin with `display_order` for manual ordering
- [x] Testimonials with `is_visible=False` are hidden from the homepage

**Story 4**: As a visitor to the site, I want every page to load the correct site name, favicon, and contact details so the site feels like a complete, professional business.

**Acceptance Criteria**:
- [x] `{{ site.brand_name }}` renders correctly in the nav, footer, and `<title>` across all pages
- [x] `{{ site.email }}` and `{{ site.phone }}` render in the footer
- [x] `{{ site.logo.url }}` renders in the nav (with fallback if no logo uploaded)
- [ ] **PENDING FIX (GAP-4)**: If no SiteSettings row exists, `site` must not be `None` — use `SiteSettings.load()` in context processor

---

## 5. Solution Overview

The site shell is the `core` app — it provides the global `SiteSettings` singleton, page-level models (`HeroSection`, `AboutSection`, `Testimonial`), and a Redis-cached Django context processor that injects the `site` variable into every template.

`base.html` is the single template that all pages extend. It provides the `<head>`, nav, footer, HTMX `<script>`, CSRF `hx-headers`, and Tailwind `<link>`. Page-specific templates only need to fill the `{% block content %}`, `{% block title %}`, and `{% block meta_desc %}` blocks.

**SiteSettings is a singleton**: The model's `save()` method always sets `pk=1`. The admin hides the "Add" button once a row exists. `SiteSettings.load()` uses `get_or_create(pk=1)` and is safe to call at any time, including on a fresh database.

**Redis cache**: The context processor caches the `SiteSettings` instance in Redis (`key = "site_settings"`, TTL = 3600 s). When an operator saves SiteSettings, a `post_save` signal calls `cache.delete("site_settings")` synchronously, so the next request fetches fresh data.

---

## 6. Technical Considerations

### Singleton Pattern

```python
class SiteSettings(models.Model):
    def save(self, *args, **kwargs) -> None:
        self.pk = 1          # always pk=1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "SiteSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
```

### Context Processor

```python
# apps/core/context_processors.py
def site_settings(request) -> dict:
    site = cache.get("site_settings")
    if site is None:
        site = SiteSettings.objects.first()   # ← GAP-4: should be SiteSettings.load()
        cache.set("site_settings", site, 3600)
    return {"site": site}
```

**GAP-4 fix** (one line):
```python
site = SiteSettings.load()   # replaces objects.first()
```

### Template Inheritance

```
base.html
├── core/home.html
├── core/about.html
├── core/privacy.html
├── services/landing.html
├── services/detail.html
├── portfolio/list.html
├── portfolio/detail.html
├── inquiries/contact.html
└── inquiries/sent.html

partials/              ← no <html> wrapper; HTMX fragments only
├── _project_cards.html
├── _service_list.html
├── _inquiry_form.html
├── _inquiry_success.html
└── _field_error.html
```

### HTMX CSRF

CSRF token is injected once on the `<body>` tag in `base.html`:

```html
<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
```

All HTMX POST requests to this domain automatically carry the `X-CSRFToken` header. No JavaScript listener required.

### Cache Flow

```
Request arrives
  → context_processor called
  → cache.get("site_settings")
    → HIT: return cached SiteSettings (< 1 ms)
    → MISS: SiteSettings.load() from DB → cache.set(TTL=3600)
Admin saves SiteSettings
  → post_save signal fires
  → cache.delete("site_settings")
  → next request: cache MISS → fresh DB read
```

### Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `site` is None on fresh DB | Low (production starts with seeded data) | Medium | GAP-4 fix: use SiteSettings.load() |
| Redis down | Low | Low | Graceful degradation — DB read on every request |
| Logo/favicon not uploaded at launch | Medium | Low | Template guard: `{% if site.logo %}` |

---

## 7. Launch Checklist

- [ ] GAP-4 fixed: context processor uses `SiteSettings.load()` not `objects.first()`
- [ ] `SiteSettings` populated in admin: brand name, email, phone, address, meta_description
- [ ] `HeroSection` record created with headline, CTA, and background image
- [ ] `AboutSection` record created
- [ ] At least 2 `Testimonial` records added with `is_visible=True`
- [ ] `EMAIL_TIMEOUT = 30` added to `base.py` (see technical debt in LIFECYCLE.md)

---

## 8. Appendix

- Workflow spec: `docs/workflows/WORKFLOW-site-settings-cache.md`
- Admin customisation: `apps/core/admin.py`
