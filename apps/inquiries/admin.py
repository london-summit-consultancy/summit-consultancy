from django.contrib import admin, messages
from django.db import transaction
from django.utils.html import format_html

from .models import Inquiry, InquiryStatus

_STATUS_COLOURS = {
    InquiryStatus.NEW: "#2563eb",
    InquiryStatus.CONTACTED: "#d97706",
    InquiryStatus.QUALIFIED: "#16a34a",
    InquiryStatus.CLOSED_WON: "#15803d",
    InquiryStatus.CLOSED_LOST: "#6b7280",
}


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ["full_name", "email", "company", "buyer_type", "status_badge", "created_at"]
    list_filter = ["status", "buyer_type", "created_at"]
    search_fields = ["full_name", "email", "company", "project_desc"]
    readonly_fields = ["source_page", "ip_address", "website", "created_at", "updated_at"]
    date_hierarchy = "created_at"
    fieldsets = (
        ("Contact", {"fields": ("full_name", "email", "phone", "company", "buyer_type")}),
        ("Project", {"fields": ("service", "project_desc", "budget_range")}),
        ("Pipeline", {"fields": ("status", "notes")}),
        (
            "Metadata",
            {
                "fields": ("source_page", "ip_address", "created_at", "updated_at", "website"),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if not change or "status" not in form.changed_data:
            super().save_model(request, obj, form, change)
            return

        # Both writes (non-status fields + the status transition) happen in one
        # transaction: an invalid transition or a mid-write failure rolls the
        # whole change back, so we never persist a partial edit.
        with transaction.atomic():
            new_status = obj.status
            # Lock + restore DB state so transition_to reads the correct origin
            # state and no concurrent edit can race the transition.
            original = type(obj).objects.select_for_update().get(pk=obj.pk)
            obj.status = original.status

            # Persist non-status field changes (e.g. notes) before the transition
            other = [f for f in form.changed_data if f != "status"]
            if other:
                obj.save(update_fields=other + ["updated_at"])

            try:
                obj.transition_to(new_status)
            except ValueError as exc:
                # Roll back the non-status save too, then surface the reason.
                transaction.set_rollback(True)
                self.message_user(request, str(exc), messages.ERROR)

    @admin.display(description="Status")
    def status_badge(self, obj) -> str:
        colour = _STATUS_COLOURS.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;white-space:nowrap">{}</span>',
            colour,
            obj.get_status_display(),
        )
