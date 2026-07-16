from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import AIJob, Tender, TenderDocument, TenderMessage


class TenderDocumentInline(admin.TabularInline):
    model = TenderDocument
    extra = 0
    fields = (
        "title",
        "revision",
        "file",
        "file_size_bytes",
        "mime_type",
        "processing_status",
        "is_superseded",
        "uploaded_by",
    )
    readonly_fields = (
        "file",
        "file_size_bytes",
        "mime_type",
        "processing_status",
        "is_superseded",
        "revision",
        "uploaded_by",
    )

    def has_add_permission(self, request, obj=None) -> bool:
        # Documents are uploaded through the staff tool (S3/R2 + Celery), never
        # attached directly in the admin.
        return False


@admin.register(Tender)
class TenderAdmin(SimpleHistoryAdmin):
    list_display = (
        "reference",
        "title",
        "client_name",
        "status",
        "deadline",
        "created_by",
    )
    list_filter = ("status", "sector")
    search_fields = ("title", "client_name", "reference")
    readonly_fields = (
        "reference",
        "created_by",
        "status_changed_at",
        "public_id",
        "created_at",
        "updated_at",
    )
    filter_horizontal = ("assigned_to",)
    inlines = [TenderDocumentInline]
    fieldsets = (
        (
            "Identity",
            {"fields": ("reference", "public_id", "title", "client_name", "client_email")},
        ),
        ("Classification", {"fields": ("sector", "estimated_value", "deadline")}),
        ("Status", {"fields": ("status", "status_changed_at")}),
        ("Content", {"fields": ("description", "notes")}),
        ("People", {"fields": ("created_by", "assigned_to")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(TenderDocument)
class TenderDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "revision",
        "tender",
        "processing_status",
        "is_superseded",
        "uploaded_by",
        "created_at",
    )
    list_filter = ("processing_status", "is_superseded")
    search_fields = ("title", "tender__reference", "tender__title")
    readonly_fields = (
        "file",
        "file_size_bytes",
        "mime_type",
        "processing_status",
        "uploaded_by",
        "public_id",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request) -> bool:
        return False


@admin.register(TenderMessage)
class TenderMessageAdmin(admin.ModelAdmin):
    list_display = ("tender", "author", "created_at")
    search_fields = ("tender__reference", "body")
    readonly_fields = ("tender", "author", "body", "public_id", "created_at", "updated_at")

    def has_add_permission(self, request) -> bool:
        return False


@admin.register(AIJob)
class AIJobAdmin(admin.ModelAdmin):
    list_display = ("kind", "status", "requested_by", "created_at")
    list_filter = ("kind", "status")
    readonly_fields = (
        "kind",
        "status",
        "params",
        "result",
        "error",
        "requested_by",
        "public_id",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request) -> bool:
        return False
