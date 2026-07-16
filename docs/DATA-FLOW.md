# Backend → Template Data Flow

**Version**: 1.0 | **Date**: 2026-06-28 | **Author**: Alex (PM)
**Audience**: Engineers implementing templates (Phase 7)

This document maps every Django view to the exact context variables it passes to templates, explains the template inheritance chain, and documents every HTMX interaction including what triggers a partial vs. a full-page render.

---

## 1. Global Context (All Pages)

The `site_settings` context processor runs on every request. Its output is merged into every template's context automatically.

```python
# Injected by: apps/core/context_processors.py
# Cache key: "site_settings" (Redis, TTL 3600 s)
# Source: SiteSettings.objects.first() (→ fix to SiteSettings.load() per GAP-4)

context["site"] = SiteSettings instance | None
```

**Available in every template as `{{ site }}`**:

| Variable | Type | Usage |
|---|---|---|
| `site.brand_name` | str | `<title>`, nav logo text, footer |
| `site.tagline` | str | Hero fallback, meta subtitle |
| `site.email` | str | Footer, contact page |
| `site.phone` | str | Footer, contact page |
| `site.address` | str | Footer, JSON-LD LocalBusiness |
| `site.linkedin_url` | str | Footer social links |
| `site.instagram_url` | str | Footer social links |
| `site.logo` | ImageFieldFile | Nav logo `<img>` |
| `site.favicon` | ImageFieldFile | `<link rel="icon">` in `<head>` |
| `site.meta_description` | str | Global meta fallback in `<head>` |

**Guard pattern required**:
```html
{% if site %}{{ site.brand_name }}{% else %}Pioneer Consultants{% endif %}
```

---

## 2. Template Inheritance Chain

```
base.html                 ← every page extends this
│
├── Blocks available:
│   ├── {% block title %}      ← default: "{{ site.brand_name }}"
│   ├── {% block meta_desc %}  ← default: "{{ site.meta_description }}"
│   ├── {% block og_image %}   ← default: "{{ site.logo.url }}"
│   ├── {% block canonical %}  ← default: empty
│   ├── {% block content %}    ← required — page body
│   └── {% block extra_js %}   ← optional — page-specific scripts
│
├── Always rendered:
│   ├── <head> with Tailwind CSS link, HTMX script (defer), favicon
│   ├── <body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'> 
│   ├── <nav> — sticky; brand name + desktop links + mobile hamburger
│   ├── <footer> — 3 columns: brand+tagline, nav links, contact details
│   └── JSON-LD <script type="application/ld+json"> (Task 25)
│
└── Partials (no base.html; HTMX fragments only)
    ├── partials/_project_cards.html
    ├── partials/_service_list.html
    ├── partials/_inquiry_form.html
    ├── partials/_inquiry_success.html
    └── partials/_field_error.html
```

---

## 3. View-by-View Context Map

### 3.1 `GET /` — HomeView

**View**: `apps/core/views.HomeView` (TemplateView)
**Template**: `templates/core/home.html`
**Extends**: `base.html`

```python
context = {
    # From context processor (always present):
    "site": SiteSettings,

    # From get_context_data():
    "hero":        HeroSection | None,           # .filter(is_active=True).first()
    "featured_services": QuerySet[Service],      # .filter(is_featured=True)[:3]
                                                 #   .select_related("category")
    "featured_projects": QuerySet[Project],      # .filter(is_published=True, is_featured=True)[:4]
                                                 #   .prefetch_related("services_used")
    "testimonials": QuerySet[Testimonial],       # .filter(is_visible=True).order_by("display_order")
}
```

**Template guards required**:

```html
<!-- Hero: may be None if no HeroSection record exists -->
{% if hero %}
  <h1>{{ hero.headline }}</h1>
  <p>{{ hero.subheadline }}</p>
  <a href="{{ hero.cta_url }}">{{ hero.cta_label }}</a>
{% else %}
  <h1>Pioneer Consultants Limited</h1>
  <p>{{ site.tagline }}</p>
{% endif %}

<!-- Featured services: renders nothing if no is_featured=True services -->
{% for service in featured_services %}...{% empty %}...{% endfor %}

<!-- Featured projects: renders nothing if no published + featured projects -->
{% for project in featured_projects %}...{% empty %}...{% endfor %}

<!-- Testimonials: renders nothing if all are is_visible=False -->
{% for t in testimonials %}...{% empty %}...{% endfor %}
```

