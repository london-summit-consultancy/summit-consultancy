from django.core.cache import cache

from .models import SiteSettings


def get_site_settings() -> SiteSettings:
    """Cached singleton accessor shared by the context processor and views, so a
    page reading a SiteSettings-driven meta description costs no extra query."""
    site = cache.get("site_settings")
    if site is None:
        site = SiteSettings.load()
        cache.set("site_settings", site, 3600)
    return site


def site_settings(request) -> dict:
    return {"site": get_site_settings()}
