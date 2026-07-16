from dataclasses import dataclass

from django.core.validators import FileExtensionValidator
from django.db import models
from django_prose_editor.fields import ProseEditorField
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFit
from simple_history.models import HistoricalRecords

from apps.core.prose import RICH_TEXT_EXTENSIONS

# Trade-accurate labels for each export format. Shown to visitors so an engineer
# knows exactly what a file is before spending bandwidth on it.
DESIGN_FORMAT_LABELS = {
    "glb": "Interactive 3D model",
    "gltf": "Interactive 3D model",
    "ifc": "BIM model (IFC)",
    "dwg": "AutoCAD drawing",
    "dxf": "CAD exchange file",
    "nwd": "Navisworks model",
    "pdf": "Vector drawing sheet",
    "dwfx": "Design Web Format sheet",
}

# Formats the in-browser <model-viewer> can render live. Everything else is
# offered as a download only.
VIEWABLE_3D_FORMATS = ("glb", "gltf")


@dataclass(frozen=True, slots=True)
class DesignExport:
    """A single construction deliverable, resolved for template rendering.

    Carries pre-computed metadata (format, cached size) so the template never
    touches the storage backend — critical on S3, where `FieldFile.size` /
    `.url` lookups would otherwise fire a network call per file, per request.
    """

    kind: str  # "model" | "cad" | "blueprint"
    label: str
    description: str
    url: str
    fmt: str  # upper-case extension, e.g. "DWG"
    size: int | None  # bytes, cached at upload; None if unknown
    interactive: bool  # rendered live in the viewer
    action: str  # call-to-action verb


class Sector(models.TextChoices):
    INFRASTRUCTURE = "infrastructure", "Infrastructure"
    CONSTRUCTION = "construction", "Construction"


class CompletionStatus(models.TextChoices):
    COMPLETED = "completed", "Completed"
    ONGOING = "ongoing", "Ongoing"
    IN_DESIGN = "in_design", "In Design / Pre-Construction"


