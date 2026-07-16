from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Service, ServiceCategory


class ServiceInline(admin.TabularInline):
    model = Service
    extra = 0
    fields = ["name", "slug", "short_desc", "is_featured", "display_order"]
    prepopulated_fields = {"slug": ("name",)}
    show_change_link = True


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ["headline", "buyer_type", "display_order"]
    list_editable = ["display_order"]
    inlines = [ServiceInline]


@admin.register(Service)
class ServiceAdmin(SimpleHistoryAdmin):
    list_display = ["name", "category", "is_featured", "display_order"]
    list_editable = ["is_featured", "display_order"]
    list_filter = ["category", "is_featured"]
    search_fields = ["name", "short_desc"]
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        (
            "Content",
            {"fields": ("category", "name", "slug", "short_desc", "body", "icon", "image")},
        ),
        ("Display", {"fields": ("is_featured", "display_order")}),
        ("SEO", {"fields": ("meta_title", "meta_desc")}),
    )
