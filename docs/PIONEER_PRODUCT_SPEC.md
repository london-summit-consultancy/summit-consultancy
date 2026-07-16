# Pioneer Consultants Limited (PCL) — Django Web Application
**Product Specification & Engineering Reference**
**Status**: Approved for Development
**Author**: Alex (PM) **Last Updated**: 2026-06-27 **Version**: 1.2
**Task List**: [`ai/memory-bank/tasks/pioneer-tasklist.md`](../ai/memory-bank/tasks/pioneer-tasklist.md)
**Stack**: Python 3.12+ / Django 5.1+ / HTMX / Tailwind CSS v4 / PostgreSQL / Redis / Celery
**Serving**: West Midlands & GCC (RTL/i18n ready from day one)

---

## 1. Problem Statement

Pioneer Consultants Limited is a construction consultancy specialising in project management, quantity surveying, BIM modelling, structural engineering, and interior design. They serve three distinct buyer types — **Clients** (project owners), **Contractors**, and **Consultancies** — each with a different service profile.

**The business problem today:** No owned digital presence means PCL depends entirely on word-of-mouth in a highly competitive, geographically bounded market (West Midlands, UK). Without a credibility anchor online, every sales conversation starts from zero — there is no portfolio proof, no service clarity, and no structured lead intake pipeline.

**What this application must solve:**
- Establish institutional credibility: visitors must immediately understand who PCL is, what they do, and who they do it for.
- Convert browsers to inquiries: structured, trackable lead intake for each service/sector pairing.
- Give the team a CMS they can operate without engineering: portfolio updates, service edits, and new project case studies should never require a code deploy.
- Lay the architecture for future capability: multi-language (AR/EN), client portal, and project-status reporting are on the horizon.

**Cost of not solving it:** Every month without a web presence is a direct competitive disadvantage to firms with polished portfolios. A cold referral cannot evaluate PCL before a discovery call — they either trust the referrer blindly or go elsewhere.

---

## 2. Goals & Success Metrics

| Goal | Metric | Baseline | Target | Window |
|------|--------|----------|--------|--------|
| Establish digital credibility | Bounce rate on home | — | < 55% | 60 days post-launch |
| Generate structured leads | Inquiry form submissions / month | 0 | ≥ 15 | 90 days post-launch |
| Showcase work | Portfolio entries published | 0 | ≥ 8 | Launch day |
| Operational independence | CMS edits by team (no-code) | 0% | 100% | 30 days post-launch |
| SEO foundation | Google index coverage | 0 pages | 100% of published pages | 30 days post-launch |
| Lead response speed | Time-to-email on inquiry | — | < 5 min (automated) | Launch day |

---

## 3. Non-Goals (v1)

- **No client portal or project-status dashboard** — validated once the inquiry pipeline is proven; target v2.
- **No e-commerce or online payment** — services are bespoke/quoted; no fixed-price checkout in scope.
- **No Arabic locale at launch** — RTL/i18n architecture is built in from day one (logical CSS, translation-ready models), but Arabic content is deferred until the team can supply translated copy.
- **No blog in v1** — news/insights section is "Later" on the roadmap; CMS foundation makes it trivial to add.
- **No mobile app** — responsive web only.
- **No multi-branch / multi-company tenancy** — single-tenant for PCL. If Rivex-pineal later white-labels this, the architecture allows it without breaking changes.
- **No JavaScript framework** — HTMX handles all interactivity. No React, Vue, or SvelteKit. Vanilla JS only where HTMX cannot reach (e.g. image lightbox).

---

## 4. User Personas

### 4.1 Primary — The Project Owner (Client)
**"Sarah, the Client-Side Project Sponsor"**
A property developer, facilities manager, or public-sector procurement officer commissioning a construction or infrastructure project. She needs to verify that PCL can manage contractor procurement, act as employer's agent, and produce regular reports. She's evaluating 2–3 firms simultaneously and will shortlist based on portfolio credibility and how quickly a firm responds.

**Behaviour:** Lands on the site from a referral link or Google search. Reads the "Services for Clients" section. Looks for case studies. Hits the contact form.
**Key friction today:** No proof of past work, no clear service taxonomy, no fast response channel.

### 4.2 Secondary — The Main Contractor
**"Hassan, the Site Operations Manager"**
A contractor needing a QS to support tendering, BOQ preparation, BIM coordination, or financial reporting on a live project. Often time-pressured. Evaluates on speed, price signal, and whether PCL can speak contractor language.

**Behaviour:** Scans the "Services for Contractors" list. Looks for BIM and QS specifics. Calls or emails directly.
**Key friction today:** No visible specialist credentials or sector experience.

