# WORKFLOW: Project Publish / Unpublish

**Version**: 1.0 | **Date**: 2026-06-28 | **Author**: Workflow Architect
**Status**: Approved
**Related**: [[WORKFLOW-portfolio-filter]]

---

## Overview

Admin operators control the public visibility of portfolio projects using two mechanisms: (1) a bulk action on the project list, and (2) an inline editable `is_published` toggle on the list view. All edits are tracked by `django-simple-history` (`HistoricalRecords`). There is no staging/preview workflow — publishing goes live immediately.

---

## Actors

| Actor | Role |
|---|---|
| Admin operator | Selects projects, triggers publish/unpublish action |
| ProjectAdmin | Exposes list actions; provides `list_editable` for inline toggle |
| Project model + HistoricalRecords | Persists state; records change history |
| PostgreSQL | Executes the UPDATE |
| simple_history middleware | Captures `request.user` on every historical record |

---

## Prerequisites

- Operator authenticated as Django staff with `portfolio.change_project` permission
- At least one `Project` record exists

---

## Trigger

### Mechanism A — Bulk action
- **User action**: Check one or more projects on `/admin/portfolio/project/`, select "Publish selected projects" or "Unpublish selected projects" from the action dropdown, click "Go"
- **Endpoint**: POST to `/admin/portfolio/project/` (Django admin action)

### Mechanism B — Inline toggle
- **User action**: Click the `is_published` checkbox directly in the list view table, click "Save"
- **Endpoint**: POST to `/admin/portfolio/project/` (Django changelist save)

### Mechanism C — Individual edit
- **User action**: Open a project at `/admin/portfolio/project/<id>/change/`, change `is_published` in the Display fieldset, click "Save"

---

## Workflow Tree

### STEP 1A: Bulk action — queryset update
**Actor**: `ProjectAdmin.publish_selected` / `unpublish_selected`
**Action**: `queryset.update(is_published=True/False)` — a single SQL UPDATE affecting all selected rows
**Timeout**: < 500 ms (depends on selection count)
**Input**: `queryset` of selected projects
**Output on SUCCESS**: all selected projects updated → GO TO STEP 2
**Output on FAILURE**:
  - `FAILURE(db_error)`: unhandled exception → Django 500; partial update possible if mid-batch

**CRITICAL GAP — History not recorded for bulk action**: `queryset.update()` bypasses Django's model `save()` method. `simple_history`'s `HistoricalRecords` hook is `post_save` on the model instance. **Bulk `queryset.update()` does NOT trigger `post_save` per instance — history is not recorded for bulk publish/unpublish actions.**

---

### STEP 1B: Inline toggle / individual edit
**Actor**: Django admin `save_model()`
**Action**: `project.save()` — triggers `post_save` signal → `simple_history` records a `HistoricalProject` entry with the operator's user ID
**Output on SUCCESS**: single project updated, history recorded → GO TO STEP 2

---

### STEP 2: Immediate live effect
**Actor**: PostgreSQL + Django queryset
**Action**: All subsequent requests to `/portfolio/` run `Project.objects.filter(is_published=True)` — the queryset is not cached. Change is visible on the next page load with no further action required.
**Timeout**: N/A (no cache to invalidate)

**Observable states after publish**:
  - Visitor sees: project appears in `/portfolio/` list and detail page is accessible
  - Visitor sees (before publish): project is invisible to all public pages; detail URL returns 404

**Observable states after unpublish**:
  - Visitor sees: project disappears from `/portfolio/` list; detail URL returns 404
  - Operator sees: project still visible in admin with `is_published=False`

---

## State Transitions

```
[is_published=False (draft)]
  -> (publish action or inline toggle) -> [is_published=True (live)]
  -> [no approval gate, no preview — live immediately]

[is_published=True (live)]
  -> (unpublish action or inline toggle) -> [is_published=False (draft)]
  -> [removed from public pages immediately]
```

---

## History Recording

`HistoricalRecords` on `Project` model, using `simple_history`:

| Mechanism | History recorded? |
|---|---|
| Individual admin save (Mechanism C) | Yes — `HistoricalProject` row created |
| Inline list toggle (Mechanism B) | Yes — triggered via `save_model()` |
| Bulk action queryset.update() (Mechanism A) | **No** — bypass, history not created (gap) |

`simple_history.middleware.HistoryRequestMiddleware` captures `request.user` so all history entries are attributed to the correct operator.

---

## Test Cases

| Test | Trigger | Expected behaviour |
|---|---|---|
| TC-01: Publish via bulk action | Select project, "Publish selected", Go | is_published=True, visible on /portfolio/ |
| TC-02: Unpublish via bulk action | Select project, "Unpublish selected", Go | is_published=False, 404 on detail |
| TC-03: Publish via inline toggle | Click checkbox, Save | is_published=True, history recorded |
| TC-04: Unpublish via individual edit | Open project, uncheck is_published, Save | is_published=False, history recorded |
| TC-05: History for bulk action | Bulk publish | HistoricalProject NOT created (known gap) |
| TC-06: History for individual edit | Individual edit publish | HistoricalProject created with user attribution |

---

## Assumptions

| # | Assumption | Risk if wrong |
|---|---|---|
| A1 | No CDN or page-level cache in front of /portfolio/ | If Cloudflare caches pages, unpublish won't take effect until TTL expires or cache is purged |
| A2 | Operator has `change_project` permission | Without it, Django admin blocks all edits |
| A3 | `is_featured` flag is independent of `is_published` | A project can be featured=True but published=False — it won't appear publicly. Confirm template only shows featured published projects on homepage. |

## Open Questions

- Should bulk publish trigger history? If yes: iterate queryset and call `.save()` per instance (slower but records history). If no: document the trade-off explicitly.
- Should there be an approval workflow (draft → review → publish) rather than direct operator control?
- Is there a `cover_image` validation gate before publish is allowed?

## Spec vs Reality Audit Log

| Date | Finding | Action taken |
|---|---|---|
| 2026-06-28 | History not recorded for bulk actions (queryset.update bypass) — gap identified | Documented. Pending decision on whether to fix or accept. |
