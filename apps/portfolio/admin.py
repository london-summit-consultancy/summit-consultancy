from django.contrib import admin
from django.template.defaultfilters import filesizeformat
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe
from simple_history.admin import SimpleHistoryAdmin

from .models import Project, ProjectImage


class ProjectImageInline(admin.TabularInline):
    model = ProjectImage
    extra = 1
    fields = ["image", "caption", "display_order"]


@admin.register(Project)
class ProjectAdmin(SimpleHistoryAdmin):
    list_display = [
        "title",
        "sector",
        "completion_status",
        "year",
        "project_value",
        "has_exports",
        "is_featured",
        "is_published",
    ]
    list_editable = ["is_featured", "is_published"]
    list_filter = ["sector", "completion_status", "is_published", "is_featured", "year"]
    search_fields = ["title", "client_name", "location"]
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ["services_used"]
    readonly_fields = ["exports_summary"]
    inlines = [ProjectImageInline]
    actions = ["publish_selected", "unpublish_selected"]
    fieldsets = (
        (
            "Project Info",
            {
                "fields": (
                    "title",
                    "slug",
                    "client_name",
                    "sector",
                    "completion_status",
                    "location",
                    "year",
                )
            },
        ),
        (
            "Construction Metrics",
            {
                "fields": ("project_value", "gross_internal_area", "programme_months"),
                "classes": ("collapse",),
            },
        ),
        ("Content", {"fields": ("summary", "body", "cover_image", "services_used")}),
        (
            "Design Exports",
            {
                "fields": ("model_3d", "cad_file", "blueprint_sheet", "exports_summary"),
                "description": (
                    "Construction deliverables shown on the public project page. "
                    "3D model: .glb / .gltf (rendered live) or .ifc (download). "
                    "CAD: .dwg / .dxf / .nwd. Blueprint: vector .pdf / .dwfx."
                ),
                "classes": ("collapse",),
            },
        ),
        ("Display", {"fields": ("is_featured", "is_published", "display_order")}),
    )

    @admin.display(boolean=True, description="Deliverables")
    def has_exports(self, obj: Project) -> bool:
        return obj.has_design_exports

    @admin.display(description="Attached deliverables")
    def exports_summary(self, obj: Project):
        if obj.pk is None:
            return "Save the project to see attached files and sizes here."
        rows = []
        for field_file, size in (
            (obj.model_3d, obj.model_3d_size),
            (obj.cad_file, obj.cad_file_size),
            (obj.blueprint_sheet, obj.blueprint_sheet_size),
        ):
            if not field_file:
                continue
            fmt = field_file.name.rsplit(".", 1)[-1].upper()
            human = filesizeformat(size) if size else "size unknown"
            rows.append((f"{fmt} · {human}",))
        return format_html_join(mark_safe("<br>"), "{}", rows) or "None attached yet."

    @admin.action(description="Publish selected projects")
    def publish_selected(self, request, queryset) -> None:
        # Iterate per instance so simple_history records each change with user attribution.
        # queryset.update() bypasses post_save signals and would produce no history entries.
        for project in queryset:
            if not project.is_published:
                project.is_published = True
                project.save(update_fields=["is_published"])

    @admin.action(description="Unpublish selected projects")
    def unpublish_selected(self, request, queryset) -> None:
        for project in queryset:
            if project.is_published:
                project.is_published = False
                project.save(update_fields=["is_published"])
