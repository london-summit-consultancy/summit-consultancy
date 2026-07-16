import logging

from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView
from django.views.generic.edit import CreateView
from django_ratelimit.decorators import ratelimit

from apps.services.models import Service

from .forms import InquiryForm
from .tasks import send_inquiry_acknowledgement, send_inquiry_notification

logger = logging.getLogger(__name__)


@method_decorator(ratelimit(key="ip", rate="5/h", method="POST", block=True), name="post")
class InquiryCreateView(CreateView):
    form_class = InquiryForm
    template_name = "inquiries/contact.html"

    def get_context_data(self, **kwargs) -> dict:
        ctx = super().get_context_data(**kwargs)
        ctx["services"] = Service.objects.select_related("category").order_by(
            "category__display_order", "display_order"
        )
        ctx["page_title"] = "Contact Us"
        ctx["page_meta_desc"] = (
            "Get in touch with London Summit Consultancy Limited — "
            "construction consultancy for clients, contractors, and consultancies."
        )
        return ctx

    def form_valid(self, form):
        inquiry = form.save(commit=False)
        if inquiry.website:
            if self.request.htmx:
                return TemplateResponse(self.request, "partials/_inquiry_success.html", {})
            return redirect("inquiries:sent")
        inquiry.source_page = self.request.META.get("HTTP_REFERER", "")
        inquiry.ip_address = self.request.META.get("REMOTE_ADDR")
        inquiry.save()
        try:
            send_inquiry_notification.delay(inquiry.pk)
            send_inquiry_acknowledgement.delay(inquiry.pk)
        except Exception:
            # Celery broker unavailable — inquiry is persisted; emails will not be sent.
            logger.error(
                "Failed to enqueue email tasks for inquiry pk=%s — broker may be down",
                inquiry.pk,
                exc_info=True,
            )
        if self.request.htmx:
            return TemplateResponse(self.request, "partials/_inquiry_success.html", {})
        return redirect("inquiries:sent")

    def form_invalid(self, form):
        if self.request.htmx:
            return TemplateResponse(
                self.request,
                "partials/_inquiry_form.html",
                {"form": form},
                status=422,
            )
        return super().form_invalid(form)


class InquirySuccessView(TemplateView):
    template_name = "inquiries/sent.html"

    def get_context_data(self, **kwargs) -> dict:
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Message Sent"
        return ctx


class InquiryValidateView(View):
    """HTMX-only. Accepts a single field POST and returns the field error or empty string."""

    _allowed_fields = frozenset(InquiryForm.Meta.fields) - {"website"}

    def post(self, request):
        from django.http import HttpResponse

        field_name = next((k for k in request.POST if k in self._allowed_fields), None)
        if not field_name:
            return HttpResponse("")
        form = InquiryForm(data={field_name: request.POST.get(field_name, "")})
        form.is_valid()
        error = form.errors.get(field_name, [""])[0]
        return HttpResponse(error)
