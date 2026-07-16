import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.portfolio.models import Project, Sector


@pytest.fixture
def published_project(db, service):
    p = Project.objects.create(
        title="City Centre Office Development",
        slug="city-centre-office",
        sector=Sector.CONSTRUCTION,
        location="Birmingham",
        year=2024,
        summary="A modern office complex in central Birmingham.",
        body="Full project description here.",
        cover_image="",
        is_published=True,
    )
    p.services_used.add(service)
    return p


@pytest.fixture
def unpublished_project(db):
    return Project.objects.create(
        title="Unpublished Project",
        slug="unpublished-project",
        sector=Sector.INFRASTRUCTURE,
        location="Coventry",
        year=2023,
        summary="Draft project.",
        body="Draft.",
        cover_image="",
        is_published=False,
    )


class TestPortfolioListView:
    def test_shows_published_only(self, client, published_project, unpublished_project):
        response = client.get(reverse("portfolio:list"))
        assert response.status_code == 200
        assert published_project in response.context["projects"]
        assert unpublished_project not in response.context["projects"]

    def test_filter_by_sector(self, client, published_project):
        response = client.get(reverse("portfolio:list") + "?sector=construction")
        assert response.status_code == 200
        assert published_project in response.context["projects"]

    def test_filter_excludes_wrong_sector(self, client, published_project):
        response = client.get(reverse("portfolio:list") + "?sector=infrastructure")
        assert published_project not in response.context["projects"]

    def test_filter_by_service_slug(self, client, published_project, service):
        url = reverse("portfolio:list") + f"?service={service.slug}"
        response = client.get(url)
        assert published_project in response.context["projects"]

    def test_htmx_request_returns_partial(self, client, published_project):
        response = client.get(reverse("portfolio:list"), HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert response.templates[0].name == "partials/_project_cards.html"

    def test_full_request_returns_full_page(self, client, published_project):
        response = client.get(reverse("portfolio:list"))
        assert response.templates[0].name == "portfolio/list.html"


class TestProjectDetailView:
    def test_published_project_accessible(self, client, published_project):
        response = client.get(published_project.get_absolute_url())
        assert response.status_code == 200

    def test_unpublished_project_returns_404(self, client, unpublished_project):
        response = client.get(unpublished_project.get_absolute_url())
        assert response.status_code == 404


@pytest.fixture(autouse=True)
def _isolated_media(tmp_path, settings):
    """Write any uploaded export files to a throwaway dir, not the real media root."""
    settings.MEDIA_ROOT = tmp_path


class TestDesignExports:
    def _project(self, **files) -> Project:
        return Project.objects.create(
            title="Riverside Interchange",
            slug="riverside-interchange",
            sector=Sector.INFRASTRUCTURE,
            location="Leeds",
            year=2025,
            summary="A grade-separated interchange.",
            body="Body.",
            cover_image="",
            is_published=True,
            **files,
        )

    def test_no_exports_by_default(self, db):
        project = self._project()
        assert project.has_design_exports is False
        assert project.design_exports == []

    def test_glb_is_interactive_and_size_cached(self, db):
        upload = SimpleUploadedFile(
            "tower.glb", b"glTF-binary-bytes", content_type="model/gltf-binary"
        )
        project = self._project(model_3d=upload)

        assert project.model_3d_is_interactive is True
        # Size captured at save from the local upload — no storage round-trip.
        assert project.model_3d_size == len(b"glTF-binary-bytes")

        (export,) = project.design_exports
        assert export.kind == "model"
        assert export.interactive is True
        assert export.fmt == "GLB"
        assert export.action == "Download source"

    def test_ifc_is_download_only(self, db):
        upload = SimpleUploadedFile(
            "plant.ifc", b"ISO-10303-21", content_type="application/octet-stream"
        )
        project = self._project(model_3d=upload)

        assert project.model_3d_is_interactive is False
        (export,) = project.design_exports
        assert export.label == "BIM model"
        assert export.description == "BIM model (IFC)"
        assert export.action == "Download"

    def test_all_three_exports_resolved_in_order(self, db):
        project = self._project(
            model_3d=SimpleUploadedFile("m.gltf", b"a", content_type="model/gltf+json"),
            cad_file=SimpleUploadedFile("layout.dwg", b"bb", content_type="application/acad"),
            blueprint_sheet=SimpleUploadedFile("sheet.pdf", b"ccc", content_type="application/pdf"),
        )
        kinds = [e.kind for e in project.design_exports]
        assert kinds == ["model", "cad", "blueprint"]
        assert project.cad_file_size == 2
        assert project.blueprint_sheet_size == 3
        blueprint = project.design_exports[-1]
        assert blueprint.action == "View sheet"

    def test_disallowed_extension_rejected(self, db):
        project = self._project()
        project.cad_file = SimpleUploadedFile(
            "evil.exe", b"MZ", content_type="application/octet-stream"
        )
        with pytest.raises(ValidationError):
            project.full_clean()

    def test_clearing_file_resets_cached_size(self, db):
        project = self._project(
            model_3d=SimpleUploadedFile("t.glb", b"xyz", content_type="model/gltf-binary")
        )
        assert project.model_3d_size == 3
        project.model_3d.delete(save=False)
        project.model_3d = None
        project.save()
        project.refresh_from_db()
        assert project.model_3d_size is None

    def test_detail_page_renders_viewer_for_interactive_model(self, client, db):
        project = self._project(
            model_3d=SimpleUploadedFile("t.glb", b"xyz", content_type="model/gltf-binary")
        )
        response = client.get(project.get_absolute_url())
        body = response.content.decode()
        assert response.status_code == 200
        assert "<model-viewer" in body
        assert "js/model-viewer.min.js" in body

    def test_detail_page_no_viewer_script_without_model(self, client, db):
        project = self._project(
            cad_file=SimpleUploadedFile("l.dxf", b"ab", content_type="image/vnd.dxf")
        )
        response = client.get(project.get_absolute_url())
        body = response.content.decode()
        assert "js/model-viewer.min.js" not in body
        assert 'id="design-exports"' in body