### 4.3 Tertiary — The Consultancy Practice
**"Yusuf, the Structural Engineer / Architect"**
A small-to-mid consultancy that needs overflow capacity: proposal development, architectural drawings, structural calculations, or detailing on a project-by-project basis.

**Behaviour:** Evaluates the "Services for Consultancies" section. Wants to see sample drawings or calculation sets in the portfolio.
**Key friction today:** No technical portfolio artefacts visible.

### 4.4 Internal — PCL Team (CMS User)
Eng. Mohammed Bashir and any delegated team member who manages content, responds to inquiries, and publishes portfolio updates. Zero Django admin experience assumed; must work from Django admin with sensible field labels and no raw-data exposure.

---

## 5. Feature Specification

### 5.1 App Architecture (Django)

```
pioneer/                  ← project root
├── config/               ← settings, urls, wsgi, asgi
├── apps/
│   ├── core/             ← home, about, static pages, SEO meta
│   ├── services/         ← service catalog, buyer-type grouping
│   ├── portfolio/        ← project case studies, sectors, gallery
│   ├── inquiries/        ← contact form, lead tracking, email dispatch
│   └── blog/             ← (scaffold only in v1; activated in v2)
├── templates/
│   ├── base.html         ← full page shell; loads HTMX + Tailwind
│   ├── partials/         ← HTMX partial responses (no <html> wrapper)
│   │   ├── _project_cards.html
│   │   ├── _service_list.html
│   │   ├── _inquiry_form.html
│   │   ├── _inquiry_success.html
│   │   └── _field_error.html
│   ├── core/
│   ├── services/
│   ├── portfolio/
│   └── inquiries/
├── static/
└── media/
```

Each app is self-contained. No cross-app foreign keys except `inquiries` → `services` (inquiry can reference a service).

**HTMX integration via `django-htmx` middleware:**
- Adds `request.htmx` to every request (truthy when `HX-Request` header is present)
- Views use `request.htmx` to decide between returning a full page or a partial template fragment
- The same URL serves both full-page loads (first visit, direct link) and HTMX swap requests — no separate API layer needed

---

### 5.2 HTMX Interaction Patterns

This section defines every HTMX interaction in the application. Each pattern maps a user action to a Django view, a target element, and a partial template.

#### Pattern 1 — Portfolio Filter (sector / service tabs)

```html
<!-- templates/portfolio/list.html -->
<div id="filter-bar">
  <a hx-get="/portfolio/?sector=infrastructure"
     hx-target="#project-grid"
     hx-push-url="true"
     hx-swap="innerHTML"
     class="filter-tab">Infrastructure</a>

  <a hx-get="/portfolio/?sector=construction"
     hx-target="#project-grid"
     hx-push-url="true"
     hx-swap="innerHTML"
     class="filter-tab">Construction</a>
</div>

<div id="project-grid">
  {% include "partials/_project_cards.html" %}
</div>
```

HTMX request → `PortfolioListView` detects `request.htmx` → returns only `_project_cards.html`.
Full-page request → returns `portfolio/list.html` with `_project_cards.html` already included.
`hx-push-url="true"` keeps the browser URL and back-button working correctly.

#### Pattern 2 — Services Buyer-Type Tabs

```html
<!-- templates/services/landing.html -->
<div id="buyer-tabs">
  {% for category in categories %}
  <button hx-get="/services/?buyer={{ category.buyer_type }}"
          hx-target="#service-list"
          hx-swap="innerHTML"
          class="tab-btn">{{ category.headline }}</button>
  {% endfor %}
</div>

<div id="service-list">
  {% include "partials/_service_list.html" %}
</div>
```

#### Pattern 3 — Contact Form: Inline Submission & Response

The form POSTs via HTMX. On success the form is swapped for a thank-you message. On error the form is re-rendered in place with field-level errors — no full page reload.

```html
<!-- templates/inquiries/contact.html -->
<div id="contact-form">
  {% include "partials/_inquiry_form.html" %}
</div>
```

```html
<!-- templates/partials/_inquiry_form.html -->
<form hx-post="/contact/"
      hx-target="#contact-form"
      hx-swap="outerHTML"
      hx-indicator="#form-spinner">

  {% csrf_token %}
  {{ form.as_div }}

  <button type="submit">Send Message</button>
  <span id="form-spinner" class="htmx-indicator">Sending…</span>
</form>
```

View response logic:
- `form.is_valid()` → save, enqueue Celery tasks → return `_inquiry_success.html` (swaps out the form)
- `form.is_invalid()` → return `_inquiry_form.html` with bound form + errors (swaps form back in-place)

#### Pattern 4 — Inline Field Validation

Real-time validation triggered on `blur` per field, without submitting the whole form.

