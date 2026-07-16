# PRD-03: Services Catalog

**Status**: Approved — Built (v1 complete; templates pending in Phase 7)
**Author**: Alex (PM) | **Last Updated**: 2026-06-28 | **Version**: 1.0
**Stakeholders**: Eng. Mohammed Bashir (PCL), Backend Engineer
**Workflow spec**: `docs/workflows/WORKFLOW-services-tab-navigation.md`

---

## 1. Problem Statement

PCL offers 19 services across three fundamentally different buyer types — Clients, Contractors, and Consultancies. These buyers have different vocabularies, different needs, and different decision criteria. A single flat service list would either overwhelm or confuse each buyer type.

Without a structured service taxonomy, prospects who arrive via a referral cannot quickly self-identify which services apply to them — and a confused prospect bounces without converting.

**Evidence**:
- PCL founder provided a detailed 3-way buyer taxonomy in the brief: services for Clients, for Contractors, for Consultancies
- Competitor sites in the sector typically list services as a flat grid, leading to low engagement
- All three prospect personas have different service entry points and should not be shown the same content

---

## 2. Goals & Success Metrics

| Goal | Metric | Baseline | Target | Window |
|---|---|---|---|---|
| Buyer self-segmentation | % /services/ visitors who click a buyer-type tab | — | ≥ 40% | 60 days |
| Service page authority | Services pages indexed by Google | 0 | 19 (all services) | 30 days |
| Cross-navigation | % service detail visitors who visit portfolio | — | ≥ 20% | 60 days |
| Service → contact | % service page visitors who click contact CTA | — | ≥ 10% | 60 days |

---

## 3. Non-Goals

- No service pricing or estimates — all bespoke
- No online booking or scheduling — contact form only
- No per-service team member profiles — v2+
- No client testimonials per-service — testimonials on homepage only in v1

---

## 4. User Personas & Stories

### Primary — Sarah (Client)

**Story 1**: As Sarah, I want to see only the services relevant to project owners so I can quickly understand what PCL can do for me.

**Acceptance Criteria**:
- [x] Given I arrive at `/services/`, I see all categories with a buyer-type tab bar
- [x] Given I click the "For Clients" tab, only client-relevant services appear without a page reload
- [x] Given JavaScript is disabled, clicking the tab link navigates to `/services/?buyer=client` and renders the filtered list
- [x] Given I see a service I'm interested in, clicking the card takes me to `/services/<slug>/` with a full description

### Primary — Hassan (Contractor)

**Story 2**: As Hassan, I want to see BIM modelling, BOQ preparation, and QS activities clearly listed as contractor services so I can confirm PCL works with contractors before reaching out.

**Acceptance Criteria**:
- [x] 10 contractor-specific services appear under the "For Contractors" tab
- [x] Each service shows a short description (≤ 200 chars) and an icon on the card
- [x] Service detail for BIM Modelling links to any portfolio projects where BIM was used

### Primary — Eng. Mohammed Bashir (PCL Operator)

**Story 3**: As the PCL team, I want to edit service descriptions without touching code so that I can keep content accurate as our offerings evolve.

**Acceptance Criteria**:
- [x] Service body is editable via `django-prose-editor` rich text field in admin
- [x] `meta_title` and `meta_desc` fields allow SEO optimisation per-service without touching templates
- [x] `is_featured=True` controls which 3 services appear on the homepage (no code change)

---

## 5. Solution Overview

Services are structured in a two-level hierarchy: `ServiceCategory` (one per buyer type) → `Service` (the individual offerings). The landing page at `/services/` shows all three categories with a buyer-type tab UI. HTMX powers the tab switching — clicking a tab fires a GET to `/services/?buyer=<value>` and swaps only the service list area in place.

Each service has its own page at `/services/<slug>/` with a full description body, icon, related portfolio projects, and an inline contact CTA.

All 19 services are pre-loaded via the `services_seed.json` fixture. PCL can edit any service through Django admin with a rich-text body editor. `display_order` on both `ServiceCategory` and `Service` lets PCL reorder without code.

The homepage surfaces 3 featured services (`is_featured=True`) — currently: BIM Modelling (pk=10), Structural Design (pk=15), 3D Visualisation (pk=18).

**Key design decisions**:
- **Buyer-type grouping via `ServiceCategory`**: Each category has `buyer_type` as a unique field — exactly one category per buyer type. This enforces the taxonomy from the brief.
- **HTMX tab pattern with `all_categories` in context**: The full tab bar always renders (from `all_categories` — unfiltered), even when a filter is active. Only the service list area swaps. This avoids the tab bar disappearing on filter.
- **SEO meta fallback chain**: `meta_title` (if set) → `service.name`; `meta_desc` (if set) → `service.description[:160]`. Template must use `effective_meta_title`/`effective_meta_desc` properties, not raw fields.

---

## 6. Technical Considerations

### Data Model

```
ServiceCategory
├── buyer_type     TextChoices → BuyerType (unique)
├── headline       CharField(120)
├── description    TextField
└── display_order  PositiveSmallIntegerField

Service
├── category       FK → ServiceCategory (PROTECT)
├── name           CharField(120)
├── slug           SlugField(unique)
├── short_desc     CharField(200)      ← card summary
├── body           TextField           ← full description (prose editor)
├── icon           CharField(60, blank) ← Lucide icon name
├── image          ImageField(blank)
├── is_featured    BooleanField [default: False]
├── display_order  PositiveSmallIntegerField
├── meta_title     CharField(60, blank)
└── meta_desc      CharField(160, blank)
```

### Seed Data

All 3 categories and 19 services are in `fixtures/services_seed.json`. Load once with:

```bash
uv run python manage.py loaddata services_seed
```

Featured services (for homepage): pk=10 (BIM Modelling), pk=15 (Structural Design), pk=18 (3D Visualisation).

### Queryset Optimisation

```python
# Landing view
ServiceCategory.objects.prefetch_related("services").order_by("display_order")
# When filtered: .filter(buyer_type=buyer)

# Detail view
Service.objects.select_related("category").prefetch_related("projects")
# Related projects: .filter(is_published=True).order_by("-year")[:4]
```

### SEO Behaviour

| Page | `<title>` | `<meta description>` |
|---|---|---|
| `/services/` | "Services — {site.brand_name}" | `site.meta_description` |
| `/services/<slug>/` | `service.effective_meta_title` + " — {site.brand_name}" | `service.effective_meta_desc` |

### Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `service.description` left blank | Medium | Low | `effective_meta_desc` falls back to empty string — no meta description served to crawlers |
| Service body content not updated by PCL | Medium | Low | `short_desc` from fixture still renders on cards; body is supplementary |
| 3 featured services changed incorrectly | Low | Low | `is_featured` checkbox in admin, labelled clearly |

---

## 7. Launch Plan

| Phase | Gate |
|---|---|
| Alpha | 19 services visible on `/services/`, buyer tabs filter correctly |
| Content | PCL reviews and edits service descriptions to match current offering |
| Staging | SEO meta verified for all 19 service pages |
| Launch | Services in sitemap, indexed by GSC within 30 days |

---

## 8. Appendix

- Workflow spec: `docs/workflows/WORKFLOW-services-tab-navigation.md`
- Seed fixture: `fixtures/services_seed.json`
- Service taxonomy: `docs/PIONEER_PRODUCT_SPEC.md` Appendix A
