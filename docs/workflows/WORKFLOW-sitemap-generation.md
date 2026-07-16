# WORKFLOW: Sitemap Generation

**Version**: 1.0 | **Date**: 2026-06-28 | **Author**: Workflow Architect
**Status**: Draft

---

## Overview

Django's built-in sitemap framework serves an XML sitemap at `/sitemap.xml`. Pioneer defines three sitemap classes in `apps/core/sitemaps.py`: static pages (home, about, contact), all services, and all published projects. Search engine crawlers fetch this URL to discover indexable content.

---

## Actors

| Actor | Role |
|---|---|
| Search engine crawler | Requests /sitemap.xml |
| Django sitemaps framework | Renders XML combining all registered sitemaps |
| ServiceSitemap, ProjectSitemap, StaticSitemap | Provide URL lists |
| PostgreSQL | Queried for services and published projects |

---

## Trigger

- **Request**: `GET /sitemap.xml`
- **Configured in**: `config/urls.py` using `django.contrib.sitemaps.views.sitemap`

---

## Workflow Tree

### STEP 1: Receive request
**Actor**: Django URL router
**Action**: Routes `GET /sitemap.xml` to `django.contrib.sitemaps.views.sitemap` with `sitemaps` dict

---

### STEP 2: Build URL list per sitemap class
**Actor**: Django sitemaps framework

**StaticSitemap**:
  - `items()` returns a list of view names: `["core:home", "core:about", "inquiries:contact"]`
  - `location(item)` calls `reverse(item)` → `/`, `/about/`, `/contact/`
  - No DB query

**ServiceSitemap**:
  - `items()` returns `Service.objects.all()` (no published filter — all services are always public)
  - `location(obj)` returns `obj.get_absolute_url()` → `/services/<slug>/`

**ProjectSitemap**:
  - `items()` returns `Project.objects.filter(is_published=True)`
  - `location(obj)` returns `obj.get_absolute_url()` → `/portfolio/<slug>/`

---

### STEP 3: Render XML
**Actor**: Django sitemaps framework
**Action**: Merges all URL lists into a single `<urlset>` XML document
**Timeout**: < 500 ms (two small DB queries + template render)
**Output**: `Content-Type: application/xml`, HTTP 200

---

## Known Gaps

**CG-1**: No `lastmod` or `changefreq` defined on any sitemap class. Search engines will assign default values. For `ProjectSitemap`, setting `lastmod` to `project.created_at` or a future `updated_at` field would help crawl prioritisation.

**CG-2**: No cache on the sitemap endpoint. On a large portfolio, this fires two DB queries on every crawler request. Django's `cache_page` decorator should be applied in `config/urls.py`.

**CG-3**: `ServiceSitemap.items()` returns all services with no filter. If non-public services are ever added, they will appear in the sitemap.

---

## Test Cases

| Test | Trigger | Expected behaviour |
|---|---|---|
| TC-01: Sitemap serves XML | GET /sitemap.xml | 200, Content-Type: application/xml |
| TC-02: Static URLs present | — | /,  /about/, /contact/ in sitemap |
| TC-03: Service URLs present | Service with slug exists | /services/<slug>/ in sitemap |
| TC-04: Published project URLs present | Published project exists | /portfolio/<slug>/ in sitemap |
| TC-05: Unpublished projects excluded | Unpublished project exists | /portfolio/<slug>/ NOT in sitemap |

---

## Spec vs Reality Audit Log

| Date | Finding | Action taken |
|---|---|---|
| 2026-06-28 | Initial spec — code matches; no lastmod/changefreq (noted as gap) | — |