class Project(models.Model):
    # Identity
    title = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    client_name = models.CharField(max_length=100, blank=True)

    # Construction classification
    sector = models.CharField(max_length=30, choices=Sector.choices)
    completion_status = models.CharField(
        max_length=20,
        choices=CompletionStatus.choices,
        default=CompletionStatus.COMPLETED,
        verbose_name="Project Status",
    )
    services_used = models.ManyToManyField("services.Service", related_name="projects", blank=True)

    # Location & programme
    location = models.CharField(max_length=120)
    year = models.PositiveSmallIntegerField(verbose_name="Completion / Start Year")

    # Construction-specific metrics
    project_value = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="Contract Value",
        help_text="e.g. £5M–£10M",
    )
    gross_internal_area = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Gross Internal Area (m²)",
    )
    programme_months = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Programme Duration (months)",
    )

    # Content
    summary = models.TextField(max_length=500)
    body = ProseEditorField(extensions=RICH_TEXT_EXTENSIONS, sanitize=True)
    cover_image = models.ImageField(upload_to="portfolio/covers/")

    # Construction design exports
    #   Public-facing downloads/renders. Extensions are validated on save so an
    #   editor can't upload a format the front-end viewer/downloader can't handle.
    model_3d = models.FileField(
        upload_to="portfolio/models_3d/",
        blank=True,
        max_length=200,
        validators=[FileExtensionValidator(allowed_extensions=["glb", "gltf", "ifc"])],
        verbose_name="3D Interactive Model",
        help_text="Interactive browser model. .glb / .gltf render live in the viewer; "
        ".ifc is offered as a download (not browser-renderable). Export uncompressed "
        "(no Draco/Meshopt) so it renders under the site's strict CSP.",
    )
    cad_file = models.FileField(
        upload_to="portfolio/cad/",
        blank=True,
        max_length=200,
        validators=[FileExtensionValidator(allowed_extensions=["dwg", "dxf", "nwd"])],
        verbose_name="CAD Download",
        help_text="Raw engineering / infrastructure layout for download — .dwg, .dxf or .nwd.",
    )
    blueprint_sheet = models.FileField(
        upload_to="portfolio/blueprints/",
        blank=True,
        max_length=200,
        validators=[FileExtensionValidator(allowed_extensions=["pdf", "dwfx"])],
        verbose_name="Blueprint Sheet",
        help_text="High-fidelity 2D sheet — vector .pdf or .dwfx.",
    )
    # File sizes captured at upload time. Populated in save() from the pending
    # upload (a local read) so the public page can show sizes without a storage
    # round-trip on S3 for every render.
    model_3d_size = models.PositiveBigIntegerField(null=True, blank=True, editable=False)
    cad_file_size = models.PositiveBigIntegerField(null=True, blank=True, editable=False)
    blueprint_sheet_size = models.PositiveBigIntegerField(null=True, blank=True, editable=False)

    # Visibility & ordering
    is_featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    display_order = models.PositiveSmallIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-year", "display_order"]
        verbose_name = "Project"
        indexes = [
            # Primary list query: published projects ordered by year then display_order
            models.Index(
                fields=["is_published", "-year", "display_order"],
                name="portfolio_project_list_idx",
            ),
            # Homepage query: published + featured
            models.Index(
                fields=["is_published", "is_featured"],
                name="portfolio_project_featured_idx",
            ),
            # Portfolio filter: published + sector
            models.Index(
                fields=["is_published", "sector"],
                name="portfolio_project_sector_idx",
            ),
            # Sitemap lastmod + history ordering
            models.Index(
                fields=["-updated_at"],
                name="portfolio_project_updated_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        from django.urls import reverse

        return reverse("portfolio:detail", kwargs={"slug": self.slug})

    # Maps each file field to the column caching its size.
    _EXPORT_SIZE_FIELDS = (
        ("model_3d", "model_3d_size"),
        ("cad_file", "cad_file_size"),
        ("blueprint_sheet", "blueprint_sheet_size"),
    )

    def save(self, *args, **kwargs) -> None:
        # Cache each export's size before super().save() commits the upload to
        # storage. An uncommitted FieldFile reports `.size` from the local
        # upload (no network); a committed one would hit S3, so we only read the
        # freshly-attached files and leave already-stored ones untouched.
        for file_attr, size_attr in self._EXPORT_SIZE_FIELDS:
            field_file = getattr(self, file_attr)
            if not field_file:
                setattr(self, size_attr, None)
            elif not field_file._committed:
                setattr(self, size_attr, field_file.size)
        super().save(*args, **kwargs)

    @staticmethod
    def _export_format(field_file) -> str:
        """Lower-case extension of a stored file, e.g. 'glb'."""
        return field_file.name.rsplit(".", 1)[-1].lower()

    @property
    def has_design_exports(self) -> bool:
        """Any construction export present — gates the whole exports section."""
        return bool(self.model_3d or self.cad_file or self.blueprint_sheet)

    @property
    def model_3d_is_interactive(self) -> bool:
        """True only for formats the in-browser <model-viewer> can render (.glb/.gltf)."""
        return bool(self.model_3d) and self._export_format(self.model_3d) in VIEWABLE_3D_FORMATS

    @property
    def design_exports(self) -> list[DesignExport]:
        """All attached deliverables, resolved for the template in one pass.

        Reads only cached sizes and lazily-built URLs — no storage round-trips —
        so it is safe to iterate in a request-cycle template on S3.
        """
        exports: list[DesignExport] = []
        if self.model_3d:
            fmt = self._export_format(self.model_3d)
            interactive = fmt in VIEWABLE_3D_FORMATS
            exports.append(
                DesignExport(
                    kind="model",
                    label="3D model" if interactive else "BIM model",
                    description=DESIGN_FORMAT_LABELS.get(fmt, "3D model"),
                    url=self.model_3d.url,
                    fmt=fmt.upper(),
                    size=self.model_3d_size,
                    interactive=interactive,
                    action="Download source" if interactive else "Download",
                )
            )
        if self.cad_file:
            fmt = self._export_format(self.cad_file)
            exports.append(
                DesignExport(
                    kind="cad",
                    label="CAD layout",
                    description=DESIGN_FORMAT_LABELS.get(fmt, "CAD file"),
                    url=self.cad_file.url,
                    fmt=fmt.upper(),
                    size=self.cad_file_size,
                    interactive=False,
                    action="Download",
                )
            )
        if self.blueprint_sheet:
            fmt = self._export_format(self.blueprint_sheet)
            exports.append(
                DesignExport(
                    kind="blueprint",
                    label="Blueprint sheet",
                    description=DESIGN_FORMAT_LABELS.get(fmt, "Drawing sheet"),
                    url=self.blueprint_sheet.url,
                    fmt=fmt.upper(),
                    size=self.blueprint_sheet_size,
                    interactive=False,
                    action="View sheet",
                )
            )
        return exports


class ProjectImage(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="portfolio/gallery/")
    # Derived renditions (imagekit generates & caches on first access; no DB column).
    card_thumbnail = ImageSpecField(
        source="image",
        processors=[ResizeToFit(800, 600)],
        format="JPEG",
        options={"quality": 85},
    )
    hero_thumbnail = ImageSpecField(
        source="image",
        processors=[ResizeToFit(1920, 1080)],
        format="JPEG",
        options={"quality": 85},
    )
    caption = models.CharField(max_length=200, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order"]
        verbose_name = "Project Image"

    def __str__(self) -> str:
        return f"{self.project.title} — image {self.display_order}"
