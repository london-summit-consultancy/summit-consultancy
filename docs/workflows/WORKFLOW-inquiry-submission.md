# WORKFLOW: Inquiry Submission

**Version**: 1.0 | **Date**: 2026-06-28 | **Author**: Workflow Architect
**Status**: Approved
**Related**: [[WORKFLOW-email-notification-task]], [[WORKFLOW-email-acknowledgement-task]], [[WORKFLOW-field-blur-validation]]

---

## Overview

A website visitor fills in the contact form at `/contact/` and submits their enquiry. The server validates the form, discards honeypot-triggered spam silently, persists the record, enqueues two Celery email tasks (staff notification + visitor acknowledgement), and returns either an HTMX success partial or a full-page redirect. The entire synchronous path must complete within 5 s; email delivery is fully async.

---

## Actors

| Actor | Role |
|---|---|
| Visitor | Submits the HTML form (with or without JS/HTMX) |
| django-ratelimit | Enforces 5 POSTs/hour/IP; blocks excess requests at 429 |
| InquiryCreateView | Validates form, detects honeypot, persists, enqueues tasks |
| PostgreSQL | Persists the Inquiry record |
| Redis | Backs rate-limit counter, Celery broker queue |
| Celery worker | Executes email tasks asynchronously |
| Amazon SES | Delivers emails (production); console backend (dev) |

---

## Prerequisites

- PostgreSQL running and `pioneer` DB accessible
- Redis running (rate-limit counters + Celery broker)
- `services.Service` and `services.ServiceCategory` records loaded (fixture `services_seed`) — used to populate the service dropdown in `get_context_data`
- `INQUIRY_NOTIFICATION_EMAIL` env var set
- `DEFAULT_FROM_EMAIL` env var set

---

## Trigger

- **User action**: Visitor clicks "Send" on `inquiries/contact.html`
- **Endpoint**: `POST /contact/`
- **Content-Type**: `application/x-www-form-urlencoded`
- **HTMX variant**: request carries `HX-Request: true` header

---

## Workflow Tree

### STEP 1: Rate-limit check
**Actor**: django-ratelimit (decorator on `InquiryCreateView.post`)
**Action**: Counts POST requests from this IP in the last hour using Redis. Blocks if count ≥ 5.
**Timeout**: < 10 ms (Redis lookup)
**Input**: `request.META["REMOTE_ADDR"]`
**Output on SUCCESS**: count < 5 → GO TO STEP 2
**Output on FAILURE**:
  - `FAILURE(rate_limit_exceeded)`: count ≥ 5 → HTTP 429 returned by django-ratelimit; `Ratelimited` exception raised; no DB write; no cleanup needed

**Observable states**:
  - Visitor sees: HTTP 429 page ("Too Many Requests")
  - Operator sees: nothing (no record created)
  - Database: unchanged
  - Logs: `[django-ratelimit] ratelimited ip=<ip>`

---

### STEP 2: Form validation
**Actor**: `InquiryCreateView.form_valid` / `form_invalid`
**Action**: Django validates `InquiryForm` against POST data. Required fields: `full_name`, `email`, `project_desc`. Optional: `phone`, `company`, `buyer_type`, `service`, `budget_range`. Honeypot: `website` (hidden, must be empty).
**Timeout**: < 50 ms (pure Python)
**Input**: POST body
**Output on SUCCESS**: `form.is_valid() == True` → GO TO STEP 3
**Output on FAILURE**:
  - `FAILURE(validation_error)`: missing/invalid required fields
    - **HTMX path**: returns `TemplateResponse("partials/_inquiry_form.html", {"form": form}, status=422)` — HTMX replaces form with inline errors
    - **Non-HTMX path**: returns `super().form_invalid(form)` — full page re-render at 200 with inline errors
    - No DB write; no cleanup needed

**Observable states**:
  - Visitor sees: inline field errors highlighted under each invalid field
  - Operator sees: nothing (no record)
  - Database: unchanged
  - Logs: nothing (expected user error)

---