---

### 3.2 `GET /about/` — AboutView

**View**: `apps/core/views.AboutView` (TemplateView)
**Template**: `templates/core/about.html`

```python
context = {
    "site": SiteSettings,
    "about": AboutSection | None,    # .first()
    "page_title":    "About Us",
    "page_meta_desc": "About Pioneer Consultants Limited — ...",
}
```

**Template guard**:
```html
{% if about %}
  <h2>{{ about.headline }}</h2>
  {{ about.body|safe }}
  {% if about.image %}<img src="{{ about.image.url }}" ...>{% endif %}
{% else %}
  <p>About section coming soon.</p>
{% endif %}
```

---

### 3.3 `GET /services/` — ServicesLandingView

**View**: `apps/services/views.ServicesLandingView` (TemplateView)
**Template (full page)**: `templates/services/landing.html`
**Template (HTMX partial)**: `templates/partials/_service_list.html`

```python
context = {
    "site": SiteSettings,
    "categories":      QuerySet[ServiceCategory],  # filtered by ?buyer= if set
                                                   # .prefetch_related("services")
                                                   # .order_by("display_order")
    "selected_buyer":  str,                        # "client" | "contractor" | "consultancy" | ""
    "all_categories":  QuerySet[ServiceCategory],  # UNFILTERED — always all 3
                                                   # used to render the tab bar
    "page_title":      "Our Services",
    "page_meta_desc":  "...",
}
```

**HTMX pattern**:
```
GET /services/                    → full page: services/landing.html
GET /services/?buyer=contractor   → full page (no HTMX header)
GET /services/?buyer=contractor   → partial: _service_list.html (HX-Request: true)
  │                                  swaps: #service-list innerHTML
  └── hx-target="#service-list"
      hx-swap="innerHTML"
      hx-push-url="true"
```

**In `services/landing.html`**:
```html
<!-- Tab bar — uses all_categories (always all 3) -->
{% for cat in all_categories %}
  <button hx-get="/services/?buyer={{ cat.buyer_type }}"
          hx-target="#service-list"
          hx-swap="innerHTML"
          hx-push-url="true"
          class="{% if selected_buyer == cat.buyer_type %}tab-active{% endif %}">
    {{ cat.get_buyer_type_display }}
  </button>
{% endfor %}

<div id="service-list">
  {% include "partials/_service_list.html" %}
</div>
```

**In `_service_list.html`** (receives same context):
```html
<!-- Iterates filtered categories -->
{% for category in categories %}
  <h2>{{ category.headline }}</h2>
  {% for service in category.services.all %}
    <a href="{{ service.get_absolute_url }}">{{ service.name }}</a>
    <p>{{ service.short_desc }}</p>
  {% endfor %}
{% empty %}
  <p>No services found for this buyer type.</p>
{% endfor %}
```

---

### 3.4 `GET /services/<slug>/` — ServiceDetailView

**View**: `apps/services/views.ServiceDetailView` (DetailView)
**Template**: `templates/services/detail.html`

```python
context = {
    "site": SiteSettings,
    "object":            Service,             # select_related("category")
                                              # prefetch_related("projects")
    "related_projects":  QuerySet[Project],   # .filter(is_published=True).order_by("-year")[:4]
    "page_title":        service.effective_meta_title,   # meta_title or service.name
    "page_meta_desc":    service.effective_meta_desc,    # meta_desc or description[:160]
}
```

**Template must use**:
```html
<title>{% block title %}{{ page_title }} — {{ site.brand_name }}{% endblock %}</title>
<meta name="description" content="{% block meta_desc %}{{ page_meta_desc }}{% endblock %}">

{{ object.name }}        {# service name #}
{{ object.short_desc }}  {# card summary #}
{{ object.body|safe }}   {# rich text body from prose editor #}

{% if related_projects %}
  <!-- related projects grid -->
{% endif %}
```

