# WORKFLOW: Portfolio Filter & Browse

**Version**: 1.0 | **Date**: 2026-06-28 | **Author**: Workflow Architect
**Status**: Approved

---

## Overview

Visitors browse published projects at `/portfolio/`. They can filter by sector (`infrastructure` or `construction`) and/or by service slug using GET query parameters. When HTMX fires the filter request, only the project cards partial is returned and swapped in-place. Without HTMX (direct navigation, no JS), the full page renders. Both paths use identical queryset logic.

---

## Actors

| Actor | Role |
|---|---|
| Visitor | Browses and filters via UI controls |
| PortfolioListView | Handles GET, filters queryset, selects template |
| Project model | Provides published queryset with prefetch |
| PostgreSQL | Executes the filtered query |

---

## Prerequisites

- At least one `Project` with `is_published=True` exists
- `Sector.choices` available for filter UI rendering
- `Service.objects.order_by("name")` available for service filter dropdown

---

## Trigger

- **User action**: Visitor navigates to `/portfolio/` or selects a filter
- **Endpoint**: `GET /portfolio/`
- **Query params**: `?sector=infrastructure|construction`, `?service=<slug>` (both optional, combinable)
- **HTMX**: filter controls carry `hx-get` targeting the project cards container

---

## Workflow Tree

### STEP 1: Build queryset
**Actor**: `PortfolioListView._get_queryset()`
**Action**:
  1. Base: `Project.objects.filter(is_published=True).prefetch_related("services_used").order_by("-year", "display_order")`
  2. If `?sector=<value>`: apply `.filter(sector=sector)`
  3. If `?service=<slug>`: apply `.filter(services_used__slug=service).distinct()`
**Timeout**: < 100 ms (indexed FK/M2M lookup)
**Input**: `request.GET.get("sector", "")`, `request.GET.get("service", "")`
**Output on SUCCESS**: filtered QuerySet (lazy, not yet evaluated) → GO TO STEP 2
**Output on FAILURE**:
  - `FAILURE(invalid sector value)`: no error raised — `filter(sector=<unknown>)` returns an empty queryset silently. No 400 is returned. This is intentional permissive behaviour.
  - `FAILURE(unknown service slug)`: same — empty queryset.

---

### STEP 2: Build context
**Actor**: `PortfolioListView.get()`
**Action**: Assembles `ctx = {"projects": qs, "sectors": Sector.choices, "services": Service.objects.order_by("name"), "selected_sector": ..., "selected_service": ...}`
**Note**: `Service.objects.order_by("name")` is an additional query on every request. No caching. Acceptable for this scale.

---

### STEP 3: Select template and return
**Actor**: `PortfolioListView.get()`
**Action**:
  - `request.htmx` is `True` → return `TemplateResponse(request, "partials/_project_cards.html", ctx)` — only the cards grid
  - `request.htmx` is `False` → return `TemplateResponse(request, "portfolio/list.html", ctx)` — full page with filters + cards

**Observable states**:
  - Visitor sees (HTMX): project cards grid updates in-place, filters and navigation stay rendered
  - Visitor sees (non-HTMX): full page rendered
  - Database: two SELECTs (projects + services)
  - Logs: `GET /portfolio/?sector=...` 200

---

## State Transitions

```
[/portfolio/ loaded]
  -> (HTMX filter click) -> [partial _project_cards.html swapped, URL updated by hx-push-url]
  -> (non-HTMX navigation) -> [full page rendered]
  -> (unknown sector/service) -> [empty cards list rendered — no error]
```

---

## Project Detail Sub-workflow

### Trigger: `GET /portfolio/<slug>/`
**View**: `ProjectDetailView` (DetailView on `Project.objects.filter(is_published=True)`)
**Happy path**: Visitor navigates to a project detail page → full page rendered with images, related projects (same sector, excl. self, top 3 by `-year`)
**Failure**:
  - `FAILURE(slug not found OR is_published=False)`: Django DetailView returns 404. No custom 404 template yet — uses Django default.
  - `FAILURE(no related projects)`: `ctx["related"]` is an empty queryset — template must handle gracefully

---

## Critical Notes

**N+1 prevention**: `_get_queryset()` uses `prefetch_related("services_used")` — correct for M2M. The `cover_image` ImageField is a single column attribute and does not trigger additional queries per row.

**`is_published` filter enforced at queryset level**: Unpublished projects are never exposed via list or detail. Attempting `GET /portfolio/unpublished-slug/` returns 404.

---

## Test Cases

| Test | Trigger | Expected behaviour |
|---|---|---|
| TC-01: No filter | GET /portfolio/ | 200, all published projects |
| TC-02: Sector filter (match) | GET /portfolio/?sector=construction | 200, only construction projects |
| TC-03: Sector filter (no match) | GET /portfolio/?sector=infrastructure (none exist) | 200, empty list |
| TC-04: Service slug filter | GET /portfolio/?service=<valid-slug> | 200, projects using that service |
| TC-05: Unknown sector | GET /portfolio/?sector=unknown | 200, empty list (no 400) |
| TC-06: HTMX request | GET + HX-Request: true | 200, template = _project_cards.html |
| TC-07: Non-HTMX request | GET (no HTMX header) | 200, template = portfolio/list.html |
| TC-08: Published detail | GET /portfolio/valid-slug/ | 200 |
| TC-09: Unpublished detail | GET /portfolio/unpublished-slug/ | 404 |

---

## Assumptions

| # | Assumption | Risk if wrong |
|---|---|---|
| A1 | `hx-push-url` is set on filter controls to update browser URL on HTMX filter | If not set, back button breaks filter state |
| A2 | `cover_image` is always present on published projects | If a project is published without a cover image, template may render a broken `<img>` src |
| A3 | Related projects query (`filter(sector=...).exclude(pk=...).order_by("-year")[:3]`) has no prefetch | Three additional DB hits per detail page load. Acceptable at this scale. |

## Spec vs Reality Audit Log

| Date | Finding | Action taken |
|---|---|---|
| 2026-06-28 | Initial spec — code matches | — |
| 2026-06-28 | A1 (hx-push-url) unverifiable from views.py alone — template audit needed | Template not yet built; to be verified when portfolio/list.html is written |
