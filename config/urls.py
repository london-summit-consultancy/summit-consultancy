from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.decorators.cache import cache_page

from apps.core.sitemaps import ProjectSitemap, ServiceSitemap, StaticSitemap

admin.site.site_header = settings.ADMIN_SITE_HEADER
admin.site.site_title = settings.ADMIN_SITE_TITLE

# Custom 500 handler: renders with the request so the `site` context processor
# runs (base.html's |default:site.* filter args would otherwise raise on the
# context-less default handler). 404 uses Django's default (context processors
# already run there).
handler500 = "apps.core.views.server_error"

sitemaps = {
    "services": ServiceSitemap,
    "portfolio": ProjectSitemap,
    "static": StaticSitemap,
}

urlpatterns = [
    path("admin/", admin.site.urls),
    # Staff-only authentication (django-allauth: email/password + Google SSO).
    path("accounts/", include("allauth.urls")),
    # Staff-only tender tool. The /internal/ prefix flags "no public access" to
    # developers and any future WAF rule; every view is login + is_staff gated.
    path("internal/", include("apps.tenders.urls", namespace="tenders")),
    path("", include("apps.core.urls", namespace="core")),
    path("services/", include("apps.services.urls", namespace="services")),
    path("portfolio/", include("apps.portfolio.urls", namespace="portfolio")),
    path("contact/", include("apps.inquiries.urls", namespace="inquiries")),
    path(
        "sitemap.xml",
        cache_page(86400)(sitemap),
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
]

if settings.DEBUG or getattr(settings, "SERVE_MEDIA", False):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