---

### 3.5 `GET /portfolio/` — PortfolioListView

**View**: `apps/portfolio/views.PortfolioListView` (TemplateView)
**Template (full page)**: `templates/portfolio/list.html`
**Template (HTMX partial)**: `templates/partials/_project_cards.html`

```python
context = {
    "site": SiteSettings,
    "projects":          QuerySet[Project],       # filter(is_published=True)
                                                  # optionally filtered by ?sector= and/or ?service=
                                                  # .prefetch_related("services_used")
                                                  # .order_by("-year", "display_order")
    "sectors":           list[tuple],             # Sector.choices → [("infrastructure", "Infrastructure"), ...]
    "services":          QuerySet[Service],        # Service.objects.order_by("name") — for service filter
    "selected_sector":   str,                     # "infrastructure" | "construction" | ""
    "selected_service":  str,                     # service slug | ""
    "page_title":        "Portfolio",
    "page_meta_desc":    "...",
}
```

**HTMX pattern**:
```
GET /portfolio/                          → full page: portfolio/list.html
GET /portfolio/?sector=construction      → full page (no HTMX)
GET /portfolio/?sector=construction      → partial: _project_cards.html (HX-Request: true)
  │                                         swaps: #project-grid innerHTML
  └── hx-target="#project-grid"
      hx-swap="innerHTML"
      hx-push-url="true"
```

**In `portfolio/list.html`**:
```html
<!-- Sector filter tabs -->
{% for value, label in sectors %}
  <a href="/portfolio/?sector={{ value }}"
     hx-get="/portfolio/?sector={{ value }}"
     hx-target="#project-grid"
     hx-swap="innerHTML"
     hx-push-url="true"
     class="{% if selected_sector == value %}tab-active{% endif %}">
    {{ label }}
  </a>
{% endfor %}

<!-- Service filter dropdown (or links) -->
{% for service in services %}
  <a href="/portfolio/?service={{ service.slug }}"
     hx-get="/portfolio/?service={{ service.slug }}"
     hx-target="#project-grid"
     hx-swap="innerHTML"
     hx-push-url="true">
    {{ service.name }}
  </a>
{% endfor %}

<div id="project-grid">
  {% include "partials/_project_cards.html" %}
</div>
```

**In `_project_cards.html`** (receives same full context):
```html
{% for project in projects %}
  <a href="{{ project.get_absolute_url }}">
    <img src="{{ project.cover_image.url }}" alt="{{ project.title }}"
         width="600" height="400" loading="lazy">
    <h3>{{ project.title }}</h3>
    <p>{{ project.sector }} — {{ project.year }}</p>
    <p>{{ project.summary }}</p>
  </a>
{% empty %}
  <p>No projects found for this filter.</p>
{% endfor %}
```

---

### 3.6 `GET /portfolio/<slug>/` — ProjectDetailView

**View**: `apps/portfolio/views.ProjectDetailView` (DetailView)
**Template**: `templates/portfolio/detail.html`

```python
context = {
    "site": SiteSettings,
    "object":       Project,              # filter(is_published=True)
                                          # prefetch_related("images", "services_used")
    "related":      QuerySet[Project],    # same sector, excl. self, published, [:3]
    "page_title":   project.title,
    "page_meta_desc": project.summary,
}
```

**Gallery (vanilla JS only)**:
```html
<!-- Images loop — data already in DOM; no HTMX needed -->
<div id="gallery">
  {% for img in object.images.all %}
    <img src="{{ img.image.url }}" alt="{{ img.caption }}"
         data-gallery-index="{{ forloop.counter0 }}"
         loading="lazy">
  {% endfor %}
</div>

<!-- Lightbox overlay — controlled by 30-line vanilla JS in {% block extra_js %} -->
<div id="lightbox" hidden>
  <img id="lightbox-img">
  <button id="prev">‹</button>
  <button id="next">›</button>
  <button id="close">✕</button>
</div>
```

---

### 3.7 `GET /contact/` — InquiryCreateView

**View**: `apps/inquiries/views.InquiryCreateView` (CreateView)
**Template**: `templates/inquiries/contact.html`

