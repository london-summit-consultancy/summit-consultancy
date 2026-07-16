from __future__ import annotations

import simple_history
from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.urls import reverse
from django.utils import timezone
from django_prose_editor.fields import ProseEditorField

from apps.core.models import TimeStampedUUIDModel
from apps.core.prose import RICH_TEXT_EXTENSIONS
from apps.portfolio.models import Sector

from .storage import tender_document_storage, tender_document_upload_to


class TenderStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    WON = "won", "Won"
    LOST = "lost", "Lost"
    WITHDRAWN = "withdrawn", "Withdrawn"


# Explicit state machine. A tender is drafted, submitted, then resolved. Any
# state can be reset to DRAFT (handled specially in ``can_transition_to``).
TENDER_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    TenderStatus.DRAFT: {TenderStatus.SUBMITTED},
    TenderStatus.SUBMITTED: {TenderStatus.WON, TenderStatus.LOST, TenderStatus.WITHDRAWN},
    TenderStatus.WON: set(),
    TenderStatus.LOST: set(),
    TenderStatus.WITHDRAWN: set(),
}


class DocumentProcessingStatus(models.TextChoices):
    PROCESSING = "processing", "Processing"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"


class Tender(TimeStampedUUIDModel):
    reference = models.CharField(
        max_length=60,
        unique=True,
        editable=False,
        help_text="Auto-generated, e.g. London Summit Consultancy Limited-2026-001.",
    )
    title = models.CharField(max_length=200)
    client_name = models.CharField(max_length=150)
    client_email = models.EmailField(blank=True)
    sector = models.CharField(max_length=30, choices=Sector.choices)
    description = ProseEditorField(extensions=RICH_TEXT_EXTENSIONS, sanitize=True)
    deadline = models.DateField(null=True, blank=True)
    estimated_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Estimated contract value in GBP.",
    )
    status = models.CharField(
        max_length=20,
        choices=TenderStatus.choices,
        default=TenderStatus.DRAFT,
    )
    status_changed_at = models.DateTimeField(null=True, blank=True)
    notes = ProseEditorField(extensions=RICH_TEXT_EXTENSIONS, sanitize=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_tenders",
    )
    assigned_to = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="assigned_tenders",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Tender"
        indexes = [
            # Primary list access pattern: filter by status, order by newest.
            # Composite serves the WHERE + ORDER BY in one scan and also covers
            # status-equality lookups (so a standalone status index is redundant).
            models.Index(fields=["status", "-created_at"], name="tender_status_created_idx"),
            models.Index(fields=["deadline"], name="tender_deadline_idx"),
            # Unfiltered default list ordering (leading col of the composite is
            # status, so it can't serve a status-less ORDER BY created_at).
            models.Index(fields=["-created_at"], name="tender_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.reference} — {self.title}"

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._original_status = instance.status
        return instance

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if not hasattr(self, "_original_status"):
            self._original_status = None

    def get_absolute_url(self) -> str:
        return reverse("tenders:detail", kwargs={"public_id": self.public_id})

    @property
    def is_overdue(self) -> bool:
        return (
            self.deadline is not None
            and self.status in {TenderStatus.DRAFT, TenderStatus.SUBMITTED}
            and self.deadline < timezone.localdate()
        )

    @staticmethod
    def _next_reference(year: int) -> str:
        prefix = f"London Summit Consultancy Limited-{year}-"
        last = (
            Tender.objects.select_for_update()
            .filter(reference__startswith=prefix)
            .order_by("-reference")
            .values_list("reference", flat=True)
            .first()
        )
        seq = int(last.rsplit("-", 1)[1]) + 1 if last else 1
        return f"{prefix}{seq:03d}"

    def save(self, *args, **kwargs) -> None:
        # Stamp status_changed_at whenever status is (re)assigned.
        if self._state.adding:
            if self.status_changed_at is None:
                self.status_changed_at = timezone.now()
        elif self.status != self._original_status:
            self.status_changed_at = timezone.now()

        if self._state.adding and not self.reference:
            # Reference generation and the insert share one transaction; the
            # unique constraint plus a bounded retry make concurrent creates safe.
            for _ in range(5):
                try:
                    with transaction.atomic():
                        year = timezone.localdate().year
                        self.reference = self._next_reference(year)
                        super().save(*args, **kwargs)
                    break
                except IntegrityError:
                    self.reference = ""
                    self.pk = None
            else:
                raise IntegrityError("Could not allocate a unique tender reference.")
        else:
            super().save(*args, **kwargs)

        self._original_status = self.status

    # --- state machine -----------------------------------------------------
    def can_transition_to(self, new_status: str) -> bool:
        if new_status not in TenderStatus.values:
            return False
        if new_status == self.status:
            return False
        # Any state may be reset to DRAFT.
        if new_status == TenderStatus.DRAFT:
            return True
        return new_status in TENDER_ALLOWED_TRANSITIONS.get(self.status, set())

    def transition_to(self, new_status: str) -> None:
        if not self.can_transition_to(new_status):
            raise ValueError(f"Illegal tender transition {self.status!r} -> {new_status!r}.")
        self.status = new_status
        self.status_changed_at = timezone.now()
        self.save(update_fields=["status", "status_changed_at", "updated_at"])


class TenderDocument(TimeStampedUUIDModel):
    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=200)
    revision = models.CharField(
        max_length=10,
        help_text="Free-form revision label, e.g. 'Rev A', 'Rev 1'.",
    )
    file = models.FileField(
        upload_to=tender_document_upload_to,
        storage=tender_document_storage,
        max_length=500,
        blank=True,
    )
    file_size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    is_superseded = models.BooleanField(default=False)
    processing_status = models.CharField(
        max_length=20,
        choices=DocumentProcessingStatus.choices,
        default=DocumentProcessingStatus.PROCESSING,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_documents",
    )
    notes = models.TextField(blank=True)
    ai_summary = models.TextField(blank=True, help_text="AI-generated summary of the document.")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Tender Document"
        constraints = [
            models.UniqueConstraint(
                fields=["tender", "title", "revision"],
                name="uniq_tender_document_title_revision",
            )
        ]
        indexes = [
            models.Index(fields=["tender", "is_superseded"], name="tenderdoc_tender_super_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.revision})"

    @property
    def filename(self) -> str:
        return self.file.name.rsplit("/", 1)[-1] if self.file else ""


class TenderMessage(TimeStampedUUIDModel):
    """Append-only per-tender discussion message (fanned out live via Ably)."""

    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tender_messages",
    )
    body = models.TextField()

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Tender Message"
        indexes = [
            models.Index(fields=["tender", "created_at"], name="tendermsg_tender_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.author} on {self.tender.reference}"


class AIJobKind(models.TextChoices):
    ASK = "ask", "Tender Q&A"
    EMAIL = "email", "Client email draft"
    DESCRIPTION = "description", "Description draft"


class AIJobStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"


class AIJob(TimeStampedUUIDModel):
    """A durable, pollable AI request. Interactive AI never runs in the request
    cycle: the view enqueues an AIJob, Celery runs the (slow, local) model, and
    the browser polls for the result. Persisting the job gives observability and
    keeps a wedged model off the web workers."""

    kind = models.CharField(max_length=20, choices=AIJobKind.choices)
    status = models.CharField(
        max_length=20, choices=AIJobStatus.choices, default=AIJobStatus.PENDING
    )
    params = models.JSONField(default=dict, blank=True)
    result = models.TextField(blank=True)
    error = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_jobs",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "AI Job"
        indexes = [
            models.Index(fields=["requested_by", "status"], name="aijob_requester_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} ({self.get_status_display()})"


# Audit trail via simple_history's register() API (per spec), keeping the model
# body free of the HistoricalRecords descriptor.
simple_history.register(Tender)
