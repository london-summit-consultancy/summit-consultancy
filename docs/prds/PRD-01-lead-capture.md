# PRD-01: Lead Capture & Inquiry Pipeline

**Status**: Approved — Built (v1 complete; 2 gaps pending fix before launch)
**Author**: Alex (PM) | **Last Updated**: 2026-06-28 | **Version**: 1.1
**Stakeholders**: Eng. Mohammed Bashir (PCL), Backend Engineer, Eng Lead
**Workflow specs**: `docs/workflows/WORKFLOW-inquiry-submission.md`, `WORKFLOW-inquiry-pipeline-management.md`

---

## 1. Problem Statement

PCL has no structured way to capture or track inbound interest. Referrals come in via WhatsApp or email, are tracked in no system, and have no pipeline visibility. Every lead is manual and un-measured.

**Evidence**:
- Zero digital lead intake exists today — all referral-driven
- PCL founder confirmed leads are forgotten when initial contact is not followed up within 48 hours
- No data on where leads originate, what services they need, or how many convert

**Cost of not solving**: Every submitted inquiry that falls through the cracks is lost revenue in a word-of-mouth market where repeat referrals depend on first engagement speed.

---

## 2. Goals & Success Metrics

| Goal | Metric | Baseline | Target | Window |
|---|---|---|---|---|
| Capture structured leads | Form submissions / month | 0 | ≥ 15 | 90 days post-launch |
| Automated response speed | Time from submission to visitor email | — | < 5 min | Launch day |
| Pipeline visibility | % inquiries tracked from new → resolved | 0% | 100% | Ongoing |
| Qualified conversion | Inquiries reaching `qualified` / total | 0% | ≥ 30% | Month 3 |
| Spam protection | Bot submissions reaching DB / total | — | < 1% | Launch day |

---

## 3. Non-Goals

- No CRM integration in v1 — Django admin is the CRM
- No live chat or SMS — email only
- No visitor accounts or inquiry history view for submitters
- No CAPTCHA in v1 — honeypot + ratelimit covers current risk level

---

## 4. User Personas & Stories

### Primary — The Prospect (any of Sarah, Hassan, or Yusuf)

**Story 1**: As a prospect, I want to send an enquiry about a specific service so that I can start a conversation with PCL without making a phone call.

**Acceptance Criteria**:
- [x] Given I fill in name, email, and project description, when I click Send, then I see a confirmation message in place of the form (no page reload)
- [x] Given I submit without required fields, when I click Send, then inline errors appear under each invalid field
- [x] Given I am on a slow connection, then a loading spinner shows during submission
- [x] Given JavaScript is disabled, when I submit the form, then a standard POST redirect to `/contact/sent/` works correctly

**Story 2**: As a prospect, I want to receive an immediate acknowledgement email so that I know my message was received.

**Acceptance Criteria**:
- [x] Given a valid form submission, within 5 minutes I receive a confirmation email from PCL's address
- [x] The email addresses me by name
- [x] If email delivery fails, the system retries up to 3 times

### Primary — PCL Operator (Eng. Mohammed Bashir)

**Story 3**: As a PCL team member, I want to receive an email the moment a new inquiry arrives so that I can follow up within the same day.

**Acceptance Criteria**:
- [x] Within 5 minutes of submission, a notification email arrives at `INQUIRY_NOTIFICATION_EMAIL`
- [x] The email shows the submitter's name, company, service interest, and project description
- [x] If SES delivery fails, the system retries 3 times with 60 s delays

**Story 4**: As a PCL team member, I want to track each lead through a sales pipeline so I can see what's active and what's been resolved.

**Acceptance Criteria**:
- [x] In Django admin, I can see all inquiries with status badges colour-coded by state
- [x] I can filter by status, buyer type, and date range
- [x] I can add internal notes to any inquiry
- [ ] **PENDING FIX (GAP-1)**: Changing status via admin dropdown must enforce the state machine (currently bypassed)

---

## 5. Solution Overview

The inquiry system is a structured HTML form at `/contact/` that:

1. Rate-limits submissions at 5/hour/IP via Redis
2. Detects bot submissions via a honeypot field (`website`) that humans never fill
3. Validates fields server-side with per-field blur validation via HTMX (immediate feedback as the user types)
4. On valid, non-spam submission: saves the inquiry, enqueues two Celery tasks (staff notification + visitor acknowledgement), and returns a success partial fragment in place of the form
5. On invalid submission: re-renders the form fragment with field-level errors (HTTP 422 so HTMX treats it as a content response, not a network error)

