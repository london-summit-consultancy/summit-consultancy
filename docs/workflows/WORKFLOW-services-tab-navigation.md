# WORKFLOW: Services Tab Navigation

**Version**: 1.0 | **Date**: 2026-06-28 | **Author**: Workflow Architect
**Status**: Approved

---

## Overview

Visitors browse Pioneer's 19 services at `/services/`. Services are grouped by `ServiceCategory` (which carries a `buyer_type`). A tab UI lets visitors filter categories by buyer type (`client`, `contractor`, `consultancy`). HTMX fires a GET request on tab click and swaps only the service list area. Without HTMX, the full page renders. Individual service pages are accessible at `/services/<slug>/`.

---

## Actors

| Actor | Role |
|---|---|
| Visitor | Navigates to /services/, clicks buyer-type tabs |
| ServicesLandingView | Handles GET, filters categories, selects template |
| ServiceDetailView | Renders single service with related projects |
| ServiceCategory / Service models | Provide data |
| PostgreSQL | Executes queries |

---

## Prerequisites

- `ServiceCategory` and `Service` records loaded (via `services_seed` fixture or admin entry)
- Each `ServiceCategory` has a `buyer_type` value matching `BuyerType.choices`

---

## Trigger

- **Entry**: Visitor navigates to `/services/`
- **Filter**: Visitor clicks a buyer-type tab → HTMX fires `GET /services/?buyer=<value>`
- **Detail**: Visitor clicks a service → `GET /services/<slug>/`

---

## Workflow Tree — Landing Page

### STEP 1: Build category queryset
**Actor**: `ServicesLandingView.get()`
**Action**:
  1. Base: `ServiceCategory.objects.prefetch_related("services").order_by("display_order")`
  2. If `?buyer=<value>`: apply `.filter(buyer_type=buyer)` — filters the entire category queryset, not individual services within them
**Timeout**: < 50 ms
**Input**: `request.GET.get("buyer", "")`
**Output on SUCCESS**: filtered `qs` → GO TO STEP 2
**Output on FAILURE**:
  - `FAILURE(unknown buyer value)`: no error — filter returns empty queryset silently

---

### STEP 2: Build context
**Actor**: `ServicesLandingView.get()`
**Action**: `ctx = {"categories": qs, "selected_buyer": buyer, "all_categories": ServiceCategory.objects.order_by("display_order")}`
**Note**: `all_categories` is fetched separately (unfiltered) so the tab UI always shows all three buyer type options regardless of filter.

---

### STEP 3: Select template and return
**Action**:
  - `request.htmx` → `TemplateResponse(request, "partials/_service_list.html", ctx)` — service cards only
  - Not HTMX → `TemplateResponse(request, "services/landing.html", ctx)` — full page with tabs

**Observable states**:
  - Visitor sees (HTMX tab click): service list area swaps; active tab state updates in UI
  - Visitor sees (no JS): full page rendered with pre-filtered results
  - Database: 1 query for filtered categories + 1 for all_categories (tab UI)

---

## Workflow Tree — Service Detail

### Trigger: `GET /services/<slug>/`
**View**: `ServiceDetailView` (DetailView)
**Queryset**: `Service.objects.select_related("category").prefetch_related("projects")`
**Happy path**: renders `services/detail.html` with:
  - `related_projects`: `self.object.projects.filter(is_published=True).order_by("-year")[:4]`
  - `page_title`: `service.effective_meta_title` (falls back to `service.name` if `meta_title` is blank)
  - `page_meta_desc`: `service.effective_meta_desc` (falls back to `service.description` if `meta_desc` is blank)
**Failure**:
  - Unknown slug → Django 404

---

## SEO Implications

`effective_meta_title` and `effective_meta_desc` properties on `Service` implement a two-tier fallback:

```
meta_title (if set) → service.name
meta_desc  (if set) → service.description[:160]
```

Template must use these — not `service.name` directly — to allow per-service SEO overrides without a code change.

---

## State Transitions

```
[/services/ loaded (no filter)]
  -> (HTMX tab click, buyer=client)       -> [partial _service_list.html, only client categories]
  -> (HTMX tab click, buyer=contractor)   -> [partial _service_list.html, only contractor categories]
  -> (HTMX tab click, buyer=consultancy)  -> [partial _service_list.html, only consultancy categories]
  -> (HTMX tab click, buyer="" or "all")  -> [partial _service_list.html, all categories]
  -> (click on service card)              -> GET /services/<slug>/ → full page
```

---

## Test Cases

| Test | Trigger | Expected behaviour |
|---|---|---|
| TC-01: No filter | GET /services/ | 200, all categories, full page |
| TC-02: Filter by buyer (HTMX) | GET /services/?buyer=client + HX-Request | 200, partial template, client categories only |
| TC-03: Filter by buyer (non-HTMX) | GET /services/?buyer=contractor | 200, full page, contractor categories only |
| TC-04: Unknown buyer | GET /services/?buyer=unknown | 200, empty categories list |
| TC-05: Service detail | GET /services/bim-modelling/ | 200, service page with related projects |
| TC-06: Unknown service slug | GET /services/nonexistent/ | 404 |
| TC-07: All_categories always present | GET /services/?buyer=client | `all_categories` in context contains all 3 buyer type groups |

---

## Assumptions

| # | Assumption | Risk if wrong |
|---|---|---|
| A1 | All 19 services in the seed fixture are assigned to the correct `buyer_type` categories | Misassigned services appear under wrong tab or not at all |
| A2 | `service.description` is not blank (used as meta_desc fallback) | If blank, `effective_meta_desc` returns blank string — no meta description served to crawlers |
| A3 | `prefetch_related("projects")` on detail view covers `is_published=True` filter | `prefetch_related` fetches all related projects; the subsequent `.filter(is_published=True)` on the prefetched manager adds a second query. For 4 projects this is fine. |

## Spec vs Reality Audit Log

| Date | Finding | Action taken |
|---|---|---|
| 2026-06-28 | Initial spec — code matches | — |