### STEP 3: Honeypot check
**Actor**: `InquiryCreateView.form_valid`
**Action**: Checks `inquiry.website` field value (hidden field, never filled by real users). If non-empty, the request is a bot.
**Timeout**: < 1 ms
**Input**: `form.cleaned_data["website"]`
**Output on SUCCESS**: `website == ""` → GO TO STEP 4
**Output on FAILURE (bot detected)**:
  - `inquiry.website` is non-empty → silently discard; respond as if success to avoid leaking detection:
    - **HTMX path**: return `TemplateResponse("partials/_inquiry_success.html", {})` — 200
    - **Non-HTMX path**: `redirect("inquiries:sent")` — 302
  - No DB write; no cleanup needed

**Observable states**:
  - Visitor (bot) sees: success page — bot learns nothing
  - Operator sees: nothing (no record created)
  - Database: unchanged
  - Logs: *(gap — no logging of detected spam — see Assumptions A3)*

---

### STEP 4: Persist inquiry
**Actor**: `InquiryCreateView.form_valid` → `inquiry.save()`
**Action**: Enriches the unsaved model instance with `source_page` (HTTP_REFERER) and `ip_address` (REMOTE_ADDR), then calls `inquiry.save()`. Initial `status` is `InquiryStatus.NEW`.
**Timeout**: < 200 ms (DB write, single row)
**Input**: Validated form data + request metadata
**Output on SUCCESS**: `Inquiry` row created with `pk`, `status="new"`, `created_at` set → GO TO STEP 5
**Output on FAILURE**:
  - `FAILURE(db_error)`: PostgreSQL unavailable or constraint violation → unhandled exception → Django 500 response. No cleanup (no row was written). **This is a gap — no try/except wraps save(). See Assumptions A4.**

**Observable states**:
  - Visitor sees: loading state (spinner on HTMX, no feedback on non-HTMX)
  - Operator sees: nothing yet (Celery not yet enqueued)
  - Database: `inquiries_inquiry` row inserted, `status="new"`
  - Logs: Django SQL debug log (if `DEBUG=True`)

---

### STEP 5: Enqueue email tasks
**Actor**: `InquiryCreateView.form_valid`
**Action**: Calls `send_inquiry_notification.delay(inquiry.pk)` then `send_inquiry_acknowledgement.delay(inquiry.pk)`. Both are enqueued to Redis Celery broker. The view does NOT await completion.
**Timeout**: < 50 ms (two Redis LPUSH operations)
**Input**: `inquiry.pk`
**Output on SUCCESS**: Both tasks queued in Redis → GO TO STEP 6
**Output on FAILURE**:
  - `FAILURE(redis_unavailable)`: Redis is down → `send_inquiry_notification.delay()` raises `OperationalError` → unhandled exception → Django 500. **Gap: inquiry is already saved but emails never sent. No retry or fallback. See Assumptions A5.**

**Observable states**:
  - Visitor sees: still loading
  - Operator sees: nothing yet
  - Database: Inquiry row exists
  - Logs: Celery `task_received` log entry (if worker is running)

---

### STEP 6: Return success response
**Actor**: `InquiryCreateView.form_valid`
**Action**: Returns success response based on HTMX detection.
  - **HTMX path**: `TemplateResponse("partials/_inquiry_success.html", {})` — 200; HTMX swaps the form area with a thank-you partial
  - **Non-HTMX path**: `redirect("inquiries:sent")` — 302 to `/contact/sent/` → `InquirySuccessView` renders `inquiries/sent.html`
**Timeout**: < 10 ms
**Output**: HTTP 200 (HTMX) or 302 (non-HTMX)

**Observable states**:
  - Visitor sees: "Thank you — we'll be in touch" success message
  - Operator sees: new inquiry row visible in Django admin
  - Database: Inquiry row exists with `status="new"`
  - Logs: `GET /contact/sent/` (non-HTMX) or nothing (HTMX)

---

## State Transitions

```
[form displayed]
  -> (POST received, rate limit OK, form valid, not honeypot, DB write OK, enqueue OK)
  -> [inquiry.status = "new"] → STEP 6 success response

[form displayed]
  -> (POST received, rate limit exceeded) -> [HTTP 429, no record]

[form displayed]
  -> (POST received, form invalid) -> [form re-displayed with errors, no record]

[form displayed]
  -> (POST received, honeypot filled) -> [success response shown, no record]
```

