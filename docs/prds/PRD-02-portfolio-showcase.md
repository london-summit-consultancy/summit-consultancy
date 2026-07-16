# PRD-02: Portfolio Showcase

**Status**: Approved — Built (v1 complete; templates pending in Phase 7)
**Author**: Alex (PM) | **Last Updated**: 2026-06-28 | **Version**: 1.0
**Stakeholders**: Eng. Mohammed Bashir (PCL), Backend Engineer
**Workflow spec**: `docs/workflows/WORKFLOW-portfolio-filter.md`, `WORKFLOW-project-publish.md`

---

## 1. Problem Statement

PCL's sales conversations start from zero because prospects cannot evaluate PCL's credentials before a discovery call. Without a portfolio, every referral must be taken on faith. In a market where 2–3 firms are evaluated simultaneously, credibility is established before the first phone call.

**Evidence**:
- PCL founder confirmed that referrals often ask "do you have examples of similar work?" before agreeing to a meeting
- Zero portfolio proof exists digitally today
- Personas (Sarah the Client, Hassan the Contractor, Yusuf the Consultancy) all need sector-specific evidence: they are not convinced by a generic project list

**Cost of not solving**: Prospects who cannot self-validate PCL's track record will shortlist competitors who have visible case studies.

---

## 2. Goals & Success Metrics

| Goal | Metric | Baseline | Target | Window |
|---|---|---|---|---|
| Portfolio at launch | Published projects | 0 | ≥ 8 | Launch day |
| Sector self-service | % visitors who use sector/service filter | — | ≥ 25% | 60 days |
| Portfolio → contact funnel | % portfolio visitors who click contact CTA | — | ≥ 15% | 60 days |
| Content autonomy | % of portfolio updates done without Eng | 0% | 100% | Launch day |

---

## 3. Non-Goals

- No visitor reviews or comments on projects
- No secure document download (drawings, calculations) — v2+
- No client-facing project-status view — v2+
- No pagination in v1 (grid shows all published projects; acceptable at < 30 entries)

---

## 4. User Personas & Stories

### Primary — Sarah (Client) / Hassan (Contractor) / Yusuf (Consultancy)

**Story 1**: As a prospect, I want to browse PCL's past projects filtered by my sector so that I can quickly find evidence relevant to my own project.

**Acceptance Criteria**:
- [x] Given I visit `/portfolio/`, I see all published projects in a grid ordered by year (newest first)
- [x] Given I click the "Construction" sector tab, the grid updates without page reload to show only construction projects
- [x] Given I click the "Infrastructure" tab, the same filter applies
- [x] Given JavaScript is disabled, the filter link is a real `<a href="/portfolio/?sector=construction">` that works via normal GET
- [x] Given no projects match a filter, the grid shows an empty state message (no broken layout)

**Story 2**: As a prospect, I want to read a full case study for a specific project so I can understand scope, deliverables, and outcome.

**Acceptance Criteria**:
- [x] Given I click a project card, I reach `/portfolio/<slug>/` with full project body, gallery, and related projects
- [x] Given a project is unpublished, attempting to access its URL directly returns 404
- [x] Given the project has images, a gallery is visible and keyboard-accessible (Escape closes lightbox)

### Primary — Eng. Mohammed Bashir (PCL Operator)

**Story 3**: As the PCL team, I want to add a new project case study and publish it without involving an engineer.

**Acceptance Criteria**:
- [x] Given I log into `/admin/portfolio/project/add/`, I can fill in all project fields, add inline images, and save
- [x] Given `is_published=False`, the project is invisible to public visitors
- [x] Given I toggle `is_published=True`, the project appears on `/portfolio/` on the next page load
- [x] All changes are tracked in history (who changed what, when) — except bulk actions (GAP-3 — known, documented)

---

## 5. Solution Overview

The portfolio is a grid of published project cards at `/portfolio/` filtered by sector and/or service slug. HTMX powers the filter without a page reload — the same URL serves both the full page (on first load or with JS disabled) and the card grid partial (on HTMX filter requests).

Each project card links to a full case study at `/portfolio/<slug>/` with a rich body, optional image gallery, related projects (same sector, max 3), and a contact CTA.

The admin team manages portfolio entirely through Django admin — adding project records, uploading images, setting published state, and ordering via `display_order`. `django-simple-history` records all changes with user attribution for accountability.

