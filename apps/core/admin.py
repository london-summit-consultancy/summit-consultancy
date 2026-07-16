import logging

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import AboutSection, HeroSection, SiteSettings, Testimonial, User

logger = logging.getLogger(__name__)


class UserCreationForm(forms.ModelForm):
    """Admin add-form: collects a raw password and hashes it on save."""

    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Password confirmation", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ("email", "full_name")

    def clean_password2(self) -> str:
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("The two password fields didn't match.")
        return p2

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    """Admin change-form: shows the hashed password read-only (edit via the link)."""

    password = ReadOnlyPasswordHashField()

    class Meta:
        model = User
        fields = (
            "email",
            "full_name",
            "password",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
            "user_permissions",
        )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = UserCreationForm
    form = UserChangeForm
    model = User
    list_display = ("email", "full_name", "is_staff", "is_active", "date_joined")
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("email", "full_name")
    ordering = ("email",)
    readonly_fields = ("public_id", "last_login", "date_joined")
    filter_horizontal = ("groups", "user_permissions")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("full_name", "public_id")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "password1", "password2"),
            },
        ),
    )

    def save_model(self, request, obj, form, change) -> None:
        super().save_model(request, obj, form, change)
        if change:
            return
        # New staff account: send the allauth verification email (via SMTP2GO)
        # and a branded welcome. Both are best-effort — never block admin save.
        try:
            from allauth.account.utils import send_email_confirmation

            send_email_confirmation(request, obj, signup=False)
        except Exception:
            logger.warning("Could not send verification email to %s", obj.email, exc_info=True)
        try:
            from .tasks import send_welcome_email

            send_welcome_email.delay(obj.pk)
        except Exception:
            logger.error("Could not enqueue welcome email for %s", obj.email, exc_info=True)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            "Branding",
            {"fields": ("brand_name", "tagline", "logo", "favicon", "footer_location_text")},
        ),
        ("Company Details", {"fields": ("company_registration", "founded_year")}),
        ("Contact", {"fields": ("email", "phone", "address")}),
        ("Social Media", {"fields": ("linkedin_url", "instagram_url")}),
        (
            "SEO",
            {
                "fields": (
                    "meta_description",
                    "about_meta_description",
                    "services_meta_description",
                    "portfolio_meta_description",
                )
            },
        ),
    )

    def has_add_permission(self, request) -> bool:
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def changelist_view(self, request, extra_context=None):
        obj = SiteSettings.objects.first()
        if obj:
            return HttpResponseRedirect(reverse("admin:core_sitesettings_change", args=[obj.pk]))
        return super().changelist_view(request, extra_context)


@admin.register(HeroSection)
class HeroSectionAdmin(admin.ModelAdmin):
    list_display = ["headline", "cta_label", "is_active"]
    list_editable = ["is_active"]


@admin.register(AboutSection)
class AboutSectionAdmin(admin.ModelAdmin):
    readonly_fields = ["updated_at"]

    def has_add_permission(self, request) -> bool:
        return not AboutSection.objects.exists()

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ["client_name", "client_title", "headline", "is_visible", "display_order"]
    list_editable = ["is_visible", "display_order"]
    list_filter = ["is_visible"]
    fields = [
        "client_name",
        "client_title",
        "avatar",
        "headline",
        "quote",
        "is_visible",
        "display_order",
    ]
