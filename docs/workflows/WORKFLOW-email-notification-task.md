# WORKFLOW: Email Notification Task (Staff)

**Version**: 1.0 | **Date**: 2026-06-28 | **Author**: Workflow Architect
**Status**: Approved
**Related**: [[WORKFLOW-inquiry-submission]], [[WORKFLOW-email-acknowledgement-task]]

---

## Overview

After an inquiry is saved, the Celery task `send_inquiry_notification` is enqueued. A Celery worker picks it up, fetches the inquiry from the database, renders a plain-text email template, and sends it to the staff notification address (`INQUIRY_NOTIFICATION_EMAIL`). Retries up to 3 times with 60 s delay on any exception. The inquiry record is never modified by this task.

---

## Actors

| Actor | Role |
|---|---|
| Celery worker | Executes the task |
| PostgreSQL | Source of Inquiry data |
| Django email backend | Routes to SES (production) or console (dev) |
| Amazon SES / console | Delivers the email |
| Staff recipient | Receives notification at `INQUIRY_NOTIFICATION_EMAIL` |

---

## Prerequisites

- `inquiry_id` refers to an existing `Inquiry` row
- `INQUIRY_NOTIFICATION_EMAIL` env var set
- `DEFAULT_FROM_EMAIL` env var set
- Email template exists: `inquiries/email/notification.txt`
- Celery worker running and consuming the default queue
- Redis available as Celery broker

---

## Trigger

- **Enqueued by**: `InquiryCreateView.form_valid` → `send_inquiry_notification.delay(inquiry.pk)`
- **Task name**: `apps.inquiries.tasks.send_inquiry_notification`
- **Queue**: default

---

## Workflow Tree

### STEP 1: Fetch inquiry
**Actor**: Celery worker
**Action**: `Inquiry.objects.select_related("service").get(pk=inquiry_id)`
**Timeout**: 5 s (implicit DB query timeout)
**Input**: `inquiry_id: int`
**Output on SUCCESS**: `Inquiry` instance → GO TO STEP 2
**Output on FAILURE**:
  - `FAILURE(DoesNotExist)`: inquiry was deleted after enqueue → `return` (task exits silently, no retry). This is the correct behaviour — no notification needed for a deleted record.
  - `FAILURE(db_error)`: DB connection lost → exception raised → GO TO RETRY

**Observable states**:
  - Operator sees: task in "STARTED" state (Celery Flower / result backend)
  - Database: Inquiry read, not modified

---

### STEP 2: Render email body
**Actor**: Celery worker
**Action**: `render_to_string("inquiries/email/notification.txt", {"inquiry": inquiry})`
**Timeout**: < 100 ms (template render, no I/O)
**Input**: `Inquiry` instance
**Output on SUCCESS**: rendered plain-text string → GO TO STEP 3
**Output on FAILURE**:
  - `FAILURE(TemplateDoesNotExist)`: template file missing → `TemplateDoesNotExist` exception → GO TO RETRY (will keep failing until template is deployed)
  - `FAILURE(TemplateSyntaxError)`: bad template → same — GO TO RETRY (will fail until fixed)

---

### STEP 3: Send email via Django mail
**Actor**: Celery worker → Django email backend
**Action**: `send_mail(subject, body, from_email, [INQUIRY_NOTIFICATION_EMAIL], fail_silently=False)`
**Timeout**: 30 s (SES SMTP call — no explicit timeout set in code; relies on socket default)
**Input**: rendered body, subject string
**Output on SUCCESS**: email delivered to SES → GO TO TERMINAL (task SUCCESS)
**Output on FAILURE**:
  - `FAILURE(SMTPException / ConnectionError)`: SES unavailable, bad credentials, or connection refused → exception raised → GO TO RETRY
  - `FAILURE(timeout)`: socket hangs > 30 s → same → GO TO RETRY

---

### RETRY
**Triggered by**: any exception from Steps 1–3 (except `Inquiry.DoesNotExist`)
**Mechanism**: `self.retry(exc=exc)` with `max_retries=3`, `default_retry_delay=60` (seconds)
**Attempts**: original + 3 retries = 4 total attempts
**Back-off**: fixed 60 s (not exponential)
**After max retries exceeded**: task moves to FAILURE state in Celery result backend; exception propagated

**Observable states**:
  - Operator sees (Celery Flower): task in RETRY state, retry countdown
  - Staff recipient: no email during retries
  - Logs: `[celery.app.trace] Task apps.inquiries.tasks.send_inquiry_notification[<uuid>] retry: Retry in 60s`

---

## State Transitions

```
[task PENDING in Redis queue]
  -> (worker picks up, inquiry exists, render OK, SES OK) -> [task SUCCESS]
  -> (worker picks up, Inquiry.DoesNotExist) -> [task SUCCESS (silent exit)]
  -> (worker picks up, any error, retries < 3) -> [task RETRY, wait 60s]
  -> (worker picks up, any error, retries == 3) -> [task FAILURE]
```

---

## Cleanup Inventory

This task creates no resources. On failure, the only consequence is staff not receiving the notification email. The Inquiry record is unaffected.

---

## Critical Gaps

**CG-1 (Medium)**: No explicit socket timeout on `send_mail`. A hung SMTP connection will block the worker thread until the OS TCP timeout (~minutes), delaying other tasks. **Fix**: Set `EMAIL_TIMEOUT` in Django settings (available in Django 5+).

**CG-2 (Low)**: Fixed 60 s retry delay. If SES is down for > 4 minutes, all 3 retries fail. Exponential backoff (60, 120, 240 s) would be more resilient.

**CG-3 (Low)**: `select_related("service")` in Step 1 is correct. The `notification.txt` template must reference `inquiry.service.name` carefully since `service` can be NULL (FK with `null=True`). Template must guard: `{% if inquiry.service %}{{ inquiry.service.name }}{% endif %}`.

---

## Test Cases

| Test | Trigger | Expected behaviour |
|---|---|---|
| TC-01: Happy path | Valid inquiry_id, SES up | Email sent to INQUIRY_NOTIFICATION_EMAIL, task SUCCESS |
| TC-02: Inquiry deleted | DoesNotExist | Task exits silently, task SUCCESS (no retry) |
| TC-03: SES failure retry | SMTPException on first attempt | Task retried, SUCCESS on attempt 2 |
| TC-04: SES down all retries | SMTPException × 4 | Task FAILURE after 4 attempts |
| TC-05: Template missing | TemplateDoesNotExist | Task RETRY × 3 → FAILURE |
| TC-06: Service is NULL | inquiry.service = None | Email still sends (template must handle null service gracefully) |

---

## Assumptions

| # | Assumption | Risk if wrong |
|---|---|---|
| A1 | `EMAIL_BACKEND` is SES in production | If misconfigured, emails go nowhere or fail silently |
| A2 | Celery worker is always running | If no worker is consuming, tasks stay in Redis queue indefinitely |
| A3 | `notification.txt` template handles null `inquiry.service` | If template does `{{ inquiry.service.name }}` without guard, TemplateError on NULL service |

## Spec vs Reality Audit Log

| Date | Finding | Action taken |
|---|---|---|
| 2026-06-28 | Initial spec — code matches | — |
| 2026-06-28 | No EMAIL_TIMEOUT set in settings (CG-1) | Noted, not yet fixed |
