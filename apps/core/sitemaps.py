from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.portfolio.models import Project
from apps.services.models import Service


class ServiceSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.8

    def items(self):
        return Service.objects.all()

    def location(self, obj) -> str:
        return obj.get_absolute_url()


class ProjectSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return Project.objects.filter(is_published=True)

    def location(self, obj) -> str:
        return obj.get_absolute_url()

    def lastmod(self, obj):
        return obj.updated_at


class StaticSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.5

    def items(self) -> list[str]:
        return [
            "core:home",
            "core:about",
            "services:landing",
            "portfolio:list",
            "inquiries:contact",
        ]

    def location(self, item) -> str:
        return reverse(item)
