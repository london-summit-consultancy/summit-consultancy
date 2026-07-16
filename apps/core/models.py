import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.cache import cache
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django_prose_editor.fields import ProseEditorField
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill, ResizeToFit

from .prose import RICH_TEXT_EXTENSIONS


class TimeStampedUUIDModel(models.Model):
    """Abstract base: a stable, non-guessable ``public_id`` for external URLs
    (PKs are never exposed) plus created/updated audit timestamps.

    Introduced with Phase 2B (tenders). Existing pre-2B models keep their
    integer-PK + inline-timestamp shape; new models should inherit this.
    """

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UserManager(BaseUserManager):
    """Manager for the email-as-username custom user."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields) -> "User":
        if not email:
            raise ValueError("Users must have an email address.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields) -> "User":
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user: email is the identifier, PKs are never exposed (``public_id``).

    Introduced in Phase 2B to back the staff-only tender tool and Google SSO.
    """

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    is_staff = models.BooleanField(
        default=False,
        help_text="Designates whether the user can log into the admin site and the tender tool.",
    )
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["email"]

    def __str__(self) -> str:
        return self.email

    def get_full_name(self) -> str:
        return self.full_name or self.email

    def get_short_name(self) -> str:
        return self.full_name.split(" ")[0] if self.full_name else self.email


class SiteSettings(models.Model):
    brand_name = models.CharField(max_length=100, default="London Summit Consultancy")
    tagline = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    linkedin_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    logo = models.ImageField(upload_to="brand/", blank=True)
    # Small logo rendition for the nav/footer (imagekit-derived, no DB column).
    logo_thumbnail = ImageSpecField(
        source="logo",
        processors=[ResizeToFit(200, 80)],
        format="JPEG",
        options={"quality": 85},
    )
    favicon = models.ImageField(upload_to="brand/", blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    footer_location_text = models.CharField(
        max_length=300,
        blank=True,
        help_text="Footer line, e.g. 'Serving clients across the Kingdom of Saudi Arabia.'",
    )
    about_meta_description = models.TextField(
        blank=True,
        help_text="SEO meta description for the About page.",
    )
    services_meta_description = models.TextField(
        blank=True,
        help_text="SEO meta description for the Services landing page.",
    )
    portfolio_meta_description = models.TextField(
        blank=True,
        help_text="SEO meta description for the Portfolio page.",
    )
    company_registration = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="Companies House Registration No.",
        help_text="Companies House registration number (e.g. 12345678)",
    )
    founded_year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Founded Year",
        help_text="Year the company was founded — appears in structured data",
    )

    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"

    def __str__(self) -> str:
        return self.brand_name

    def save(self, *args, **kwargs) -> None:
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "SiteSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


@receiver(post_save, sender=SiteSettings)
def clear_site_settings_cache(sender, **kwargs) -> None:
    cache.delete("site_settings")


class HeroSection(models.Model):
    headline = models.CharField(max_length=120)
    subheadline = models.TextField(max_length=300)
    cta_label = models.CharField(max_length=40, default="Get in Touch")
    cta_url = models.CharField(max_length=200, default="/contact/")
    background = models.ImageField(upload_to="hero/", blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Hero Section"

    def __str__(self) -> str:
        return self.headline


class AboutSection(models.Model):
    headline = models.CharField(max_length=120)
    body = ProseEditorField(extensions=RICH_TEXT_EXTENSIONS, sanitize=True)
    image = models.ImageField(upload_to="about/", blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "About Section"

    def __str__(self) -> str:
        return self.headline

    def save(self, *args, **kwargs) -> None:
        self.pk = 1
        super().save(*args, **kwargs)


class Testimonial(models.Model):
    client_name = models.CharField(max_length=100)
    client_title = models.CharField(max_length=100)
    headline = models.CharField(
        max_length=120,
        blank=True,
        help_text="Optional short, bold card title, e.g. 'Delivered ahead of programme'.",
    )
    quote = models.TextField()
    avatar = models.ImageField(
        upload_to="testimonials/",
        blank=True,
        help_text="Optional client headshot. When empty, the client's initials are shown instead.",
    )
    # Square, retina-ready crop generated on first access (no DB column).
    avatar_thumb = ImageSpecField(
        source="avatar",
        processors=[ResizeToFill(128, 128)],
        format="JPEG",
        options={"quality": 85},
    )
    is_visible = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order"]
        verbose_name = "Testimonial"

    def __str__(self) -> str:
        return f"{self.client_name} — {self.client_title}"

    @property
    def initials(self) -> str:
        """Monogram fallback derived from the real client name (max two letters)."""
        parts = [word for word in self.client_name.split() if word]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()
