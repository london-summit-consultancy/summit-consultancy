from django.db import models

from apps.services.models import BuyerType

_ALLOWED_TRANSITIONS: dict[str, list[str]] = {}


class InquiryStatus(models.TextChoices):
    NEW = "new", "New"
    CONTACTED = "contacted", "Contacted"
    QUALIFIED = "qualified", "Qualified"
    CLOSED_WON = "won", "Closed — Won"
    CLOSED_LOST = "lost", "Closed — Lost"


_ALLOWED_TRANSITIONS = {
    InquiryStatus.NEW: [InquiryStatus.CONTACTED],
    InquiryStatus.CONTACTED: [InquiryStatus.QUALIFIED, InquiryStatus.CLOSED_LOST],
    InquiryStatus.QUALIFIED: [InquiryStatus.CLOSED_WON, InquiryStatus.CLOSED_LOST],
}


class Inquiry(models.Model):
    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    company = models.CharField(max_length=120, blank=True)
    buyer_type = models.CharField(max_length=20, choices=BuyerType.choices, blank=True)
    service = models.ForeignKey(
        "services.Service",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inquiries",
    )
    project_desc = models.TextField(verbose_name="Project Description")
    budget_range = models.CharField(max_length=80, blank=True)
    website = models.CharField(max_length=200, blank=True)  # honeypot
    status = models.CharField(
        max_length=20, choices=InquiryStatus.choices, default=InquiryStatus.NEW
    )
    source_page = models.CharField(max_length=200, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Inquiry"
        verbose_name_plural = "Inquiries"
        indexes = [
            # Admin pipeline: most common view — new inquiries first
            models.Index(fields=["status", "-created_at"], name="inquiry_status_date_idx"),
            # Admin date hierarchy filter
            models.Index(fields=["-created_at"], name="inquiry_created_idx"),
            # Pipeline filter: buyer type + status (e.g. all contractors in qualified)
            models.Index(fields=["buyer_type", "status"], name="inquiry_buyer_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} <{self.email}> — {self.get_status_display()}"

    def transition_to(self, new_status: str) -> None:
        allowed = _ALLOWED_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from {self.status!r} to {new_status!r}. "
                f"Allowed next states: {allowed}"
            )
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])
