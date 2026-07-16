# WORKFLOW: Email Acknowledgement Task (Visitor)

**Version**: 1.0 | **Date**: 2026-06-28 | **Author**: Workflow Architect
**Status**: Approved
**Related**: [[WORKFLOW-inquiry-submission]], [[WORKFLOW-email-notification-task]]

---

## Overview

Parallel to the staff notification, `send_inquiry_acknowledgement` is enqueued immediately after inquiry save. A Celery worker sends a "we received your enquiry" confirmation email to the visitor's own email address. Retries up to 3 times with 60 s delay on any exception.

---

## Actors

| Actor | Role |
|---|---|
| Celery worker | Executes the task |
| PostgreSQL | Source of Inquiry data (specifically `inquiry.email`) |
| Django email backend | Routes to SES (production) or console (dev) |
| Amazon SES / console | Delivers the email |
| Visitor | Receives confirmation at `inquiry.email` |

---

## Prerequisites

- `inquiry_id` refers to an existing `Inquiry` row
- `inquiry.email` is a valid email address (validated at form submission)
- `DEFAULT_FROM_EMAIL` env var set
- Email template exists: `inquiries/email/acknowledgement.txt`
- Celery worker running; Redis available

---

## Trigger

- **Enqueued by**: `InquiryCreateView.form_valid` → `send_inquiry_acknowledgement.delay(inquiry.pk)`
- **Task name**: `apps.inquiries.tasks.send_inquiry_acknowledgement`
- **Queue**: default
- **Concurrency note**: Both this task and `send_inquiry_notification` are enqueued in the same view call. They run independently — neither waits for the other.

---

## Workflow Tree

### STEP 1: Fetch inquiry
**Actor**: Celery worker
**Action**: `Inquiry.objects.get(pk=inquiry_id)` — no `select_related` (acknowledgement template only needs top-level inquiry fields)
**Timeout**: 5 s
**Input**: `inquiry_id: int`
**Output on SUCCESS**: `Inquiry` instance → GO TO STEP 2
**Output on FAILURE**:
  - `FAILURE(DoesNotExist)`: record deleted → `return` (silent exit, no retry)
  - `FAILURE(db_error)`: → GO TO RETRY

---

### STEP 2: Render email body
**Actor**: Celery worker
**Action**: `render_to_string("inquiries/email/acknowledgement.txt", {"inquiry": inquiry})`
**Timeout**: < 100 ms
**Output on SUCCESS**: rendered body → GO TO STEP 3
**Output on FAILURE**:
  - `FAILURE(TemplateDoesNotExist / SyntaxError)`: → GO TO RETRY

---

### STEP 3: Send email to visitor
**Actor**: Celery worker → Django email backend
**Action**: `send_mail(subject, body, from_email, [inquiry.email], fail_silently=False)`
**Subject**: `"We received your enquiry — Pioneer Consultants"`
**Timeout**: 30 s (socket default — no explicit timeout)
**Output on SUCCESS**: email sent → task SUCCESS
**Output on FAILURE**:
  - `FAILURE(SMTPException / timeout)`: → GO TO RETRY

---

### RETRY
**Mechanism**: `self.retry(exc=exc)`, `max_retries=3`, `default_retry_delay=60`
**After max retries**: task FAILURE; visitor never receives acknowledgement

---

## State Transitions

```
[task PENDING in Redis]
  -> (inquiry exists, render OK, SES OK) -> [task SUCCESS, visitor email sent]
  -> (DoesNotExist)                       -> [task SUCCESS, silent exit]
  -> (any error, retries < 3)             -> [task RETRY, 60s wait]
  -> (any error, retries == 3)            -> [task FAILURE, visitor gets no email]
```

---

## Difference from Notification Task

| Aspect | send_inquiry_notification | send_inquiry_acknowledgement |
|---|---|---|
| Recipient | `INQUIRY_NOTIFICATION_EMAIL` (staff) | `inquiry.email` (visitor) |
| Template | `notification.txt` | `acknowledgement.txt` |
| select_related | Yes (`"service"`) | No |
| Failure impact | Staff unaware of new inquiry | Visitor gets no confirmation |

---

## Cleanup Inventory

No resources created. On failure, visitor has no email confirmation but the inquiry record exists in the database — staff can follow up manually.

---

## Test Cases

| Test | Trigger | Expected behaviour |
|---|---|---|
| TC-01: Happy path | Valid inquiry_id, SES up | Confirmation email sent to inquiry.email |
| TC-02: Inquiry deleted | DoesNotExist | Task exits silently, SUCCESS |
| TC-03: SES transient failure | SMTPException once | Retried, SUCCESS on attempt 2 |
| TC-04: SES down all attempts | SMTPException × 4 | task FAILURE, visitor gets no email |

---

## Assumptions

| # | Assumption | Risk if wrong |
|---|---|---|
| A1 | `inquiry.email` is always a valid deliverable address | Visitor could enter a valid-format but non-existent address; SES would bounce. No bounce handling exists. |
| A2 | Both tasks are enqueued independently | If worker concurrency is 1 and notification task is slow, acknowledgement waits — but this is an ordering concern, not a correctness concern |

## Spec vs Reality Audit Log

| Date | Finding | Action taken |
|---|---|---|
| 2026-06-28 | Initial spec — code matches | — |