```html
<input name="email"
       hx-post="/contact/validate/"
       hx-trigger="blur"
       hx-target="next .field-error"
       hx-swap="innerHTML"
       hx-include="[name='email']">
<span class="field-error"></span>
```

`InquiryValidateView` receives a single field name + value, runs partial form validation, returns an error string or empty string.

#### Pattern 5 — Project Image Gallery (vanilla JS only)

Gallery lightbox is the one place HTMX is not used — image data is already in the DOM, so a 30-line vanilla JS listener handles open/close/prev/next without a network request. No HTMX, no external library.

---

### 5.3 `core` App

**Purpose:** Site shell — home page, about page, privacy policy, footer, SEO meta per-page.

#### Models

```python
class SiteSettings(models.Model):
    """Singleton. One row always."""
    brand_name        = models.CharField(max_length=100)
    tagline           = models.CharField(max_length=200)
    email             = models.EmailField()
    phone             = models.CharField(max_length=30)
    address           = models.TextField()
    linkedin_url      = models.URLField(blank=True)
    instagram_url     = models.URLField(blank=True)
    logo              = models.ImageField(upload_to='brand/')
    favicon           = models.ImageField(upload_to='brand/')
    meta_description  = models.CharField(max_length=160)  # global fallback

class HeroSection(models.Model):
    """Home page hero — editable headline, subline, CTA, background image."""
    headline     = models.CharField(max_length=120)
    subheadline  = models.TextField(max_length=300)
    cta_label    = models.CharField(max_length=40)
    cta_url      = models.CharField(max_length=200)
    background   = models.ImageField(upload_to='hero/')
    is_active    = models.BooleanField(default=True)

class AboutSection(models.Model):
    """Single editable about block."""
    headline    = models.CharField(max_length=120)
    body        = models.TextField()
    image       = models.ImageField(upload_to='about/', blank=True)
    updated_at  = models.DateTimeField(auto_now=True)

class Testimonial(models.Model):
    client_name    = models.CharField(max_length=100)
    client_title   = models.CharField(max_length=100)
    quote          = models.TextField()
    is_visible     = models.BooleanField(default=True)
    display_order  = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['display_order']
```

#### Views
- `HomeView(TemplateView)` — assembles hero, featured services (3), featured portfolio (4), testimonials
- `AboutView(TemplateView)`
- `PrivacyView(TemplateView)`

#### Admin
- `SiteSettings` — inline singleton via `get_or_create`, no add button
- `HeroSection`, `AboutSection`, `Testimonial` — standard ModelAdmin with image previews

---

### 5.4 `services` App

**Purpose:** Service catalog structured around PCL's three buyer types (Client, Contractor, Consultancy) plus the six named service lines.

#### Models

```python
class BuyerType(models.TextChoices):
    CLIENT       = 'client',       'Client'
    CONTRACTOR   = 'contractor',   'Contractor'
    CONSULTANCY  = 'consultancy',  'Consultancy'

class ServiceCategory(models.Model):
    """e.g. 'Services for Clients'"""
    buyer_type    = models.CharField(max_length=20, choices=BuyerType.choices, unique=True)
    headline      = models.CharField(max_length=120)
    description   = models.TextField()
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['display_order']
        verbose_name_plural = 'Service Categories'

class Service(models.Model):
    category      = models.ForeignKey(ServiceCategory, on_delete=models.PROTECT, related_name='services')
    name          = models.CharField(max_length=120)
    slug          = models.SlugField(unique=True)
    short_desc    = models.CharField(max_length=200)
    body          = models.TextField()
    icon          = models.CharField(max_length=60, blank=True)  # Lucide icon name
    image         = models.ImageField(upload_to='services/', blank=True)
    is_featured   = models.BooleanField(default=False)
    display_order = models.PositiveSmallIntegerField(default=0)
    meta_title    = models.CharField(max_length=60, blank=True)
    meta_desc     = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ['category__display_order', 'display_order']
```

**Seed data (fixture)** — all 19 services from the brief pre-populated at `python manage.py loaddata services_seed`.

#### Views

```python
class ServicesLandingView(ListView):
    model = ServiceCategory
    template_name = 'services/landing.html'
    queryset = ServiceCategory.objects.prefetch_related('services')

    def get(self, request, *args, **kwargs):
        buyer = request.GET.get('buyer')
        qs = self.get_queryset()
        if buyer:
            qs = qs.filter(buyer_type=buyer)
        ctx = {'categories': qs, 'selected_buyer': buyer}
        # HTMX tab swap — return only the service list fragment
        if request.htmx:
            return TemplateResponse(request, 'partials/_service_list.html', ctx)
        return TemplateResponse(request, self.template_name, ctx)

class ServiceDetailView(DetailView):
    model = Service
    template_name = 'services/detail.html'
    queryset = Service.objects.select_related('category').prefetch_related('projects')
```

