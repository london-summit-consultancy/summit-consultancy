from __future__ import annotations

import logging
import os
import uuid

import magic
from csp.decorators import csp_update
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import (
    FileResponse,
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from apps.core import ai, realtime
from apps.core.realtime import STAFF_NOTIFICATIONS_CHANNEL, tender_channel
from apps.core.tasks import publish_realtime
from apps.inquiries.models import Inquiry, InquiryStatus
from apps.portfolio.models import CompletionStatus, Project, Sector
from apps.services.models import BuyerType, Service

from .forms import TenderForm
from .models import (
    AIJob,
    AIJobKind,
    AIJobStatus,
    DocumentProcessingStatus,
    Tender,
    TenderDocument,
    TenderMessage,
    TenderStatus,
)
from .tasks import (
    notify_tender_status_change,
    process_document_upload,
    run_ai_job,
    send_client_status_update,
    send_client_tender_ack,
)

logger = logging.getLogger(__name__)

_PIPELINE_STATUSES = [TenderStatus.DRAFT, TenderStatus.SUBMITTED]

# Ably realtime needs WebSocket/HTTP connections beyond 'self'. Scope the
# relaxation to the internal pages that actually use it, keeping the public
# site's strict CSP intact.
_ABLY_CONNECT_SRC = [
    "wss://*.ably.io",
    "https://*.ably.io",
    "wss://*.ably-realtime.com",
    "https://*.ably-realtime.com",
]
realtime_csp = csp_update({"connect-src": _ABLY_CONNECT_SRC})
# Plotly evaluates generated code, so the dashboard additionally needs
# 'unsafe-eval' — again scoped to this one internal view only.
dashboard_csp = csp_update({"connect-src": _ABLY_CONNECT_SRC, "script-src": ["'unsafe-eval'"]})


def _notify_staff(event: str, message: str, url: str) -> None:
    """Fan a short notification out to all staff (best-effort)."""
    try:
        publish_realtime.delay(STAFF_NOTIFICATIONS_CHANNEL, event, {"message": message, "url": url})
    except Exception:
        logger.warning("Could not enqueue staff notification %s", event, exc_info=True)


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Login required AND is_staff. Anonymous users are redirected to LOGIN_URL;
    authenticated non-staff users get a 403 (AccessMixin default)."""

    def test_func(self) -> bool:
        return bool(self.request.user.is_staff)


def _transition_options(tender: Tender) -> list[dict[str, str]]:
    """Legal next statuses for the current tender, for conditional buttons."""
    return [
        {"value": value, "label": label}
        for value, label in TenderStatus.choices
        if tender.can_transition_to(value)
    ]


class TenderListView(StaffRequiredMixin, ListView):
    context_object_name = "tenders"

    def get_template_names(self) -> list[str]:
        if self.request.htmx:
            return ["tenders/partials/_tender_list.html"]
        return ["tenders/list.html"]

    def get_queryset(self):
        # The list renders reference/title/client/sector/deadline/value/status/
        # assignees only. Defer the large prose TEXT columns and skip the unused
        # created_by join and documents prefetch.
        qs = (
            Tender.objects.defer("description", "notes")
            .prefetch_related("assigned_to")
            .order_by("-created_at")
        )
        status = self.request.GET.get("status", "")
        if status in TenderStatus.values:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs) -> dict:
        ctx = super().get_context_data(**kwargs)
        counts = Tender.objects.aggregate(
            draft=Count("pk", filter=Q(status=TenderStatus.DRAFT)),
            submitted=Count("pk", filter=Q(status=TenderStatus.SUBMITTED)),
            won=Count("pk", filter=Q(status=TenderStatus.WON)),
            lost=Count("pk", filter=Q(status=TenderStatus.LOST)),
            withdrawn=Count("pk", filter=Q(status=TenderStatus.WITHDRAWN)),
        )
        pipeline_value = Tender.objects.filter(status__in=_PIPELINE_STATUSES).aggregate(
            total=Sum("estimated_value")
        )["total"]
        ctx["status_counts"] = counts
        ctx["pipeline_value"] = pipeline_value or 0
        ctx["active_status"] = self.request.GET.get("status", "")
        ctx["status_choices"] = TenderStatus.choices
        ctx["realtime_enabled"] = realtime.is_enabled()
        ctx["page_title"] = "Tender Pipeline"
        return ctx


@method_decorator(realtime_csp, name="dispatch")
class TenderDetailView(StaffRequiredMixin, DetailView):
    template_name = "tenders/detail.html"
    context_object_name = "tender"
    slug_field = "public_id"
    slug_url_kwarg = "public_id"

    def get_queryset(self):
        return Tender.objects.select_related("created_by").prefetch_related(
            "assigned_to", "documents__uploaded_by"
        )

    def get_context_data(self, **kwargs) -> dict:
        ctx = super().get_context_data(**kwargs)
        documents = list(self.object.documents.all())
        ctx["current_documents"] = [d for d in documents if not d.is_superseded]
        ctx["archived_documents"] = [d for d in documents if d.is_superseded]
        ctx["history_entries"] = self.object.history.select_related("history_user").all()[:50]
        ctx["transition_options"] = _transition_options(self.object)
        ctx["messages_list"] = list(self.object.messages.select_related("author").all()[:100])
        ctx["realtime_enabled"] = realtime.is_enabled()
        ctx["ai_enabled"] = ai.is_enabled()
        ctx["tender_channel"] = tender_channel(str(self.object.public_id))
        ctx["page_title"] = f"{self.object.reference} — {self.object.title}"
        return ctx


class TenderCreateView(StaffRequiredMixin, CreateView):
    form_class = TenderForm
    template_name = "tenders/form.html"

    def get_context_data(self, **kwargs) -> dict:
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "New Tender"
        ctx["is_create"] = True
        ctx["ai_enabled"] = ai.is_enabled()
        return ctx

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save(commit=False)
            self.object.created_by = self.request.user
            self.object.save()
            form.save_m2m()
        try:
            send_client_tender_ack.delay(str(self.object.public_id))
        except Exception:
            logger.error(
                "Failed to enqueue client ack for tender %s — broker may be down",
                self.object.public_id,
                exc_info=True,
            )
        if self.request.htmx:
            resp = HttpResponse(status=204)
            resp["HX-Redirect"] = self.object.get_absolute_url()
            return resp
        return redirect(self.object.get_absolute_url())

    def form_invalid(self, form):
        if self.request.htmx:
            return TemplateResponse(
                self.request,
                self.template_name,
                self.get_context_data(form=form),
                status=422,
            )
        return super().form_invalid(form)


class TenderUpdateView(StaffRequiredMixin, UpdateView):
    form_class = TenderForm
    template_name = "tenders/form.html"
    context_object_name = "tender"
    slug_field = "public_id"
    slug_url_kwarg = "public_id"
    queryset = Tender.objects.all()

    def get_context_data(self, **kwargs) -> dict:
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = f"Edit {self.object.reference}"
        ctx["is_create"] = False
        ctx["ai_enabled"] = ai.is_enabled()
        return ctx

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
        if self.request.htmx:
            resp = HttpResponse(status=204)
            resp["HX-Redirect"] = self.object.get_absolute_url()
            return resp
        return redirect(self.object.get_absolute_url())

    def form_invalid(self, form):
        if self.request.htmx:
            return TemplateResponse(
                self.request,
                self.template_name,
                self.get_context_data(form=form),
                status=422,
            )
        return super().form_invalid(form)


class TenderStatusUpdateView(StaffRequiredMixin, View):
    """POST-only. Validates the transition, writes it atomically under a row
    lock, notifies assignees, and returns the status block partial."""

    def post(self, request, public_id):
        tender = get_object_or_404(Tender, public_id=public_id)
        new_status = request.POST.get("status", "")

        with transaction.atomic():
            locked = Tender.objects.select_for_update().get(pk=tender.pk)
            if not locked.can_transition_to(new_status):
                raise PermissionDenied(f"Illegal transition {locked.status!r} -> {new_status!r}.")
            locked.transition_to(new_status)

        try:
            notify_tender_status_change.delay(
                str(tender.public_id), new_status, str(request.user.public_id)
            )
            send_client_status_update.delay(str(tender.public_id))
        except Exception:
            logger.error(
                "Failed to enqueue status-change notifications for tender %s — broker may be down",
                tender.public_id,
                exc_info=True,
            )
        _notify_staff(
            "tender.status",
            f"{tender.reference} is now {tender.get_status_display()}",
            tender.get_absolute_url(),
        )

        # Re-read for a fresh instance; the status block needs no relations.
        tender = Tender.objects.get(pk=tender.pk)
        ctx = {
            "tender": tender,
            "transition_options": _transition_options(tender),
            "history_entries": tender.history.select_related("history_user").all()[:50],
        }
        return TemplateResponse(request, "tenders/partials/_status_block.html", ctx)


class DocumentUploadView(StaffRequiredMixin, View):
    """POST-only multipart upload. Validates, stages the file locally, enqueues
    the R2 move + processing task, and returns 202 with a 'Processing…' row.
    The request never blocks on storage."""

    def post(self, request, public_id):
        tender = get_object_or_404(Tender, public_id=public_id)
        title = (request.POST.get("title") or "").strip()
        revision = (request.POST.get("revision") or "").strip()
        upload = request.FILES.get("file")

        if not title or not revision:
            return HttpResponseBadRequest("Title and revision are required.")
        if upload is None:
            return HttpResponseBadRequest("No file was provided.")
        if upload.size > settings.TENDER_MAX_UPLOAD_BYTES:
            return HttpResponseBadRequest("File exceeds the 500 MB limit.")

        ext = os.path.splitext(upload.name)[1].lower()
        if ext not in settings.TENDER_ALLOWED_UPLOAD_EXTENSIONS:
            return HttpResponseBadRequest(f"File type '{ext}' is not permitted.")

        # Authoritative content sniff on the first chunk (untrusted client
        # Content-Type is ignored). The Celery task re-sniffs the stored object.
        head = upload.read(2048)
        upload.seek(0)
        sniffed = magic.from_buffer(head, mime=True) if head else "application/octet-stream"
        if sniffed not in settings.TENDER_ALLOWED_UPLOAD_MIME_TYPES:
            return HttpResponseBadRequest(f"File content type '{sniffed}' is not permitted.")

        if TenderDocument.objects.filter(tender=tender, title=title, revision=revision).exists():
            return HttpResponseBadRequest(f"'{title}' {revision} already exists for this tender.")

        staging_path = self._stage(upload)

        document = TenderDocument.objects.create(
            tender=tender,
            title=title,
            revision=revision,
            uploaded_by=request.user,
            processing_status=DocumentProcessingStatus.PROCESSING,
        )

        try:
            process_document_upload.delay(
                str(document.public_id), staging_path, os.path.basename(upload.name)
            )
        except Exception:
            logger.error(
                "Failed to enqueue document processing for %s — broker may be down",
                document.public_id,
                exc_info=True,
            )

        ctx = {"document": document, "tender": tender}
        return TemplateResponse(request, "tenders/partials/_document_row.html", ctx, status=202)

    @staticmethod
    def _stage(upload) -> str:
        staging_dir = settings.TENDER_UPLOAD_STAGING_DIR
        os.makedirs(staging_dir, exist_ok=True)
        safe_name = os.path.basename(upload.name)
        staging_path = os.path.join(staging_dir, f"{uuid.uuid4().hex}_{safe_name}")
        with open(staging_path, "wb") as dest:
            for chunk in upload.chunks():
                dest.write(chunk)
        return staging_path


class DocumentSupersededToggleView(StaffRequiredMixin, View):
    def post(self, request, doc_public_id):
        document = get_object_or_404(
            TenderDocument.objects.select_related("tender", "uploaded_by"),
            public_id=doc_public_id,
        )
        document.is_superseded = not document.is_superseded
        document.save(update_fields=["is_superseded", "updated_at"])
        ctx = {"document": document, "tender": document.tender}
        return TemplateResponse(request, "tenders/partials/_document_row.html", ctx)


def _enqueue_ai_job(request, kind: str, params: dict) -> JsonResponse:
    """Create a pollable AIJob and hand it to Celery. Returns 202 + a poll URL,
    or 503 if AI is unconfigured / the broker is down. The (slow, local) model
    call happens in the worker — never in this request."""
    if not ai.is_enabled():
        return JsonResponse({"error": "The local AI service is not configured."}, status=503)
    job = AIJob.objects.create(kind=kind, params=params, requested_by=request.user)
    try:
        run_ai_job.delay(str(job.public_id))
    except Exception:
        logger.error(
            "Could not enqueue AI job %s — broker may be down", job.public_id, exc_info=True
        )
        AIJob.objects.filter(pk=job.pk).update(
            status=AIJobStatus.FAILED, error="The AI queue is unavailable."
        )
        return JsonResponse({"error": "The AI queue is unavailable."}, status=503)
    return JsonResponse(
        {
            "job_id": str(job.public_id),
            "poll_url": reverse("tenders:ai_job_status", kwargs={"job_public_id": job.public_id}),
        },
        status=202,
    )


class AIDraftDescriptionView(StaffRequiredMixin, View):
    """POST title/client/sector → enqueue an AI description draft (202 + poll URL)."""

    def post(self, request):
        title = (request.POST.get("title") or "").strip()
        if not title:
            return JsonResponse({"error": "Enter a title first."}, status=400)
        return _enqueue_ai_job(
            request,
            AIJobKind.DESCRIPTION,
            {
                "title": title,
                "client_name": (request.POST.get("client_name") or "").strip(),
                "sector": (request.POST.get("sector") or "").strip(),
            },
        )


class AIDraftClientEmailView(StaffRequiredMixin, View):
    """POST purpose → enqueue an AI client-email draft (202 + poll URL)."""

    def post(self, request, public_id):
        tender = get_object_or_404(Tender, public_id=public_id)
        return _enqueue_ai_job(
            request,
            AIJobKind.EMAIL,
            {
                "tender_public_id": str(tender.public_id),
                "purpose": (request.POST.get("purpose") or "").strip(),
            },
        )


class AITenderQAView(StaffRequiredMixin, View):
    """POST a question → enqueue an AI Q&A job (202 + poll URL)."""

    def post(self, request, public_id):
        tender = get_object_or_404(Tender, public_id=public_id)
        question = (request.POST.get("question") or "").strip()
        if not question:
            return JsonResponse({"error": "Type a question."}, status=400)
        return _enqueue_ai_job(
            request,
            AIJobKind.ASK,
            {"tender_public_id": str(tender.public_id), "question": question},
        )


class AIJobStatusView(StaffRequiredMixin, View):
    """Poll target: returns the job's status and (when ready) its result. Scoped
    to the requester so staff can't read each other's drafts."""

    def get(self, request, job_public_id):
        job = get_object_or_404(AIJob, public_id=job_public_id, requested_by=request.user)
        return JsonResponse({"status": job.status, "result": job.result, "error": job.error})


@method_decorator(dashboard_csp, name="dispatch")
class DashboardView(StaffRequiredMixin, TemplateView):
    """Staff analytics. Only aggregated figures reach the browser — never raw
    rows or client PII — and all labels are numeric/enum values."""

    template_name = "tenders/dashboard.html"

    def get_context_data(self, **kwargs) -> dict:
        ctx = super().get_context_data(**kwargs)
        qs = Tender.objects.all()

        status_map = dict(TenderStatus.choices)
        counts = {row["status"]: row["n"] for row in qs.values("status").annotate(n=Count("pk"))}
        status_labels = [str(label) for label in status_map.values()]
        status_values = [counts.get(value, 0) for value in status_map]

        sector_rows = (
            qs.filter(status__in=_PIPELINE_STATUSES)
            .values("sector")
            .annotate(total=Sum("estimated_value"))
            .order_by("-total")
        )
        sector_display = dict(Tender._meta.get_field("sector").choices)
        sector_labels = [str(sector_display.get(r["sector"], r["sector"])) for r in sector_rows]
        sector_values = [float(r["total"] or 0) for r in sector_rows]

        monthly = (
            qs.annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(n=Count("pk"))
            .order_by("month")
        )
        month_labels = [r["month"].strftime("%b %Y") for r in monthly if r["month"]]
        month_values = [r["n"] for r in monthly if r["month"]]

        won = counts.get(TenderStatus.WON, 0)
        lost = counts.get(TenderStatus.LOST, 0)
        decided = won + lost

        ctx["charts"] = {
            "status": {"labels": status_labels, "values": status_values},
            "sector": {"labels": sector_labels, "values": sector_values},
            "monthly": {"labels": month_labels, "values": month_values},
            "outcome": {"won": won, "lost": lost},
        }
        ctx["win_rate"] = round(100 * won / decided, 1) if decided else 0
        ctx["total_pipeline"] = (
            qs.filter(status__in=_PIPELINE_STATUSES).aggregate(t=Sum("estimated_value"))["t"] or 0
        )
        ctx["total_tenders"] = qs.count()
        ctx["realtime_enabled"] = realtime.is_enabled()
        ctx["page_title"] = "Analytics"

        # --- Inquiries pipeline (apps.inquiries) --------------------------
        inquiry_qs = Inquiry.objects.all()

        inquiry_status_map = dict(InquiryStatus.choices)
        inquiry_counts = {
            row["status"]: row["n"] for row in inquiry_qs.values("status").annotate(n=Count("pk"))
        }
        inquiry_status_labels = [str(label) for label in inquiry_status_map.values()]
        inquiry_status_values = [inquiry_counts.get(value, 0) for value in inquiry_status_map]

        # buyer_type is blank=True; add an explicit "Not specified" bucket for unset rows.
        buyer_type_map = dict(BuyerType.choices)
        buyer_counts = {
            row["buyer_type"]: row["n"]
            for row in inquiry_qs.values("buyer_type").annotate(n=Count("pk"))
        }
        buyer_labels = [str(label) for label in buyer_type_map.values()] + ["Not specified"]
        buyer_values = [buyer_counts.get(value, 0) for value in buyer_type_map] + [
            buyer_counts.get("", 0)
        ]

        inquiry_monthly = (
            inquiry_qs.annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(n=Count("pk"))
            .order_by("month")
        )
        inquiry_month_labels = [r["month"].strftime("%b %Y") for r in inquiry_monthly if r["month"]]
        inquiry_month_values = [r["n"] for r in inquiry_monthly if r["month"]]

        inquiry_won = inquiry_counts.get(InquiryStatus.CLOSED_WON, 0)
        inquiry_lost = inquiry_counts.get(InquiryStatus.CLOSED_LOST, 0)
        inquiry_decided = inquiry_won + inquiry_lost

        # --- Portfolio & service delivery (apps.portfolio, apps.services) -
        # Unfiltered, no is_published gate: staff need the true internal delivery
        # picture, same convention as Tender.objects.all() above.
        project_qs = Project.objects.all()

        sector_choice_map = dict(Sector.choices)
        tender_sector_counts = {
            row["sector"]: row["n"] for row in qs.values("sector").annotate(n=Count("pk"))
        }
        project_sector_counts = {
            row["sector"]: row["n"] for row in project_qs.values("sector").annotate(n=Count("pk"))
        }
        sector_compare_labels = [str(label) for label in sector_choice_map.values()]
        sector_compare_tenders = [tender_sector_counts.get(v, 0) for v in sector_choice_map]
        sector_compare_projects = [project_sector_counts.get(v, 0) for v in sector_choice_map]

        completion_map = dict(CompletionStatus.choices)
        completion_counts = {
            row["completion_status"]: row["n"]
            for row in project_qs.values("completion_status").annotate(n=Count("pk"))
        }
        completion_labels = [str(label) for label in completion_map.values()]
        completion_values = [completion_counts.get(v, 0) for v in completion_map]

        # Service demand (inquiries) vs delivery (projects it was used on). Service has
        # two independent to-many reverse relations (FK "inquiries" + M2M "projects");
        # annotating both Counts in one queryset joins both onto Service, so each base
        # row fans out per (inquiry, project) combination. distinct=True is mandatory
        # here, not defensive — without it a service with 3 inquiries and 4 projects
        # reports inquiry_n=12, project_n=12 instead of 3 and 4.
        service_rows = (
            Service.objects.annotate(
                inquiry_n=Count("inquiries", distinct=True),
                project_n=Count("projects", distinct=True),
            )
            .values("name", "inquiry_n", "project_n")
            .order_by("-inquiry_n", "name")
        )
        service_labels = [r["name"] for r in service_rows]
        service_inquiry_values = [r["inquiry_n"] for r in service_rows]
        service_project_values = [r["project_n"] for r in service_rows]

        ctx["charts"].update(
            {
                "inquiry_status": {
                    "labels": inquiry_status_labels,
                    "values": inquiry_status_values,
                },
                "buyer_type": {"labels": buyer_labels, "values": buyer_values},
                "inquiry_monthly": {
                    "labels": inquiry_month_labels,
                    "values": inquiry_month_values,
                },
                "sector_compare": {
                    "labels": sector_compare_labels,
                    "tenders": sector_compare_tenders,
                    "projects": sector_compare_projects,
                },
                "completion_status": {"labels": completion_labels, "values": completion_values},
                "service_demand": {
                    "labels": service_labels,
                    "inquiries": service_inquiry_values,
                    "projects": service_project_values,
                },
            }
        )
        ctx["total_inquiries"] = inquiry_qs.count()
        ctx["inquiry_win_rate"] = (
            round(100 * inquiry_won / inquiry_decided, 1) if inquiry_decided else 0
        )
        ctx["projects_delivered"] = project_qs.filter(
            completion_status=CompletionStatus.COMPLETED
        ).count()
        ctx["services_offered"] = Service.objects.count()
        return ctx


class AblyTokenView(StaffRequiredMixin, View):
    """Mint a short-lived, capability-scoped Ably token for the current staff
    user (used by the browser SDK's authUrl)."""

    def get(self, request):
        if not realtime.is_enabled():
            return JsonResponse({"error": "Realtime is not configured."}, status=503)
        try:
            token_request = realtime.create_token_request(str(request.user.public_id))
        except Exception:
            logger.error("Ably token request failed", exc_info=True)
            return JsonResponse({"error": "Could not create a realtime token."}, status=502)
        return JsonResponse(token_request)


class TenderMessageCreateView(StaffRequiredMixin, View):
    """POST a chat message: persist it, fan it out over Ably, return its row."""

    def post(self, request, public_id):
        tender = get_object_or_404(Tender, public_id=public_id)
        body = (request.POST.get("body") or "").strip()
        if not body:
            return HttpResponseBadRequest("Message cannot be empty.")
        if len(body) > 4000:
            return HttpResponseBadRequest("Message is too long.")

        message = TenderMessage.objects.create(tender=tender, author=request.user, body=body)
        # Fan out to other viewers + notify staff. The browser sends only plain
        # text fields; subscribers render them as textContent (never innerHTML).
        payload = {
            "id": str(message.public_id),
            "author": request.user.get_full_name(),
            "body": message.body,
            "created": message.created_at.strftime("%d %b %Y, %H:%M"),
        }
        try:
            publish_realtime.delay(tender_channel(str(tender.public_id)), "message", payload)
        except Exception:
            logger.warning("Could not enqueue chat publish", exc_info=True)
        _notify_staff(
            "tender.message",
            f"New message on {tender.reference}",
            tender.get_absolute_url(),
        )
        return TemplateResponse(
            request, "tenders/partials/_message.html", {"message": message, "own": True}
        )


class TenderDocumentDownloadView(StaffRequiredMixin, View):
    """Staff-gated download. On R2 (production) redirect to a signed, expiring
    URL; on the local filesystem stream the bytes."""

    def get(self, request, doc_public_id):
        document = get_object_or_404(TenderDocument, public_id=doc_public_id)
        if not document.file:
            raise Http404("Document has no stored file.")
        if settings.TENDER_DOCS_SIGNED_URLS:
            return HttpResponseRedirect(document.file.url)
        return FileResponse(
            document.file.open("rb"),
            as_attachment=True,
            filename=document.filename,
        )
