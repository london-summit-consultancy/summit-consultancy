# WORKFLOW: Site Settings Cache

**Version**: 1.0 | **Date**: 2026-06-28 | **Author**: Workflow Architect
**Status**: Approved

---

## Overview

`SiteSettings` is a singleton model (always `pk=1`) that stores the brand name, contact details, social URLs, and SEO meta description for the site. Because it is needed on every page render (via the `site_settings` context processor), it is cached in Redis with a 1-hour TTL. When an operator updates settings in admin, the `post_save` signal clears the Redis key immediately, forcing a fresh read on the next request.

---

## Actors

| Actor | Role |
|---|---|
| Django request/response cycle | Triggers context processor on every template render |
| `site_settings` context processor | Reads from Redis or DB, injects into template context |
| Redis | Caches the `SiteSettings` instance (key: `"site_settings"`, TTL: 3600 s) |
| `SiteSettings` model | Singleton DB record (`pk=1`) |
| `clear_site_settings_cache` signal | Receives `post_save`, deletes Redis key |
| Admin operator | Updates `SiteSettings` via `/admin/core/sitesettings/` |

---

## Prerequisites

- Redis running and accessible at `REDIS_URL`
- `SiteSettings` row with `pk=1` exists (created on first `SiteSettings.load()` call via `get_or_create`)
- `apps.core.context_processors.site_settings` registered in `TEMPLATES[0]["OPTIONS"]["context_processors"]`

---

## Trigger (Read path)

Every HTTP request that renders a Django template calls all registered context processors.

---

## Workflow Tree — Read Path (per request)

### STEP 1: Cache lookup
**Actor**: `site_settings(request)` context processor
**Action**: `cache.get("site_settings")`
**Timeout**: < 5 ms (Redis GET)
**Output on SUCCESS (cache hit)**: returns cached `SiteSettings` instance → RETURN `{"site": site}` immediately
**Output on FAILURE (cache miss)**: `None` returned → GO TO STEP 2
**Output on FAILURE (Redis down)**: `cache.get()` raises or returns `None` depending on Django cache backend behaviour → falls through to STEP 2 (DB read). Gracefully degraded.

---

### STEP 2: Database read
**Actor**: `site_settings(request)` context processor
**Action**: `SiteSettings.objects.first()`
**Timeout**: < 50 ms
**Output on SUCCESS**: `SiteSettings` instance or `None` (if no row exists)
**Output on FAILURE**: unhandled exception; likely Django 500

**Edge case**: if `SiteSettings` table is empty (fresh install, no fixture), `objects.first()` returns `None`. Templates must guard `{% if site %}` or use `SiteSettings.load()` which uses `get_or_create`.

> **Gap**: The context processor uses `objects.first()`, NOT `SiteSettings.load()`. On a fresh DB, `site` context variable is `None`. Template rendering will fail if it does `{{ site.brand_name }}` without a guard.

---

### STEP 3: Cache the result
**Actor**: `site_settings(request)` context processor
**Action**: `cache.set("site_settings", site, 3600)` — stores for 1 hour
**Timeout**: < 5 ms (Redis SET)
**Output on FAILURE (Redis down)**: silently ignored — next request will miss cache and hit DB again (graceful degradation)

---

## Workflow Tree — Invalidation Path (on admin save)

### STEP 1: Admin saves SiteSettings
**Actor**: Admin operator → `SiteSettings.save()`
**Action**: Operator clicks "Save" in admin. `save()` sets `self.pk = 1` (singleton enforcement) then calls `super().save()`. PostgreSQL writes the row.

---

### STEP 2: post_save signal fires
**Actor**: Django signal dispatcher
**Action**: `clear_site_settings_cache(sender=SiteSettings, ...)` is called synchronously in the same request thread.
**Action**: `cache.delete("site_settings")` — removes the Redis key
**Timeout**: < 5 ms
**Output**: key deleted (or silently ignored if key did not exist)

**On next page request**: cache miss → DB read → fresh data served within 1 request cycle.

---

## State Transitions

```
[cache empty / cold start]
  -> (any page request) -> [DB read, cache populated, TTL=3600s]

[cache populated]
  -> (page request within TTL) -> [cache hit, no DB read]
  -> (TTL expires naturally) -> [cache miss, DB read, re-populated]
  -> (admin saves SiteSettings) -> [cache deleted] -> (next request) -> [DB read, re-populated]

[Redis down]
  -> (any page request) -> [cache.get() returns None, DB read on every request — degraded but functional]
```

---

## Singleton Enforcement

`SiteSettings.save()` always sets `self.pk = 1`:

```python
def save(self, *args, **kwargs) -> None:
    self.pk = 1
    super().save(*args, **kwargs)
```

The admin add view is blocked by `has_add_permission` returning `False` when `SiteSettings.objects.exists()`. The add and delete buttons are hidden for the singleton.

`SiteSettings.load()` uses `get_or_create(pk=1)` — safe to call at any time including on a fresh DB.

---

## Test Cases

| Test | Trigger | Expected behaviour |
|---|---|---|
| TC-01: Cache hit | Second page request after first | No DB query for site_settings |
| TC-02: Cache miss | First request, or after delete | DB query fires, result cached |
| TC-03: Admin save clears cache | Operator updates brand_name, clicks Save | `cache.get("site_settings")` returns None on next check |
| TC-04: Empty DB | No SiteSettings row, `objects.first()` | Returns None; template must handle `{% if site %}` |
| TC-05: Redis down | Redis unavailable | DB read on every request, no crash |
| TC-06: Singleton enforcement | Try to create second SiteSettings | pk forced to 1, existing record updated |

---

## Assumptions

| # | Assumption | Risk if wrong |
|---|---|---|
| A1 | `SiteSettings` row with pk=1 always exists in production | If row missing, `site` is `None` in every template. Fix: call `SiteSettings.load()` in context processor instead of `objects.first()`. |
| A2 | Redis TTL of 3600 s is acceptable for brand/settings changes | If operator updates settings, max 1 hr stale data (but signal invalidation makes this 0 in practice) |
| A3 | `post_save` signal is synchronous and runs in the same thread | Always true for Django signals unless `dispatch_uid` race or disconnect |

## Open Questions

- Should the context processor use `SiteSettings.load()` (get_or_create) instead of `objects.first()` for safety?
- Should the cache TTL be configurable via a settings variable?

## Spec vs Reality Audit Log

| Date | Finding | Action taken |
|---|---|---|
| 2026-06-28 | Context processor uses `objects.first()` not `load()` — gap on fresh DB | Documented. Low risk in production (admin creates singleton on first visit). |
