from django.http import HttpRequest, HttpResponse, HttpResponseServerError
from django.shortcuts import render
from django.views.generic import TemplateView

from apps.portfolio.models import Project, Sector
from apps.services.models import BuyerType, Service

from .context_processors import get_site_settings
from .models import AboutSection, HeroSection, Testimonial


class HomeView(TemplateView):
    template_name = "core/home.html"

    def get_context_data(self, **kwargs) -> dict:
        ctx = super().get_context_data(**kwargs)
        ctx["hero"] = HeroSection.objects.filter(is_active=True).first()
        ctx["featured_services"] = Service.objects.filter(is_featured=True).select_related(
            "category"
        )[:3]
        ctx["featured_projects"] = Project.objects.filter(
            is_published=True, is_featured=True
        ).prefetch_related("services_used")[:4]
        # All visible testimonials feed the social-proof avatar cluster + count;
        # the first two are featured as full cards. Every value here is real
        # client data entered by staff — nothing is placeholder or invented.
        testimonials = list(Testimonial.objects.filter(is_visible=True))
        ctx["testimonials"] = testimonials
        ctx["featured_testimonials"] = testimonials[:2]
        ctx["testimonial_count"] = len(testimonials)
        # Capacity band stats — derived from real data so the homepage can never
        # contradict the services/portfolio it links to.
        ctx["services_count"] = Service.objects.count()
        ctx["stakeholder_count"] = len(BuyerType.choices)  # client / contractor / consultancy
        ctx["sector_count"] = len(Sector.choices)  # infrastructure / construction
        return ctx


class AboutView(TemplateView):
    template_name = "core/about.html"

    def get_context_data(self, **kwargs) -> dict:
        ctx = super().get_context_data(**kwargs)
        ctx["about"] = AboutSection.objects.first()
        ctx["page_title"] = "About Us"
        ctx["page_meta_desc"] = get_site_settings().about_meta_description
        return ctx


class PrivacyView(TemplateView):
    template_name = "core/privacy.html"

    def get_context_data(self, **kwargs) -> dict:
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Privacy Policy"
        return ctx


class RobotsView(TemplateView):
    template_name = "robots.txt"
    content_type = "text/plain"


def server_error(request: HttpRequest) -> HttpResponse:
    """Custom handler500.

    Django's default ``server_error`` renders 500.html with an empty context, so
    the ``site`` context processor never runs — and base.html's ``|default:site.*``
    filter arguments raise ``VariableDoesNotExist``, collapsing to Django's bare
    error string. Rendering *with* the request restores full branding. Guarded so
    a DB-triggered 500 degrades to a plain response instead of erroring again.
    """
    try:
        return render(request, "500.html", status=500)
    except Exception:
        return HttpResponseServerError("Internal Server Error")