**Key design decisions**:
- **`is_published` gate on queryset level**: `ProjectDetailView.queryset = Project.objects.filter(is_published=True)` — unpublished projects cannot be accessed even by guessing the slug
- **HTMX with `hx-push-url="true"`**: Filter updates the browser URL, so the back button and direct links to a filtered view work correctly
- **No pagination in v1**: At ≤ 30 projects the grid is scrollable; pagination deferred until volume warrants it
- **Gallery via vanilla JS only**: Image data is already in the DOM from the server render — no HTMX round-trip needed for lightbox. 30-line vanilla JS listener handles open/close/prev/next.

---

## 6. Technical Considerations

### Data Model

```
Project
├── title           CharField(150)
├── slug            SlugField(unique)
├── client_name     CharField(100, blank)  ← optional — may be confidential
├── sector          TextChoices → Sector
├── services_used   M2M → Service
├── location        CharField(120)
├── year            PositiveSmallIntegerField
├── summary         TextField(500)  ← used as meta_desc fallback
├── body            TextField  ← rich content (django-prose-editor)
├── cover_image     ImageField(upload_to="portfolio/covers/")
├── is_featured     BooleanField [default: False]
├── is_published    BooleanField [default: False]
├── display_order   PositiveSmallIntegerField [default: 0]
├── created_at      DateTimeField(auto_now_add)
└── history         HistoricalRecords

ProjectImage
├── project         FK → Project (CASCADE)
├── image           ImageField(upload_to="portfolio/gallery/")
├── caption         CharField(200, blank)
└── display_order   PositiveSmallIntegerField [default: 0]
```

### Queryset Optimisation (N+1 prevention)

```python
# List view
Project.objects.filter(is_published=True)
    .prefetch_related("services_used")
    .order_by("-year", "display_order")

# Detail view
Project.objects.filter(is_published=True)
    .prefetch_related("images", "services_used")
```

### SEO Behaviour

| Page | `<title>` | `<meta description>` | OG image |
|---|---|---|---|
| `/portfolio/` | "Portfolio — {site.brand_name}" | `site.meta_description` | Site logo |
| `/portfolio/<slug>/` | `{project.title} — {site.brand_name}` | `project.summary[:160]` | `project.cover_image` |

### Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| ≥ 8 projects not submitted by PCL before launch | Medium | High | PCL content deadline: 2 weeks before Phase 9 |
| Cover image missing on published project | Low | Medium | Admin `clean()` validation before publish, or template fallback |
| History not recorded on bulk publish | Certain (known GAP-3) | Low | Documented; PCL team informed; audit via individual save if needed |

### Open Questions

- [ ] Should client names on projects be hidden by default, shown only on request? — Owner: PCL | Deadline: before content submission
- [ ] Will PCL provide professional photography, or should we plan for image quality variance? — Owner: PCL | Deadline: 3 weeks before launch

---

## 7. Content Requirements from PCL

For each project entry PCL must supply:

| Field | Required | Notes |
|---|---|---|
| Project title | ✅ | Public-facing |
| Sector | ✅ | infrastructure or construction |
| Location | ✅ | City / region |
| Year | ✅ | Year of completion |
| Summary | ✅ | ≤ 500 chars; used on card and as meta description |
| Body / case study | ✅ | Full description of scope, approach, outcome |
| Cover image | ✅ | Minimum 1200px wide; will be served via S3 |
| Services used | Optional | Link to service catalog entries |
| Client name | Optional | Omit if confidential |
| Gallery images | Optional | Up to 10; appear in lightbox on detail page |

Minimum 8 projects submitted 2 weeks before launch date.

---

## 8. Launch Plan

| Phase | Gate |
|---|---|
| Alpha | Admin can add project, toggle publish, see it on /portfolio/ |
| Content | PCL submits ≥ 8 project briefs; engineer loads content into admin |
| Staging | All projects render correctly on mobile; filter works; detail pages 404 correctly for unpublished |
| Launch | Portfolio in sitemap, OG tags verified via Facebook Debugger |

---

## 9. Appendix

- Workflow specs: `docs/workflows/WORKFLOW-portfolio-filter.md`, `WORKFLOW-project-publish.md`
- Tests: `tests/test_portfolio.py` (7 tests, all passing)