#### URLs
```
/services/                         ← landing (full page + HTMX tab target)
/services/<slug>/                  ← detail
```

---

### 5.5 `portfolio` App

**Purpose:** Case studies / project showcase. Visitors filter by sector and service via HTMX without page reload. Drives credibility for all three personas.

#### Models

```python
class Sector(models.TextChoices):
    INFRASTRUCTURE = 'infrastructure', 'Infrastructure'
    CONSTRUCTION   = 'construction',   'Construction'

class Project(models.Model):
    title         = models.CharField(max_length=150)
    slug          = models.SlugField(unique=True)
    client_name   = models.CharField(max_length=100, blank=True)  # optional — client may be confidential
    sector        = models.CharField(max_length=30, choices=Sector.choices)
    services_used = models.ManyToManyField('services.Service', related_name='projects', blank=True)
    location      = models.CharField(max_length=120)
    year          = models.PositiveSmallIntegerField()
    summary       = models.TextField(max_length=500)
    body          = models.TextField()
    cover_image   = models.ImageField(upload_to='portfolio/covers/')
    is_featured   = models.BooleanField(default=False)
    is_published  = models.BooleanField(default=False)
    display_order = models.PositiveSmallIntegerField(default=0)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year', 'display_order']

class ProjectImage(models.Model):
    project       = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='images')
    image         = models.ImageField(upload_to='portfolio/gallery/')
    caption       = models.CharField(max_length=200, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['display_order']
```

#### Views

```python
class PortfolioListView(ListView):
    model = Project
    template_name = 'portfolio/list.html'
    paginate_by = 12

    def get_queryset(self):
        qs = Project.objects.filter(is_published=True).prefetch_related('services_used')
        sector = self.request.GET.get('sector')
        service = self.request.GET.get('service')
        if sector:
            qs = qs.filter(sector=sector)
        if service:
            qs = qs.filter(services_used__slug=service)
        return qs

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(object_list=self.get_queryset())
        # HTMX filter swap — return only the card grid fragment
        if request.htmx:
            return TemplateResponse(request, 'partials/_project_cards.html', ctx)
        return TemplateResponse(request, self.template_name, ctx)

class ProjectDetailView(DetailView):
    model = Project
    template_name = 'portfolio/detail.html'
    queryset = Project.objects.filter(is_published=True).prefetch_related('images', 'services_used')
```

#### URLs
```
/portfolio/                         ← list (full page + HTMX filter target)
/portfolio/<slug>/                  ← detail
```

#### Admin
- `ProjectAdmin` with inline `ProjectImageInline`
- Custom action: `publish_selected`, `unpublish_selected`
- List display: title, sector, year, is_featured, is_published

---

### 5.6 `inquiries` App

**Purpose:** Structured lead capture. Every form submission creates a tracked record, triggers an email to PCL, and sends an auto-acknowledgement to the submitter. The form responds inline via HTMX — no page navigation on submit.

#### Models

```python
class InquiryStatus(models.TextChoices):
    NEW         = 'new',        'New'
    CONTACTED   = 'contacted',  'Contacted'
    QUALIFIED   = 'qualified',  'Qualified'
    CLOSED_WON  = 'won',        'Closed — Won'
    CLOSED_LOST = 'lost',       'Closed — Lost'

class Inquiry(models.Model):
    # Submitter details
    full_name    = models.CharField(max_length=120)
    email        = models.EmailField()
    phone        = models.CharField(max_length=30, blank=True)
    company      = models.CharField(max_length=120, blank=True)
    buyer_type   = models.CharField(max_length=20, choices=BuyerType.choices, blank=True)

    # Lead routing
    service      = models.ForeignKey('services.Service', on_delete=models.SET_NULL, null=True, blank=True, related_name='inquiries')
    project_desc = models.TextField(verbose_name='Project Description')
    budget_range = models.CharField(max_length=80, blank=True)

    # Honeypot — must remain empty; bots fill it, humans don't
    website      = models.CharField(max_length=200, blank=True)

    # Pipeline state (state machine — not booleans)
    status       = models.CharField(max_length=20, choices=InquiryStatus.choices, default=InquiryStatus.NEW)

    # Metadata
    source_page  = models.CharField(max_length=200, blank=True)
    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)
    notes        = models.TextField(blank=True)  # internal sales notes

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Inquiries'

    def transition_to(self, new_status: str) -> None:
        """Enforces valid state transitions. Raises ValueError on illegal move."""
        allowed = {
            InquiryStatus.NEW:       [InquiryStatus.CONTACTED],
            InquiryStatus.CONTACTED: [InquiryStatus.QUALIFIED, InquiryStatus.CLOSED_LOST],
            InquiryStatus.QUALIFIED: [InquiryStatus.CLOSED_WON, InquiryStatus.CLOSED_LOST],
        }
        if new_status not in allowed.get(self.status, []):
            raise ValueError(f'Cannot transition from {self.status} to {new_status}')
        self.status = new_status
        self.save(update_fields=['status', 'updated_at'])
```