```python
context = {
    "site": SiteSettings,
    "form":     InquiryForm,              # unbound on GET
    "services": QuerySet[Service],        # .select_related("category")
                                          # .order_by("category__display_order", "display_order")
                                          # for the service dropdown in the form
    "page_title": "Contact Us",
    "page_meta_desc": "...",
}
```

**Form behaviour matrix**:

| Request type | Form state | Response | Status | Template |
|---|---|---|---|---|
| GET | Unbound | Full page | 200 | `inquiries/contact.html` |
| POST (HTMX) valid | — | Success partial | 200 | `partials/_inquiry_success.html` |
| POST (HTMX) invalid | Bound + errors | Form partial | 422 | `partials/_inquiry_form.html` |
| POST (HTMX) honeypot | — | Success partial (silent discard) | 200 | `partials/_inquiry_success.html` |
| POST (plain) valid | — | Redirect | 302 | → `/contact/sent/` |
| POST (plain) invalid | Bound + errors | Full page | 200 | `inquiries/contact.html` |

**In `inquiries/contact.html`**:
```html
<div id="contact-form">
  {% include "partials/_inquiry_form.html" %}
</div>
```

**In `partials/_inquiry_form.html`**:
```html
<form hx-post="{% url 'inquiries:contact' %}"
      hx-target="#contact-form"
      hx-swap="outerHTML"
      hx-indicator="#form-spinner"
      method="post"
      action="{% url 'inquiries:contact' %}">

  {% csrf_token %}

  <!-- full_name -->
  {{ form.full_name }}
  <span class="field-error">{{ form.full_name.errors.0 }}</span>

  <!-- email with blur validation -->
  <input name="email" value="{{ form.email.value|default:'' }}"
         hx-post="{% url 'inquiries:validate' %}"
         hx-trigger="blur"
         hx-target="next .field-error"
         hx-swap="innerHTML">
  <span class="field-error">{{ form.email.errors.0 }}</span>

  <!-- ... other fields ... -->

  <!-- honeypot — hidden from humans -->
  {{ form.website }}   {# renders as <input type="hidden" name="website"> #}

  <button type="submit">Send Message</button>
  <span id="form-spinner" class="htmx-indicator">Sending…</span>
</form>
```

**In `partials/_inquiry_success.html`**:
```html
<!-- No context variables needed; static content only -->
<div class="success-message">
  <h2>Message Sent</h2>
  <p>Thank you — we'll be in touch within one business day.</p>
</div>
```

---

### 3.8 `POST /contact/validate/` — InquiryValidateView

**View**: `apps/inquiries/views.InquiryValidateView` (View)
**Response**: Plain text `HttpResponse` — no template

```python
# Returns: HttpResponse(error_string)
# error_string == ""  → field is valid, HTMX clears the error span
# error_string != ""  → field is invalid, HTMX swaps into "next .field-error"
```

**Trigger and target**:
```html
<input name="email"
       hx-post="{% url 'inquiries:validate' %}"
       hx-trigger="blur"
       hx-target="next .field-error"
       hx-swap="innerHTML"
       hx-include="[name='email']">
<span class="field-error"></span>
```

HTMX swaps the response text into the `<span class="field-error">` immediately after the input. Empty response clears any existing error.

---

### 3.9 `GET /contact/sent/` — InquirySuccessView

**View**: `apps/inquiries/views.InquirySuccessView` (TemplateView)
**Template**: `templates/inquiries/sent.html`

```python
context = {
    "site": SiteSettings,
    "page_title": "Message Sent",
}
```

Non-HTMX fallback only. Users who have JS disabled are redirected here after successful form submission. Renders a full page confirming the message was received.

---

## 4. HTMX Request/Response Summary

