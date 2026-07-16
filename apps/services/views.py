from django.template.response import TemplateResponse
from django.views.generic import DetailView, TemplateView

from apps.core.context_processors import get_site_settings

from .models import Service, ServiceCategory


class ServicesLandingView(TemplateView):
    template_name = "services/landing.html"

    def get(self, request, *args, **kwargs):
        buyer = request.GET.get("buyer", "")
        qs = ServiceCategory.objects.prefetch_related("services").order_by("display_order")
        if buyer:
            qs = qs.filter(buyer_type=buyer)
        ctx = {
            "categories": qs,
            "selected_buyer": buyer,
            "all_categories": ServiceCategory.objects.order_by("display_order"),
            "page_title": "Our Services",
            "page_meta_desc": get_site_settings().services_meta_description,
        }
        if request.htmx:
            return TemplateResponse(request, "partials/_service_list.html", ctx)
        return TemplateResponse(request, self.template_name, ctx)


class ServiceDetailView(DetailView):
    model = Service
    template_name = "services/detail.html"
    queryset = Service.objects.select_related("category").prefetch_related("projects")

    def get_context_data(self, **kwargs) -> dict:
        ctx = super().get_context_data(**kwargs)
        ctx["related_projects"] = self.object.projects.filter(is_published=True).order_by("-year")[
            :4
        ]
        ctx["page_title"] = self.object.effective_meta_title
        ctx["page_meta_desc"] = self.object.effective_meta_desc
        return ctx
