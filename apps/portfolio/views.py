from django.template.response import TemplateResponse
from django.views.generic import DetailView, TemplateView

from apps.core.context_processors import get_site_settings
from apps.services.models import Service

from .models import Project, Sector


class PortfolioListView(TemplateView):
    template_name = "portfolio/list.html"

    def _get_queryset(self):
        qs = (
            Project.objects.filter(is_published=True)
            .prefetch_related("services_used")
            .order_by("-year", "display_order")
        )
        sector = self.request.GET.get("sector", "")
        service = self.request.GET.get("service", "")
        if sector:
            qs = qs.filter(sector=sector)
        if service:
            qs = qs.filter(services_used__slug=service).distinct()
        return qs

    def get(self, request, *args, **kwargs):
        ctx = {
            "projects": self._get_queryset(),
            "sectors": Sector.choices,
            "services": Service.objects.order_by("name"),
            "selected_sector": request.GET.get("sector", ""),
            "selected_service": request.GET.get("service", ""),
            "page_title": "Portfolio",
            "page_meta_desc": get_site_settings().portfolio_meta_description,
        }
        if request.htmx:
            return TemplateResponse(request, "partials/_project_cards.html", ctx)
        return TemplateResponse(request, self.template_name, ctx)


class ProjectDetailView(DetailView):
    model = Project
    template_name = "portfolio/detail.html"
    queryset = Project.objects.filter(is_published=True).prefetch_related("images", "services_used")

    def get_context_data(self, **kwargs) -> dict:
        ctx = super().get_context_data(**kwargs)
        ctx["related"] = (
            Project.objects.filter(is_published=True, sector=self.object.sector)
            .exclude(pk=self.object.pk)
            .order_by("-year")[:3]
        )
        ctx["page_title"] = self.object.title
        ctx["page_meta_desc"] = self.object.summary
        return ctx