#### Form

```python
class InquiryForm(forms.ModelForm):
    class Meta:
        model  = Inquiry
        fields = ['full_name', 'email', 'phone', 'company', 'buyer_type',
                  'service', 'project_desc', 'budget_range', 'website']
        widgets = {
            'website': forms.HiddenInput(),  # honeypot — invisible to humans
        }
```

#### Views

```python
class InquiryCreateView(CreateView):
    form_class    = InquiryForm
    template_name = 'inquiries/contact.html'

    def form_valid(self, form):
        inquiry = form.save(commit=False)
        if inquiry.website:          # honeypot triggered — discard silently
            return TemplateResponse(self.request, 'partials/_inquiry_success.html', {})
        inquiry.source_page = self.request.META.get('HTTP_REFERER', '')
        inquiry.ip_address  = self.request.META.get('REMOTE_ADDR')
        inquiry.save()
        send_inquiry_notification.delay(inquiry.pk)
        send_inquiry_acknowledgement.delay(inquiry.pk)
        # HTMX swap → return success fragment (replaces the form div)
        if self.request.htmx:
            return TemplateResponse(self.request, 'partials/_inquiry_success.html', {})
        return redirect('inquiries:sent')

    def form_invalid(self, form):
        # HTMX swap → return form fragment with errors (re-renders in place)
        if self.request.htmx:
            return TemplateResponse(
                self.request,
                'partials/_inquiry_form.html',
                {'form': form},
                status=422,   # tells HTMX to treat this as a content response, not an error
            )
        return super().form_invalid(form)


class InquiryValidateView(View):
    """HTMX-only endpoint for per-field blur validation."""

    def post(self, request):
        field_name = next(
            (k for k in request.POST if k in InquiryForm.Meta.fields), None
        )
        if not field_name:
            return HttpResponse('')
        form = InquiryForm(data={field_name: request.POST.get(field_name)})
        form.is_valid()
        error = form.errors.get(field_name, [''])[0]
        return HttpResponse(error)
```

#### Celery Tasks

```python
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_inquiry_notification(self, inquiry_id: int) -> None:
    """Sends internal alert email to PCL team via Amazon SES."""

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_inquiry_acknowledgement(self, inquiry_id: int) -> None:
    """Sends 'We received your message' email to the submitter via Amazon SES."""
```

**Both tasks are fire-and-forget from the view.** The view never waits on email.

#### Admin
- Full `InquiryAdmin` with status filter, date hierarchy, search by name/email/company
- Custom action: bulk status transitions
- Read-only fields: `source_page`, `ip_address`, `created_at`, `website`
- Status change calls `transition_to()` — not a raw field edit

#### Spam Protection
- Django CSRF baseline (HTMX sends the CSRF token automatically via `hx-headers` in `base.html`)
- Honeypot `website` field — bot submissions silently discarded in `form_valid`
- Rate limiting: max 5 submissions per IP per hour (Redis-backed via `django-ratelimit`)

---

### 5.7 HTMX Configuration in `base.html`

```html
<!-- templates/base.html (relevant head section) -->
<head>
  <!-- HTMX — loaded from CDN; pin to a specific version for reproducibility -->
  <script src="https://unpkg.com/htmx.org@2.0.4"
          integrity="sha384-..."
          crossorigin="anonymous" defer></script>

  <!-- Attach CSRF token to all HTMX requests automatically -->
  <meta name="csrf-token" content="{{ csrf_token }}">
  <script>
    document.addEventListener('DOMContentLoaded', () => {
      document.body.addEventListener('htmx:configRequest', (e) => {
        e.detail.headers['X-CSRFToken'] = document.querySelector('[name=csrf-token]').content;
      });
    });
  </script>
</head>
```

Alternatively, install HTMX via npm (`npm install htmx.org`) and serve the built file via Whitenoise — preferred for production so the asset hash is under our control.

---

### 5.8 SEO & Technical Requirements

