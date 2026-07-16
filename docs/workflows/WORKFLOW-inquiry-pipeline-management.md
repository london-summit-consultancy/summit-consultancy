# WORKFLOW: Inquiry Pipeline Management (Admin)

**Version**: 1.0 | **Date**: 2026-06-28 | **Author**: Workflow Architect
**Status**: Approved
**Related**: [[WORKFLOW-inquiry-submission]]

---

## Overview

After an inquiry lands in the database with status `new`, a staff operator works it through a defined 5-state pipeline using the Django admin. State transitions are enforced by `Inquiry.transition_to()` — a guard method that raises `ValueError` on any illegal transition. The admin currently exposes the `status` field as an editable dropdown (not wired to `transition_to()`). This is the primary gap in this workflow.

---

## Actors

| Actor | Role |
|---|---|
| Staff operator | Manages inquiry through the pipeline in Django admin |
| InquiryAdmin | Displays inquiry data; renders status badge; exposes status field |
| Inquiry.transition_to() | Enforces legal state transitions |
| PostgreSQL | Persists state changes |

---

## Prerequisites

- Operator is authenticated as Django staff/superuser
- Inquiry record exists in the database

---

## Trigger

- **User action**: Operator opens an Inquiry in `/admin/inquiries/inquiry/<id>/change/` and edits the `status` field
- **OR**: Operator is given a programmatic way to call `inquiry.transition_to(new_status)`

---

## State Machine

```
                    ┌──────────────┐
  Form submit  ───▶ │     NEW      │
                    └──────┬───────┘
                           │ transition_to("contacted")
                           ▼
                    ┌──────────────┐
                    │  CONTACTED   │
                    └──────┬───────┘
              ┌────────────┴──────────────┐
              │                           │
  transition_to("qualified")  transition_to("lost")
              ▼                           ▼
       ┌────────────┐              ┌──────────────┐
       │  QUALIFIED │              │ CLOSED — LOST│  ← terminal
       └──────┬─────┘              └──────────────┘
     ┌────────┴────────┐
     │                 │
transition_to("won")  transition_to("lost")
     ▼                 ▼
┌──────────┐    ┌──────────────┐
│CLOSED WON│    │ CLOSED — LOST│  ← terminal
└──────────┘    └──────────────┘
(terminal)
```

### Legal transitions enforced by `_ALLOWED_TRANSITIONS`

| From | To (allowed) |
|---|---|
| `new` | `contacted` |
| `contacted` | `qualified`, `lost` |
| `qualified` | `won`, `lost` |
| `won` | *(none — terminal)* |
| `lost` | *(none — terminal)* |

Any other transition raises `ValueError("Cannot transition from ... to ...")`.

---

## Critical Gap — Admin Bypass

**The Django admin `status` field is an editable dropdown that calls `inquiry.save()` directly, bypassing `transition_to()` entirely.** An operator can currently set `status = "won"` on a `new` inquiry without going through `contacted` or `qualified`.

**Severity**: High — data integrity risk; pipeline analytics will be incorrect.

**Fix options** (for Backend Architect to implement):
1. Override `InquiryAdmin.save_model()` to call `transition_to()` instead of direct save when status changes.
2. Add a custom admin action "Move to Contacted", "Move to Qualified", etc., that each call `transition_to()`.
3. Make `status` a `readonly_field` in admin and add action buttons (most explicit).

Until fixed, `transition_to()` is only enforced programmatically (e.g., in tests or future API).

---

## Workflow Tree

### STEP 1: Operator opens inquiry
**Actor**: Staff operator + InquiryAdmin
**Action**: GET `/admin/inquiries/inquiry/<id>/change/`
**Observable states**:
  - Operator sees: full inquiry detail with `status_badge` (coloured pill), all fieldsets (Contact, Project, Pipeline, Metadata)
  - The Pipeline fieldset shows: `status` dropdown, `notes` textarea

---

### STEP 2: Operator reads current status and context
**Actor**: Staff operator
**Action**: Reviews `full_name`, `email`, `company`, `buyer_type`, `service`, `project_desc`, `budget_range`, `notes`, `source_page`

---

### STEP 3: Operator updates status
**Actor**: Staff operator
**Action**: Selects new status from dropdown, optionally adds/edits `notes`, clicks "Save"

**Path A — Current behaviour (bypass risk)**:
  - `InquiryAdmin.save_model()` calls `inquiry.save()` directly
  - Any status value is accepted regardless of current state
  - `updated_at` is set by `auto_now=True` on the model

**Path B — Intended behaviour (pending fix)**:
  - `save_model()` detects status change, calls `inquiry.transition_to(new_status)`
  - Illegal transitions raise `ValueError` → admin shows error message, no save
  - Legal transitions write `status` and `updated_at` via `update_fields=["status", "updated_at"]`

---

### STEP 4: Status persisted
**Actor**: PostgreSQL
**Action**: `UPDATE inquiries_inquiry SET status=... WHERE id=...`
**Observable states**:
  - Operator sees: admin success message "Inquiry ... was changed successfully."
  - Status badge on list view updates to new colour and label
  - Database: `inquiry.status` = new value, `updated_at` = now

---

## Observable States per Status

| Status | status_badge colour | Meaning to operator |
|---|---|---|
| `new` | Blue `#2563eb` | Just received, not yet acted on |
| `contacted` | Amber `#d97706` | Initial contact made |
| `qualified` | Green `#16a34a` | Opportunity confirmed, pursuing |
| `won` | Dark green `#15803d` | Project won |
| `lost` | Grey `#6b7280` | Opportunity closed without winning |

---

## Test Cases

| Test | Trigger | Expected behaviour (after fix) |
|---|---|---|
| TC-01: new → contacted | transition_to("contacted") | Status updated, no error |
| TC-02: new → won (illegal) | transition_to("won") | ValueError raised, status unchanged |
| TC-03: new → qualified (illegal) | transition_to("qualified") | ValueError raised |
| TC-04: contacted → qualified | transition_to("qualified") | Status updated |
| TC-05: contacted → lost | transition_to("lost") | Status updated (terminal) |
| TC-06: qualified → won | transition_to("won") | Status updated (terminal) |
| TC-07: won → anything (illegal) | transition_to("contacted") | ValueError raised |
| TC-08: Admin bypass (current) | Admin dropdown new→won | Currently succeeds (bug) |

Tests TC-01 to TC-07 are already covered in `tests/test_inquiries.py::TestInquiryStateMachine`.

---

## Assumptions

| # | Assumption | Risk if wrong |
|---|---|---|
| A1 | Operators are trusted not to abuse the bypass in the short term | Data integrity depends on operator discipline until the fix is shipped |
| A2 | Terminal states (won/lost) intentionally have no exit — no re-open path exists | If a project is incorrectly closed and must be re-opened, there is no workflow path. Manual DB edit would be required. |

## Open Questions

- Should `transition_to()` log the state change to `simple_history`? (Currently only `Project` uses `HistoricalRecords`.)
- Should there be an email/notification to the visitor or staff when status moves to `contacted` or `qualified`?

## Spec vs Reality Audit Log

| Date | Finding | Action taken |
|---|---|---|
| 2026-06-28 | Admin bypass gap discovered — status dropdown calls save() not transition_to() | Documented. Pending fix in Backend Architect task. |