| Trigger | Endpoint | Header | View | Response | Status | Swaps into |
|---|---|---|---|---|---|---|
| Sector tab click | `GET /portfolio/?sector=X` | HX-Request | PortfolioListView | `_project_cards.html` | 200 | `#project-grid` |
| Service filter click | `GET /portfolio/?service=Y` | HX-Request | PortfolioListView | `_project_cards.html` | 200 | `#project-grid` |
| Buyer tab click | `GET /services/?buyer=X` | HX-Request | ServicesLandingView | `_service_list.html` | 200 | `#service-list` |
| Form submit (valid) | `POST /contact/` | HX-Request | InquiryCreateView | `_inquiry_success.html` | 200 | `#contact-form` (outerHTML) |
| Form submit (invalid) | `POST /contact/` | HX-Request | InquiryCreateView | `_inquiry_form.html` | 422 | `#contact-form` (outerHTML) |
| Form submit (honeypot) | `POST /contact/` | HX-Request | InquiryCreateView | `_inquiry_success.html` | 200 | `#contact-form` (outerHTML) |
| Field blur | `POST /contact/validate/` | HX-Request | InquiryValidateView | `""` or error string | 200 | `next .field-error` |

---

## 5. N+1 Prevention Reference

| View | Relation | Fix |
|---|---|---|
| `HomeView` | `featured_projects → services_used` | `prefetch_related("services_used")` |
| `HomeView` | Testimonials | Single query, no relations |
| `ServicesLandingView` | `category → services` | `prefetch_related("services")` |
| `ServiceDetailView` | `service → category` | `select_related("category")` |
| `ServiceDetailView` | `service → projects` | `prefetch_related("projects")` — then `.filter(is_published=True)[:4]` is a second query |
| `PortfolioListView` | `project → services_used` | `prefetch_related("services_used")` |
| `ProjectDetailView` | `project → images` | `prefetch_related("images")` |
| `ProjectDetailView` | `project → services_used` | `prefetch_related("services_used")` |
| `InquiryCreateView` (GET) | `service → category` | `select_related("category")` on services queryset |

---

## 6. Meta / SEO Block Usage

In `base.html`, define blocks:

```html
<title>{% block title %}{{ site.brand_name|default:"Pioneer Consultants" }}{% endblock %}</title>
<meta name="description"
      content="{% block meta_desc %}{{ site.meta_description }}{% endblock %}">
<meta property="og:title"
      content="{% block og_title %}{{ site.brand_name }}{% endblock %}">
<meta property="og:description"
      content="{% block og_desc %}{{ site.meta_description }}{% endblock %}">
<meta property="og:image"
      content="{% block og_image %}{% if site.logo %}{{ request.scheme }}://{{ request.get_host }}{{ site.logo.url }}{% endif %}{% endblock %}">
<link rel="canonical" href="{% block canonical %}{{ request.build_absolute_uri }}{% endblock %}">
```

**Per-page override pattern** (used in Service/Portfolio detail views):

```html
{% block title %}{{ page_title }} — {{ site.brand_name }}{% endblock %}
{% block meta_desc %}{{ page_meta_desc }}{% endblock %}
{% block og_title %}{{ page_title }}{% endblock %}
{% block og_desc %}{{ page_meta_desc }}{% endblock %}
{% block og_image %}{{ request.scheme }}://{{ request.get_host }}{{ object.cover_image.url }}{% endblock %}
```

---

## 7. Admin → DB → Template Data Path (End-to-End)

```
PCL operator edits content in Django admin
  │
  ├── SiteSettings saved
  │     → SiteSettings.save() forces pk=1
  │     → post_save signal: cache.delete("site_settings")
  │     → next request: context_processor → DB read → cache.set(TTL=3600)
  │     → {{ site.brand_name }} / {{ site.email }} etc. updated on next page load
  │
  ├── Service edited
  │     → Service.save() → DB UPDATE
  │     → no cache — queryset is live on every request
  │     → /services/ and /services/<slug>/ reflect changes immediately
  │
  ├── Project published (is_published toggled True)
  │     → Project.save() → DB UPDATE, HistoricalRecords entry created
  │     → no cache — PortfolioListView queryset is live
  │     → /portfolio/ shows project on next page load
  │
  ├── Project bulk published (queryset.update())
  │     → DB UPDATE (no post_save signal, no history entry — GAP-3)
  │     → /portfolio/ shows projects on next page load
  │
  └── Testimonial updated
        → Testimonial.save() → DB UPDATE
        → HomeView fetches fresh queryset on next request
        → testimonials carousel updated on next homepage load
```
