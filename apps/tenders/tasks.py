from __future__ import annotations

import logging
import os

import magic
from celery import shared_task
from django.conf import settings
from django.core.files import File
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string

from apps.core.tasks import publish_realtime

logger = logging.getLogger(__name__)

# Base seconds for exponential upload-retry backoff (10s, 20s, 40s).
_RETRY_BASE_COUNTDOWN = 10


def _cleanup_staging(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        logger.warning("Could not remove staging file %s", path, exc_info=True)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def process_document_upload(
    self, document_public_id: str, staging_path: str, original_filename: str
) -> None:
    """Move a staged upload into the private ``tender_documents`` store (R2 in
    prod), sniff its MIME type and size, and supersede prior revisions of the
    same document title. Retries with exponential backoff; a final failure marks
    the document FAILED rather than dropping it silently."""
    from .models import DocumentProcessingStatus, TenderDocument

    try:
        document = TenderDocument.objects.select_related("tender").get(public_id=document_public_id)
    except TenderDocument.DoesNotExist:
        _cleanup_staging(staging_path)
        return

    if not os.path.exists(staging_path):
        TenderDocument.objects.filter(pk=document.pk).update(
            processing_status=DocumentProcessingStatus.FAILED
        )
        logger.error(
            "Staging file %s for document %s vanished before processing",
            staging_path,
            document_public_id,
        )
        return

    try:
        mime_type = magic.from_file(staging_path, mime=True)
        size_bytes = os.path.getsize(staging_path)
        with open(staging_path, "rb") as handle:
            # Writes to R2/filesystem via the FileField's configured storage.
            document.file.save(original_filename, File(handle), save=False)
        document.mime_type = mime_type
        document.file_size_bytes = size_bytes
        document.is_superseded = False
        document.processing_status = DocumentProcessingStatus.READY
        with transaction.atomic():
            document.save(
                update_fields=[
                    "file",
                    "mime_type",
                    "file_size_bytes",
                    "is_superseded",
                    "processing_status",
                    "updated_at",
                ]
            )
            # Mark every prior revision of the same document title as superseded.
            TenderDocument.objects.filter(tender=document.tender, title=document.title).exclude(
                pk=document.pk
            ).update(is_superseded=True)
        # Best-effort AI summary — never fails or delays the upload itself.
        try:
            from apps.core import ai

            if ai.is_enabled():
                summarize_tender_document.delay(str(document.public_id))
        except Exception:
            logger.warning("Could not enqueue AI summary for %s", document_public_id, exc_info=True)
        # Live "new document" notification to staff.
        try:
            from apps.core import realtime

            if realtime.is_enabled():
                publish_realtime.delay(
                    realtime.STAFF_NOTIFICATIONS_CHANNEL,
                    "tender.document",
                    {
                        "message": f"New document on {document.tender.reference}",
                        "url": document.tender.get_absolute_url(),
                    },
                )
        except Exception:
            logger.warning("Could not enqueue document notification", exc_info=True)
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(
                exc=exc, countdown=_RETRY_BASE_COUNTDOWN * (2**self.request.retries)
            ) from exc
        TenderDocument.objects.filter(pk=document.pk).update(
            processing_status=DocumentProcessingStatus.FAILED
        )
        _cleanup_staging(staging_path)
        logger.error(
            "Document %s failed to process after retries", document_public_id, exc_info=True
        )
        return

    _cleanup_staging(staging_path)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def notify_tender_status_change(
    self, tender_public_id: str, new_status: str, changed_by_id: str
) -> None:
    """Email every assigned staff member that a tender changed status."""
    from apps.core.models import User

    from .models import Tender

    try:
        tender = Tender.objects.prefetch_related("assigned_to").get(public_id=tender_public_id)
    except Tender.DoesNotExist:
        return

    recipients = [u.email for u in tender.assigned_to.all() if u.email]
    if not recipients:
        return

    changed_by = User.objects.filter(public_id=changed_by_id).first()

    try:
        subject = f"[{tender.reference}] status changed to {tender.get_status_display()}"
        body = render_to_string(
            "tenders/email/status_change.txt",
            {
                "tender": tender,
                "new_status_display": tender.get_status_display(),
                "changed_by": changed_by,
            },
        )
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception as exc:
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_client_tender_ack(self, tender_public_id: str) -> None:
    """Warm acknowledgement to the client when we register their opportunity —
    'we're on it'. Best-effort; skipped when no client email is on file."""
    from .models import Tender

    if not getattr(settings, "SEND_CLIENT_EMAILS", True):
        return
    try:
        tender = Tender.objects.get(public_id=tender_public_id)
    except Tender.DoesNotExist:
        return
    if not tender.client_email:
        return

    try:
        body = render_to_string("tenders/email/client_ack.txt", {"tender": tender})
        send_mail(
            subject=f"We've received your project — {tender.title}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[tender.client_email],
            fail_silently=False,
        )
    except Exception as exc:
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_client_status_update(self, tender_public_id: str) -> None:
    """Keep the client feeling looked-after with a friendly status update."""
    from .models import Tender, TenderStatus

    if not getattr(settings, "SEND_CLIENT_EMAILS", True):
        return
    try:
        tender = Tender.objects.get(public_id=tender_public_id)
    except Tender.DoesNotExist:
        return
    # Only notify clients on outward-meaningful milestones, not internal drafts.
    if not tender.client_email or tender.status not in {
        TenderStatus.SUBMITTED,
        TenderStatus.WON,
    }:
        return

    try:
        body = render_to_string("tenders/email/client_status.txt", {"tender": tender})
        send_mail(
            subject=f"An update on your project — {tender.title}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[tender.client_email],
            fail_silently=False,
        )
    except Exception as exc:
        raise self.retry(exc=exc) from exc


def _extract_text(document) -> str:
    """Best-effort text extraction from a stored document for AI summarisation.
    Supports PDF (pypdf) and plain-text; other formats yield no text."""
    mime = (document.mime_type or "").lower()
    try:
        if mime == "application/pdf" or document.filename.lower().endswith(".pdf"):
            from pypdf import PdfReader

            with document.file.open("rb") as handle:
                reader = PdfReader(handle)
                return "\n".join((page.extract_text() or "") for page in reader.pages)
        if mime.startswith("text/"):
            with document.file.open("rb") as handle:
                return handle.read().decode("utf-8", errors="replace")
    except Exception:
        logger.warning("Text extraction failed for document %s", document.public_id, exc_info=True)
    return ""


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def summarize_tender_document(self, document_public_id: str) -> None:
    """Generate and store a local-DeepSeek summary of a processed document."""
    from apps.core import ai

    from .models import DocumentProcessingStatus, TenderDocument

    if not ai.is_enabled():
        return
    try:
        document = TenderDocument.objects.get(
            public_id=document_public_id, processing_status=DocumentProcessingStatus.READY
        )
    except TenderDocument.DoesNotExist:
        return

    text = _extract_text(document)
    if not text.strip():
        return

    try:
        summary = ai.summarize_document(document.filename, text)
    except ai.AIUnavailable:
        return  # quota/transient — a missing summary is non-critical
    except Exception as exc:
        raise self.retry(exc=exc) from exc

    TenderDocument.objects.filter(pk=document.pk).update(ai_summary=summary)


def _tender_ai_context(tender) -> str:
    from django.utils.html import strip_tags

    context = (
        f"Client: {tender.client_name}\n"
        f"Sector: {tender.get_sector_display()}\n"
        f"Status: {tender.get_status_display()}\n"
        f"Deadline: {tender.deadline or 'n/a'}\n"
        f"Description: {strip_tags(tender.description)}\n"
        f"Notes: {strip_tags(tender.notes)}\n"
    )
    summaries = [d.ai_summary for d in tender.documents.all() if d.ai_summary]
    if summaries:
        context += "Document summaries:\n" + "\n\n".join(summaries)
    return context


@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def run_ai_job(self, job_public_id: str) -> None:
    """Run a queued interactive-AI request (Q&A / client-email / description)
    off the request cycle, storing the result on the AIJob for the browser to
    poll. A slow local model therefore never occupies a web worker."""
    from apps.core import ai

    from .models import AIJob, AIJobKind, AIJobStatus, Tender

    try:
        job = AIJob.objects.get(public_id=job_public_id, status=AIJobStatus.PENDING)
    except AIJob.DoesNotExist:
        return

    params = job.params or {}
    try:
        if job.kind == AIJobKind.DESCRIPTION:
            result = ai.draft_tender_description(
                params.get("title", ""), params.get("client_name", ""), params.get("sector", "")
            )
        else:
            tender = Tender.objects.prefetch_related("documents").get(
                public_id=params.get("tender_public_id")
            )
            if job.kind == AIJobKind.EMAIL:
                result = ai.draft_client_email(
                    tender.client_name,
                    tender.title,
                    tender.get_status_display(),
                    params.get("purpose", ""),
                )
            else:  # ASK
                result = ai.answer_tender_question(
                    tender.title, _tender_ai_context(tender), params.get("question", "")
                )
    except Tender.DoesNotExist:
        AIJob.objects.filter(pk=job.pk).update(status=AIJobStatus.FAILED, error="Tender not found.")
        return
    except ai.AIUnavailable as exc:
        AIJob.objects.filter(pk=job.pk).update(status=AIJobStatus.FAILED, error=str(exc))
        return
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        AIJob.objects.filter(pk=job.pk).update(
            status=AIJobStatus.FAILED, error="The AI request failed."
        )
        return

    AIJob.objects.filter(pk=job.pk).update(status=AIJobStatus.READY, result=result)
