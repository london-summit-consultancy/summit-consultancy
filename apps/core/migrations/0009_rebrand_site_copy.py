# Rebrand: Pioneer Consultants -> London Summit Consultancy Limited.
#
# 0005 backfilled the old copy onto the SiteSettings singleton, so existing
# databases carry the Pioneer literals as data. Each swap below only fires when
# the current value still equals the old literal — admin-edited copy is never
# overwritten. Reversible for parity with 0005.

from django.core.cache import cache
from django.db import migrations

OLD_BRAND_NAME = "Pioneer Consultants"
NEW_BRAND_NAME = "London Summit Consultancy"

# old literal (from 0005_backfill_site_copy) -> London Summit replacement
_REBRAND = {
    "brand_name": (OLD_BRAND_NAME, NEW_BRAND_NAME),
    "footer_location_text": (
        "Serving clients across the West Midlands and surrounding areas.",
        "Serving clients across London and the Gulf region.",
    ),
    "about_meta_description": (
        "Learn about Pioneer Consultants — an independent construction consultancy "
        "delivering project, cost, and commercial expertise from concept to completion.",
        "Learn about London Summit Consultancy — an independent construction consultancy "
        "delivering project, cost, and commercial expertise from concept to completion.",
    ),
    "services_meta_description": (
        "Pioneer Consultants offers specialist construction consultancy services — "
        "project management, cost consultancy, and commercial advisory for clients, "
        "contractors, and consultancies.",
        "London Summit Consultancy offers specialist construction consultancy services — "
        "project management, cost consultancy, and commercial advisory for clients, "
        "contractors, and consultancies.",
    ),
    "portfolio_meta_description": (
        "Browse Pioneer Consultants' project portfolio — "
        "infrastructure and construction case studies across the West Midlands.",
        "Browse London Summit Consultancy's project portfolio — "
        "infrastructure and construction case studies across London and the Gulf region.",
    ),
}


def _swap(apps, old_index: int, new_index: int, old_name: str, new_name: str) -> None:
    SiteSettings = apps.get_model("core", "SiteSettings")
    obj = SiteSettings.objects.filter(pk=1).first()
    if obj is not None:
        changed = False
        for field, values in _REBRAND.items():
            if getattr(obj, field) == values[old_index]:
                setattr(obj, field, values[new_index])
                changed = True
        if changed:
            obj.save()

    Site = apps.get_model("sites", "Site")
    Site.objects.filter(name=old_name).update(name=new_name)

    # The context processor caches the singleton for an hour; drop it so the
    # rebrand is visible immediately after deploy.
    cache.delete("site_settings")


def rebrand(apps, schema_editor) -> None:
    _swap(apps, 0, 1, OLD_BRAND_NAME, NEW_BRAND_NAME)


def unrebrand(apps, schema_editor) -> None:
    _swap(apps, 1, 0, NEW_BRAND_NAME, OLD_BRAND_NAME)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0008_alter_sitesettings_brand_name"),
        ("sites", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(rebrand, unrebrand),
    ]