| Requirement | Implementation |
|-------------|----------------|
| Dynamic `<title>` and `<meta description>` per page | `meta_title` / `meta_desc` fields on all content models; fallback chain to `SiteSettings.meta_description` |
| Canonical URLs | `{% block canonical %}` in base template |
| Sitemap | `django.contrib.sitemaps` — covers services, portfolio; auto-regenerated daily by Celery beat |
| Robots.txt | Served as a view; blocks `/admin/` |
| Open Graph tags | `og:title`, `og:description`, `og:image` per page |
| Image optimisation | `django-imagekit` for thumbnails (AVIF preferred, JPEG fallback) |
| Structured data | `LocalBusiness` JSON-LD block in base template (pulled from `SiteSettings`) |
| Lazy loading | `loading="lazy"` on all non-LCP images |
| Core Web Vitals | HTMX is ~14KB minified+gzipped — no JS framework overhead; no render-blocking scripts; CSS-only animations; all images carry `width` + `height` |
| HTMX + SEO | All pages are fully server-rendered on first load — crawlers see complete HTML. HTMX only enhances subsequent interactions; no content is hidden behind JS for initial render. |

---

### 5.9 Settings Layout

```
config/
├── settings/
│   ├── base.py       ← shared
│   ├── local.py      ← dev (DEBUG=True, console email backend)
│   └── production.py ← S3, SES, Redis, Sentry
```

**Key production settings:**
```python
DEFAULT_FILE_STORAGE  = 'storages.backends.s3boto3.S3Boto3Storage'
EMAIL_BACKEND         = 'django_ses.SESBackend'
CELERY_BROKER_URL     = env('REDIS_URL')
CELERY_RESULT_BACKEND = env('REDIS_URL')
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': env('REDIS_URL')}}

MIDDLEWARE = [
    ...
    'django_htmx.middleware.HtmxMiddleware',  # adds request.htmx
    ...
]
```

---

## 6. Technical Considerations

### Dependencies (Python)

```toml
# pyproject.toml (uv)
dependencies = [
    "django>=5.1",
    "django-htmx>=1.21",            # request.htmx + HtmxMiddleware
    "psycopg[binary]>=3",
    "redis>=5",
    "celery>=5.4",
    "django-environ",
    "django-storages[s3]",
    "django-ses",
    "django-imagekit",
    "django-ratelimit",
    "django-prose-editor",          # rich text in admin (no DB bloat)
    "django-simple-history",        # audit log on Project + Service
    "whitenoise",                   # static files in production
    "sentry-sdk[django]",
]
```

### Frontend (no npm build required in v1)

Tailwind CSS v4 via CDN play script for development; for production use the Tailwind CLI standalone binary to generate a purged CSS file — no Node.js build pipeline needed. HTMX served from CDN (pinned version with SRI hash) or copied into `static/js/htmx.min.js`.

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SES sending limits (sandbox) | Medium | High | Request production SES access before launch; use console backend locally |
| Media/image storage in S3 — costs spike if gallery images are unoptimised | Low | Medium | `django-imagekit` + AVIF compression; set S3 lifecycle rule for orphaned originals |
| Admin misuse wipes portfolio | Low | High | `django-simple-history` audit log on `Project` and `Service` |
| Spam flood via contact form | Medium | Medium | Honeypot + Redis rate limiter; re-evaluate CAPTCHA if >50 spam/day |
| HTMX CSRF — HTMX bypasses Django form CSRF if not wired correctly | Medium | High | `htmx:configRequest` listener in `base.html` injects `X-CSRFToken` on every request |
| `hx-push-url` breaks if user has JS disabled | Low | Low | All HTMX interactions degrade gracefully — every link and form works without JS via standard GET/POST |
| Domain not yet confirmed | High | Launch blocker | Eng. Mohammed Bashir to decide brand vs. portfolio domain before SES verification |

### Open Questions (must resolve before dev start)

- [ ] **Domain decision** — `pioneerconsultantslimited.com` vs. `pcl-consulting.com` vs. personal brand? Owner: Eng. Mohammed Bashir — Deadline: before SES config
- [ ] **Logo / brand assets** — does PCL have a finalised logo? Needed for `SiteSettings.logo` and OG image. Owner: PCL — Deadline: before frontend work begins
- [ ] **Portfolio case studies** — at least 8 project briefs needed for launch (title, client, sector, year, images, summary). Owner: PCL — Deadline: 2 weeks before launch
- [ ] **Contact details** — email and phone are blank in the brief. Owner: PCL — Deadline: before launch

---

## 7. Pages & URL Map