---

## Handoff Contracts

### InquiryCreateView → Celery broker (Redis)

**Task name**: `apps.inquiries.tasks.send_inquiry_notification`
**Enqueue call**: `.delay(inquiry_id: int)`
**Payload stored in Redis**: `{"args": [<inquiry_id>], "kwargs": {}}`
**No synchronous response expected** — fire and forget
**Timeout**: 50 ms for LPUSH to Redis
**On FAILURE (Redis down)**: Unhandled exception → 500. Inquiry already persisted. Gap. See A5.

---

## Cleanup Inventory

| Resource | Created at step | On failure | Destroy method |
|---|---|---|---|
| Inquiry DB row | Step 4 | Steps 5-6 fail: row exists, emails missing | Manual admin delete or future retry job |
| Rate-limit counter (Redis) | Step 1 | N/A | TTL-based (1hr) |
| Celery task entries (Redis) | Step 5 | N/A | Consumed by worker |

> No ABORT_CLEANUP path exists — on Step 5 failure, the Inquiry row is orphaned without email notifications. This is the highest-severity gap in this workflow.

---

## Test Cases

| Test | Trigger | Expected behaviour |
|---|---|---|
| TC-01: Happy path (non-HTMX) | Valid POST, all services up | 302 to /contact/sent/, Inquiry created, 2 Celery tasks enqueued |
| TC-02: Happy path (HTMX) | Valid POST + `HX-Request: true` | 200, `_inquiry_success.html` partial returned, Inquiry created |
| TC-03: Rate limit exceeded | 6th POST from same IP within 1hr | 429, no Inquiry created |
| TC-04: Validation failure (HTMX) | Empty required fields + `HX-Request: true` | 422, `_inquiry_form.html` with errors returned |
| TC-05: Validation failure (non-HTMX) | Empty required fields | 200 (form page), inline errors, no Inquiry created |
| TC-06: Honeypot filled (HTMX) | `website` field non-empty + `HX-Request: true` | 200, success partial, no Inquiry created |
| TC-07: Honeypot filled (non-HTMX) | `website` field non-empty | 302 to /contact/sent/, no Inquiry created |
| TC-08: Service dropdown populates | GET /contact/ | 200, `services` context contains all services ordered by category |

---

## Assumptions

| # | Assumption | Risk if wrong |
|---|---|---|
| A1 | `HTTP_REFERER` is always available for `source_page` | If missing (direct navigation), field stored as `""` — acceptable |
| A2 | `REMOTE_ADDR` is the real visitor IP (no reverse proxy in dev) | In production behind a load balancer, `REMOTE_ADDR` will be the LB IP — ratelimit will be useless. Must set `RATELIMIT_USE_CACHE` and configure `X-Forwarded-For` trust. |
| A3 | Honeypot silently discards with no logging | Operators cannot see spam volume. Low risk operationally but useful for monitoring. |
| A4 | `inquiry.save()` never raises in practice | Constraint violation (e.g., duplicate IP + same second) could produce 500 with no user feedback |
| A5 | Redis is always available when the view runs | If Redis goes down between inquiry save and task enqueue, the inquiry is persisted but email notifications are lost permanently with no recovery path |

## Open Questions

- Should a `signals.post_save` fallback enqueue tasks if `.delay()` raises, to handle Redis downtime?
- Should spam (honeypot) attempts be logged to a separate table or Sentry for monitoring?
- In production, is a WAF or Cloudflare in front? If so, `REMOTE_ADDR` fix for ratelimit is mandatory.

## Spec vs Reality Audit Log

| Date | Finding | Action taken |
|---|---|---|
| 2026-06-28 | Initial spec created from code audit | — |
| 2026-06-28 | Confirmed: no try/except around inquiry.save() (A4 gap) | Noted, not yet fixed |
| 2026-06-28 | Confirmed: no try/except around .delay() calls (A5 gap) | Noted, not yet fixed |
