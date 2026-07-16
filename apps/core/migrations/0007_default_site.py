from django.conf import settings
from django.db import migrations


def set_default_site(apps, schema_editor) -> None:
    # django.contrib.sites is now installed (required by allauth); point the
    # default Site at the real host so sitemap.xml keeps emitting correct URLs
    # instead of the framework default "example.com".
    Site = apps.get_model("sites", "Site")
    Site.objects.update_or_create(
        id=getattr(settings, "SITE_ID", 1),
        defaults={
            "domain": getattr(settings, "SITE_DOMAIN", "localhost:8000"),
            "name": getattr(settings, "SITE_NAME", "Pioneer Consultants"),
        },
    )


def noop(apps, schema_editor) -> None:
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0006_user"),
        ("sites", "0001_initial"),
    ]

    operations = [migrations.RunPython(set_default_site, noop)]
