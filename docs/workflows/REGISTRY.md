# Pioneer Consultants — Workflow Registry

**Version**: 1.0 | **Date**: 2026-06-28 | **Author**: Workflow Architect
**Project**: PCL Django + HTMX web application

---

## View 1: By Workflow (master list)

| Workflow | Spec file | Status | Trigger | Primary actor |
|---|---|---|---|---|
| Inquiry submission | WORKFLOW-inquiry-submission.md | Approved | POST /contact/ | Visitor → Celery |
| HTMX field blur validation | WORKFLOW-field-blur-validation.md | Approved | POST /contact/validate/ | Visitor (HTMX blur) |
| Email notification task | WORKFLOW-email-notification-task.md | Approved | Celery enqueue after save | Celery worker |
| Email acknowledgement task | WORKFLOW-email-acknowledgement-task.md | Approved | Celery enqueue after save | Celery worker |
| Inquiry pipeline management | WORKFLOW-inquiry-pipeline-management.md | Approved | Admin UI / transition_to() | Admin operator |
| Portfolio filter & browse | WORKFLOW-portfolio-filter.md | Approved | GET /portfolio/?sector=&service= | Visitor (HTMX or full) |
| Services tab navigation | WORKFLOW-services-tab-navigation.md | Approved | GET /services/?buyer= | Visitor (HTMX or full) |
| Project publish/unpublish | WORKFLOW-project-publish.md | Approved | Admin bulk action or inline toggle | Admin operator |
| Site settings cache | WORKFLOW-site-settings-cache.md | Approved | Every page request + post_save signal | Context processor |
| Sitemap generation | WORKFLOW-sitemap-generation.md | Draft | GET /sitemap.xml | Search engine crawler |

---

## View 2: By Component (code → workflows)

| Component | File(s) | Workflows it participates in |
|---|---|---|
| InquiryCreateView | apps/inquiries/views.py | Inquiry submission |
| InquiryValidateView | apps/inquiries/views.py | HTMX field blur validation |
| InquirySuccessView | apps/inquiries/views.py | Inquiry submission (terminal step) |
| InquiryForm | apps/inquiries/forms.py | Inquiry submission, HTMX field blur validation |
| Inquiry model | apps/inquiries/models.py | Inquiry submission, Inquiry pipeline management |
| Inquiry.transition_to() | apps/inquiries/models.py | Inquiry pipeline management |
| InquiryAdmin | apps/inquiries/admin.py | Inquiry pipeline management |
| send_inquiry_notification | apps/inquiries/tasks.py | Email notification task |
| send_inquiry_acknowledgement | apps/inquiries/tasks.py | Email acknowledgement task |
| PortfolioListView | apps/portfolio/views.py | Portfolio filter & browse |
| ProjectDetailView | apps/portfolio/views.py | Portfolio filter & browse |
| Project model | apps/portfolio/models.py | Portfolio filter & browse, Project publish/unpublish |
| ProjectAdmin | apps/portfolio/admin.py | Project publish/unpublish |
| ServicesLandingView | apps/services/views.py | Services tab navigation |
| ServiceDetailView | apps/services/views.py | Services tab navigation |
| SiteSettings model | apps/core/models.py | Site settings cache |
| site_settings context_processor | apps/core/context_processors.py | Site settings cache |
| clear_site_settings_cache signal | apps/core/models.py | Site settings cache |
| Sitemaps (3 classes) | apps/core/sitemaps.py | Sitemap generation |
| config/urls.py | config/urls.py | All workflows (URL routing) |
| Celery config | config/celery.py | Email notification task, Email acknowledgement task |
| Redis (CACHES) | config/settings/base.py | Site settings cache, Rate limiter |
| django-ratelimit decorator | apps/inquiries/views.py | Inquiry submission |

---

## View 3: By User Journey

### Visitor Journeys

| What the visitor experiences | Underlying workflow(s) | Entry point |
|---|---|---|
| Submits a contact/enquiry form | Inquiry submission → Email notification task + Email acknowledgement task | POST /contact/ |
| Sees live field errors as they type/leave each field | HTMX field blur validation | POST /contact/validate/ (HTMX-only) |
| Filters portfolio by sector or service | Portfolio filter & browse | GET /portfolio/?sector=&service= |
| Views a single project case study | Portfolio filter & browse (detail) | GET /portfolio/{slug}/ |
| Browses services by buyer type (tabs) | Services tab navigation | GET /services/?buyer= |
| Views a single service detail page | Services tab navigation (detail) | GET /services/{slug}/ |

### Operator Journeys

| What the operator does | Underlying workflow(s) | Entry point |
|---|---|---|
| Views/searches incoming enquiries | Inquiry pipeline management | Admin /admin/inquiries/inquiry/ |
| Moves an inquiry through the pipeline | Inquiry pipeline management | Admin inline status field |
| Publishes or unpublishes a project | Project publish/unpublish | Admin /admin/portfolio/project/ |
| Updates site name, contact details, branding | Site settings cache (write) | Admin /admin/core/sitesettings/ |

### System-to-System Journeys

| What happens automatically | Underlying workflow(s) | Trigger |
|---|---|---|
| Staff email fired on new inquiry | Email notification task | Celery worker after inquiry save |
| Visitor acknowledgement email fired | Email acknowledgement task | Celery worker after inquiry save |
| Site settings served to every template | Site settings cache (read) | Django context processor per-request |
| Sitemap served to search crawlers | Sitemap generation | GET /sitemap.xml |

---

## View 4: By State (Inquiry pipeline)

| State | Display label | Entered by | Exited by | Next allowed states |
|---|---|---|---|---|
| `new` | New | Initial save on form submit | transition_to("contacted") | contacted |
| `contacted` | Contacted | transition_to("contacted") | transition_to("qualified" / "lost") | qualified, closed_lost |
| `qualified` | Qualified | transition_to("qualified") | transition_to("won" / "lost") | closed_won, closed_lost |
| `won` | Closed — Won | transition_to("won") | *(terminal)* | — |
| `lost` | Closed — Lost | transition_to("lost") | *(terminal)* | — |

| State | Display label | Entered by | Exited by |
|---|---|---|---|
| Project `is_published=False` | Draft | Initial create | Publish action / inline toggle |
| Project `is_published=True` | Published | Publish action | Unpublish action |
