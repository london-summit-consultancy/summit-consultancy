from django.db import models


class BuyerType(models.TextChoices):
    CLIENT = "client", "Client"
    CONTRACTOR = "contractor", "Contractor"
    CONSULTANCY = "consultancy", "Consultancy"


class ServiceCategory(models.Model):
    buyer_type = models.CharField(max_length=20, choices=BuyerType.choices, unique=True)
    headline = models.CharField(max_length=120)
    description = models.TextField()
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order"]
        verbose_name = "Service Category"
        verbose_name_plural = "Service Categories"

    def __str__(self) -> str:
        return self.headline


class Service(models.Model):
    category = models.ForeignKey(ServiceCategory, on_delete=models.PROTECT, related_name="services")
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    short_desc = models.CharField(max_length=200)
    body = models.TextField()
    icon = models.CharField(max_length=60, blank=True)
    image = models.ImageField(upload_to="services/", blank=True)
    is_featured = models.BooleanField(default=False)
    display_order = models.PositiveSmallIntegerField(default=0)
    meta_title = models.CharField(max_length=60, blank=True)
    meta_desc = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["category__display_order", "display_order"]
        verbose_name = "Service"
        indexes = [
            # HomeView: featured services (filter is_featured=True)
            models.Index(fields=["is_featured"], name="service_featured_idx"),
            # Landing page / admin: within-category ordering
            models.Index(fields=["category", "display_order"], name="service_cat_order_idx"),
        ]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        from django.urls import reverse

        return reverse("services:detail", kwargs={"slug": self.slug})

    @property
    def effective_meta_title(self) -> str:
        return self.meta_title or self.name

    @property
    def effective_meta_desc(self) -> str:
        return self.meta_desc or self.short_desc