The inquiry then enters a 5-state pipeline (`new → contacted → qualified → won/lost`) managed in Django admin, enforced by `Inquiry.transition_to()` — a guard method that raises `ValueError` on illegal state jumps.

**Key design decisions**:
- **HTMX swap, not page reload**: The form lives in `#contact-form` div; success and error both swap the div's content. No full-page navigation for happy or error paths.
- **HTTP 422 for validation errors**: Standard 4xx codes cause HTMX to not swap by default. 422 is used because it unambiguously signals "content with errors" vs. "network/auth failure."
- **Fire-and-forget Celery tasks**: The view never awaits email delivery. Emails are delivered asynchronously. The response to the user is never gated on email success.
- **State machine via `transition_to()`**: Prevents pipeline state from being corrupted by direct DB edits or admin shortcuts.

---

## 6. Technical Considerations

### Data Model

```
Inquiry
├── full_name        CharField(120)
├── email            EmailField
├── phone            CharField(30, blank)
├── company          CharField(120, blank)
├── buyer_type       TextChoices → BuyerType
├── service          FK → Service (SET_NULL, blank)
├── project_desc     TextField  [required]
├── budget_range     CharField(80, blank)
├── website          CharField(200, blank)  ← honeypot
├── status           TextChoices → InquiryStatus [default: NEW]
├── source_page      CharField(200, blank)  ← HTTP_REFERER
├── ip_address       GenericIPAddressField  ← REMOTE_ADDR
├── created_at       DateTimeField(auto_now_add)
├── updated_at       DateTimeField(auto_now)
└── notes            TextField(blank)  ← internal only
```

### State Machine

```
new → contacted → qualified → won
                            → lost
              → lost
```

Any transition not in this graph raises `ValueError`. Terminal states (`won`, `lost`) have no exit.

### Dependencies

| Component | Dependency | Risk |
|---|---|---|
| Rate limiting | Redis (must be running) | Medium — no fallback if Redis is down |
| Task enqueue | Redis Celery broker | Medium — GAP-2: no try/except around .delay() |
| Email delivery | Amazon SES (production) | Medium — SES sandbox limits until production access granted |
| Blur validation | HTMX header detection | Low — always degrades gracefully (full form validation on submit) |

### Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Redis down during inquiry save | Low | Medium | GAP-2 — pending fix: wrap .delay() in try/except |
| SES in sandbox (production) | Medium | High | Request production SES access before launch |
| Admin bypasses state machine | Certain (current behaviour) | Medium | GAP-1 — pending fix: override save_model() |
| IP-based rate limit fails behind load balancer | High in production | Medium | Configure REMOTE_ADDR trust for X-Forwarded-For |

### Open Questions

- [ ] Is `REMOTE_ADDR` reliable in production, or is PCL behind a load balancer/CDN? — Owner: Eng | Deadline: before production deploy
- [ ] Should honeypot detections be logged somewhere for spam monitoring? — Owner: Alex | Deadline: Sprint 6

---

## 7. Launch Plan

| Phase | Audience | Gate |
|---|---|---|
| Alpha (now) | Eng only | Form submits, DB saves, Celery tasks run in CELERY_TASK_ALWAYS_EAGER mode |
| Staging | Eng + Mohammed Bashir | Emails arrive at INQUIRY_NOTIFICATION_EMAIL, acknowledgement arrives at test address, pipeline in admin visible |
| Production | Public | SES production access granted; GAP-1 and GAP-2 fixed; ratelimit IP strategy confirmed |

**Rollback criteria**: If inquiry form errors exceed 1% of submissions (monitor via Sentry), roll back to previous deploy.

---

## 8. Appendix

- Workflow spec: `docs/workflows/WORKFLOW-inquiry-submission.md`
- Pipeline spec: `docs/workflows/WORKFLOW-inquiry-pipeline-management.md`
- Email task specs: `docs/workflows/WORKFLOW-email-notification-task.md`, `docs/workflows/WORKFLOW-email-acknowledgement-task.md`
- Tests: `tests/test_inquiries.py` (10 tests, all passing)