| URL | View | Auth | HTMX Role | Notes |
|-----|------|------|-----------|-------|
| `/` | `HomeView` | Public | — | Hero, featured services (3), featured portfolio (4), testimonials |
| `/about/` | `AboutView` | Public | — | About section + company values |
| `/services/` | `ServicesLandingView` | Public | Full page + tab target | All 3 buyer-type categories; `?buyer=` triggers partial |
| `/services/<slug>/` | `ServiceDetailView` | Public | — | Service detail + related portfolio + CTA |
| `/portfolio/` | `PortfolioListView` | Public | Full page + filter target | Grid; `?sector=` / `?service=` triggers partial |
| `/portfolio/<slug>/` | `ProjectDetailView` | Public | — | Case study + gallery |
| `/contact/` | `InquiryCreateView` | Public | Form POST swap | Full page on GET; HTMX swap on POST |
| `/contact/validate/` | `InquiryValidateView` | Public | HTMX-only | Per-field blur validation; returns error string or empty |
| `/contact/sent/` | `TemplateView` | Public | — | Non-HTMX fallback success page |
| `/privacy/` | `TemplateView` | Public | — | Privacy policy |
| `/sitemap.xml` | `SitemapView` | Public | — | Auto-generated |
| `/robots.txt` | View | Public | — | Blocks `/admin/` |
| `/admin/` | Django admin | Staff | — | Full CMS |

---

## 8. Admin CMS — What PCL Can Do Without Engineering

| Task | How |
|------|-----|
| Update hero headline / image | `SiteSettings` → `HeroSection` |
| Edit about text | `AboutSection` |
| Add / edit a service | `Service` — WYSIWYG body editor |
| Add a portfolio project | `Project` (with inline images) → toggle `is_published` |
| View and update inquiry status | `Inquiry` list → change status via dropdown |
| Read internal notes on a lead | `Inquiry` → `notes` field |
| Update contact details / social links | `SiteSettings` |
| Reorder services or testimonials | `display_order` integer field |

---

## 9. Roadmap

### North Star Metric
**Qualified Inquiry Conversion Rate** — inquiries that reach `Qualified` status / total submissions.
**Current**: — **Target by Month 3**: ≥ 30%

---

### Now — v1 (Weeks 1–6)

| Initiative | Problem Solved | Success Metric | Owner | ETA |
|------------|---------------|----------------|-------|-----|
| Core Django project scaffold | Foundation | CI passes, deploy to staging | Eng | Week 1 |
| `core` app + admin | CMS shell | Team can edit home copy without code | Eng | Week 2 |
| `services` app + seed data | Buyer-type service clarity | All 19 services visible, SEO indexed | Eng | Week 2 |
| `portfolio` app | Credibility anchor | 8 projects published at launch | Eng + PCL | Week 3 |
| `inquiries` app + Celery email | Lead capture | Submission → email in < 5 min | Eng | Week 3 |
| HTMX interactions (filter, form swap, field validation) | Smooth UX without JS framework | All interactions work with JS disabled (graceful fallback) | Eng | Week 4 |
| SEO / sitemap / OG tags | Organic discovery | 100% pages indexed within 30 days | Eng | Week 4 |
| RTL/i18n architecture | Future Arabic | `LANGUAGE_CODE` switchable without template refactor | Eng | Week 4 |
| Tailwind v4 templates | Polished UI | Passes Core Web Vitals (mobile) | Eng | Week 5 |
| Staging QA + domain / SES config | Pre-launch readiness | Zero P0 bugs, emails confirmed | Eng + PCL | Week 6 |

---

### Next — v2 (Months 2–4)

| Initiative | Hypothesis | Expected Outcome | Confidence |
|------------|------------|-----------------|------------|
| Arabic (AR) locale | GCC-market clients convert better in Arabic | +20% inquiry rate from Arabic-speaking visitors | Medium — requires translated copy from PCL |
| Blog / Insights section | Thought leadership drives organic SEO | +30% organic traffic at 90 days | Medium |
| Inquiry pipeline dashboard (HTMX-driven) | Team needs pipeline visibility inside the app — not just Django admin | Reduced time-to-contact for new leads | High — build as a staff-only Django view, HTMX status-update buttons |
| Client portal (read-only project status) | Clients want visibility without email chasing | Reduces PM email load | Low — needs validated demand from first 10 clients |

---

### Later — v3+ (Month 4+)

| Initiative | Strategic Hypothesis | Signal Needed to Advance |
|------------|---------------------|--------------------------|
| Online document delivery (reports, drawings) | Secure document exchange replaces email attachments | 3+ clients requesting this explicitly |
| White-label / multi-tenant | Rivex-pineal sells the platform to other consultancies | Confirmed commercial pipeline from Rivex-pineal |
| Bid management module | Tender preparation is the highest-effort manual service | Contractor users expressing friction in discovery interviews |

---

### What We're Not Building in v1 (and Why)

