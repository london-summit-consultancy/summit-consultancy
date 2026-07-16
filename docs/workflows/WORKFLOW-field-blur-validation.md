# WORKFLOW: HTMX Field Blur Validation

**Version**: 1.0 | **Date**: 2026-06-28 | **Author**: Workflow Architect
**Status**: Approved
**Related**: [[WORKFLOW-inquiry-submission]]

---

## Overview

When a visitor leaves (blurs) a form field on the contact page, HTMX fires a POST to `/contact/validate/` carrying only that one field's name and value. The server instantiates a partial `InquiryForm`, runs validation, and returns the error string for that field (or empty string if valid). HTMX then swaps the error target element next to the field. This enables real-time inline validation without a full form submission.

---

## Actors

| Actor | Role |
|---|---|
| Visitor's browser (HTMX) | Fires POST on field `blur` event |
| InquiryValidateView | Validates the single field, returns error or `""` |
| InquiryForm | Validates the partial data set |

---

## Prerequisites

- HTMX loaded in page (`<script src="…/htmx.org@2.0.4" …>`)
- `HX-Request: true` header present (HTMX adds automatically)
- `InquiryForm.Meta.fields` includes the field being validated
- The field must not be `website` (honeypot — excluded from `_allowed_fields`)

---

## Trigger

- **User action**: Focus leaves an input field on `inquiries/contact.html`
- **Endpoint**: `POST /contact/validate/`
- **Payload**: `{<field_name>: <field_value>}` — single key/value pair

---

## Workflow Tree

### STEP 1: Identify the field
**Actor**: `InquiryValidateView.post`
**Action**: Iterates `request.POST` keys to find the first key that is in `_allowed_fields` (i.e., `InquiryForm.Meta.fields` minus `website`). If no valid field key is found, returns `HttpResponse("")` immediately.
**Timeout**: < 1 ms
**Input**: `request.POST` dict
**Output on SUCCESS**: `field_name` identified → GO TO STEP 2
**Output on FAILURE**:
  - `FAILURE(unknown_field)`: no key matches `_allowed_fields` → returns `HttpResponse("")`, 200; HTMX target is cleared silently

**Observable states**:
  - Visitor sees: nothing changes (empty response clears any prior error)

---

### STEP 2: Partial form validation
**Actor**: `InquiryValidateView.post`
**Action**: Creates `InquiryForm(data={field_name: value})` with only the single field. Calls `form.is_valid()` (expected to be `False` since other required fields are absent). Reads `form.errors.get(field_name, [""])[0]` for the first error message for that field.
**Timeout**: < 20 ms (no DB, no I/O — pure Python validation)
**Input**: `{field_name: value}`
**Output on SUCCESS (field is valid)**: `error == ""` → GO TO STEP 3 (return empty string)
**Output on FAILURE (field is invalid)**: `error != ""` → GO TO STEP 3 (return error string)

> Note: `form.is_valid()` is called knowing it returns `False` (other required fields are missing). This is intentional — only the error for the specific field is extracted, not the full error set.

**Observable states**:
  - No DB reads or writes
  - No Celery tasks

---

### STEP 3: Return response
**Actor**: `InquiryValidateView.post`
**Action**: Returns `HttpResponse(error)` — plain text, 200. HTMX swaps the response into the error `<span>` adjacent to the field. Empty response clears any existing error.
**Output**: HTTP 200, body = error string or `""`

**Observable states**:
  - Visitor sees: error message appears beneath the field, or existing error clears
  - Database: unchanged
  - Logs: nothing

---

## State Transitions

```
[field blurred]
  -> (field in _allowed_fields, value invalid) -> [error shown under field]
  -> (field in _allowed_fields, value valid)   -> [error cleared under field]
  -> (field not in _allowed_fields)            -> [no change — empty response]
  -> (field is "website" honeypot)             -> [excluded from _allowed_fields — empty response]
```

---

## Critical Design Note

`InquiryValidateView` is intentionally **HTMX-only**. There is no non-HTMX fallback because:
1. It returns a plain text fragment, not a renderable page.
2. Non-HTMX form submission gets full validation from `InquiryCreateView.form_invalid`.
3. Direct access to `/contact/validate/` without HTMX is harmless (returns empty or an error string).

There is no `@ratelimit` on this endpoint. A determined attacker could hammer it. See Assumptions A1.

---

## Test Cases

| Test | Trigger | Expected behaviour |
|---|---|---|
| TC-01: Valid email | POST `{"email": "valid@example.com"}` | 200, body `""` |
| TC-02: Invalid email | POST `{"email": "not-an-email"}` | 200, body contains error string |
| TC-03: Empty required field | POST `{"full_name": ""}` | 200, body contains "This field is required." |
| TC-04: Honeypot field | POST `{"website": "http://spam.com"}` | 200, body `""` (excluded) |
| TC-05: Unknown field key | POST `{"nonexistent_field": "value"}` | 200, body `""` |
| TC-06: Multiple keys | POST `{"email": "bad", "full_name": "ok"}` | 200, error for whichever key is first in _allowed_fields |

---

## Assumptions

| # | Assumption | Risk if wrong |
|---|---|---|
| A1 | No ratelimit on /contact/validate/ | Attacker could enumerate valid emails by watching for empty vs non-empty responses. Low risk for this use case (no auth). |
| A2 | `InquiryForm.Meta.fields` is the authoritative field list | If fields are added to the form but not Meta.fields, they won't be validatable via this endpoint |
| A3 | Only the first matching key from POST is used | HTMX always sends one key per blur; a crafted multi-key POST would only validate the first recognised field |

## Spec vs Reality Audit Log

| Date | Finding | Action taken |
|---|---|---|
| 2026-06-28 | Initial spec — code matches spec exactly | — |