| Request | Reason for Deferral | Revisit Condition |
|---------|---------------------|-------------------|
| JavaScript framework (React, Vue, etc.) | HTMX + Django templates cover all interaction requirements; a framework would add build complexity with no user-visible benefit at this scale | When client portal or real-time features require component-level state management |
| E-commerce / payment gateway | PCL's services are bespoke-quoted; no standard SKUs exist | When at least one repeatable fixed-price service is defined |
| Job applications / careers page | Not a recruitment priority at launch | When PCL has open roles to list |
| Live chat widget | Adds third-party JS weight; email response is sufficient at this volume | When inquiry volume exceeds 50/month and <24h response SLA is missed |
| Multi-language admin interface | Adds complexity for a single-operator team | When a non-English-speaking staff member is onboarded |

---

## 10. Launch Plan

| Phase | Date | Audience | Success Gate |
|-------|------|----------|-------------|
| Internal alpha | Week 5 | Eng + Eng. Mohammed Bashir | Core flows complete, admin usable, HTMX interactions smoke-tested, no P0 bugs |
| Staging review | Week 6 | PCL team | Content approved, emails confirmed, mobile + JS-disabled tested |
| Production deploy | Week 7 | Public | SES production access active, domain live, sitemap submitted to GSC |
| Post-launch watch | Weeks 7–9 | — | Error rate < 0.5%, inquiry emails arriving, no form submission regressions |

**Rollback criteria:** If SES email delivery fails and cannot be fixed in < 2 hours, revert email backend to SMTP fallback and redeploy.

---

## 11. Django + HTMX Project Conventions (Engineering Reference)

1. **All async work via Celery** — email dispatch, sitemap regeneration, image processing. Views never block.
2. **No N+1 queries** — `PortfolioListView` prefetches `services_used`; `HomeView` prefetches `testimonials`; `ServicesLandingView` prefetches `services`.
3. **State machine for inquiries** — `InquiryStatus.TextChoices` + `transition_to()`. No boolean flags for pipeline state.
4. **Idempotent Celery tasks** — email tasks check `Inquiry.status` before sending to avoid double-send on retry.
5. **Single-tenant** — no `organization_id` needed in v1. Architecture does not preclude adding it later.
6. **`ruff check` + `ruff format` enforced** — pre-commit hook required.
7. **Migrations** — never edit applied migrations. Destructive operations (column drop, type change) flagged before `migrate`.
8. **Secrets** — all credentials via `.env` (gitignored). SES keys, S3 credentials, `SECRET_KEY` — never in source.
9. **HTMX view pattern** — every view that serves an HTMX partial checks `request.htmx` and returns the matching `partials/_*.html`. Full-page fallback always works without JS.
10. **HTMX status codes** — form validation errors return HTTP 422 so HTMX swaps the response body rather than treating it as a network error.
11. **CSRF with HTMX** — `htmx:configRequest` listener in `base.html` injects `X-CSRFToken` on every HTMX request. Never disable CSRF for HTMX routes.
12. **Graceful degradation** — every HTMX-enhanced link is a real `<a href>` and every HTMX-enhanced form has `method` + `action`. The site is fully functional without JavaScript.
13. **Tests** — `pytest-django`; at minimum: `InquiryForm` validation, `transition_to` state machine, Celery task smoke tests (mocked SES), HTMX partial views return correct template with `HX-Request` header set.

---

## 12. Appendix

### A. Service Taxonomy (from brief)

**Services for Clients:**
1. Employer agent
2. Bid preparation and administration
3. Contractor procurement and management
4. Contract management
5. Regular project reporting

**Services for Contractors:**
6. Full range of Quantity Surveying activities
7. Tender preparation
8. Preparing bill of quantities (BOQ)
9. Preparing time schedules
10. BIM modelling
11. Preparing financial reports
12. Contract handling and legal compliance

**Services for Consultancies:**
13. Proposal development
14. Architectural drawings
15. Structural design with calculations
16. Structural detailing
17. Interior design

**Named service lines (hero/services page):**
18. 3D Building Visualisation
19. Construction Web Design

### B. Sectors
- Infrastructure
- Construction

### C. Brand / Domain Decision Required
Email pattern suggested in brief: `info@pioneerconsultants.com` OR `info@pcl.com`.
Domain availability and final brand name must be confirmed by Eng. Mohammed Bashir before:
- Amazon SES domain verification
- Email template `From:` address
- Site logo / favicon

### D. Key Third-Party Integrations

| Service | Purpose | Env var |
|---------|---------|---------|
| Amazon SES | Transactional email (inquiry alerts + acknowledgements) | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SES_REGION_NAME` |
| Amazon S3 | Media file storage (portfolio images, service images) | `AWS_STORAGE_BUCKET_NAME` |
| Sentry | Error tracking | `SENTRY_DSN` |
| Redis | Celery broker + result backend + rate-limit store | `REDIS_URL` |
| PostgreSQL | Primary database | `DATABASE_URL` |
