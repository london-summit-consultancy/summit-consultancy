import re
from datetime import date
from unittest.mock import MagicMock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.tenders import views as tender_views
from apps.tenders.models import (
    DocumentProcessingStatus,
    Tender,
    TenderDocument,
    TenderStatus,
)
from apps.tenders.tasks import process_document_upload

from .factories import StaffUserFactory, TenderDocumentFactory, TenderFactory


@pytest.fixture
def staff_user(db):
    return StaffUserFactory()


@pytest.fixture
def staff_client(client, staff_user):
    client.force_login(staff_user)
    return client


# --------------------------------------------------------------------------
# Reference auto-generation
# --------------------------------------------------------------------------
class TestTenderReference:
    def test_reference_format_sequential_and_unique(self, db):
        year = timezone.localdate().year
        refs = [TenderFactory().reference for _ in range(3)]

        prefix = "London Summit Consultancy Limited"
        assert refs == [f"{prefix}-{year}-001", f"{prefix}-{year}-002", f"{prefix}-{year}-003"]
        assert len(set(refs)) == 3
        for ref in refs:
            assert re.fullmatch(rf"{re.escape(prefix)}-{year}-\d{{3}}", ref)

    def test_reference_is_not_regenerated_on_update(self, db):
        tender = TenderFactory()
        original = tender.reference
        tender.title = "Renamed"
        tender.save()
        tender.refresh_from_db()
        assert tender.reference == original


# --------------------------------------------------------------------------
# State machine
# --------------------------------------------------------------------------
class TestTenderStateMachine:
    def test_legal_transition_updates_status_and_timestamp(self, db):
        tender = TenderFactory(status=TenderStatus.DRAFT)
        tender.transition_to(TenderStatus.SUBMITTED)
        tender.refresh_from_db()
        assert tender.status == TenderStatus.SUBMITTED
        assert tender.status_changed_at is not None

    def test_illegal_transition_raises_value_error(self, db):
        tender = TenderFactory(status=TenderStatus.DRAFT)
        with pytest.raises(ValueError):
            tender.transition_to(TenderStatus.WON)

    def test_any_state_can_reset_to_draft(self, db):
        tender = TenderFactory(status=TenderStatus.SUBMITTED)
        assert tender.can_transition_to(TenderStatus.DRAFT) is True

    def test_status_view_rejects_illegal_transition_with_403(self, staff_client, db):
        tender = TenderFactory(status=TenderStatus.DRAFT)
        url = reverse("tenders:status", kwargs={"public_id": tender.public_id})
        response = staff_client.post(url, {"status": TenderStatus.WON})
        assert response.status_code == 403
        tender.refresh_from_db()
        assert tender.status == TenderStatus.DRAFT

    def test_status_view_applies_legal_transition(self, staff_client, settings, db):
        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"
        tender = TenderFactory(status=TenderStatus.DRAFT)
        url = reverse("tenders:status", kwargs={"public_id": tender.public_id})
        response = staff_client.post(
            url, {"status": TenderStatus.SUBMITTED}, HTTP_HX_REQUEST="true"
        )
        assert response.status_code == 200
        tender.refresh_from_db()
        assert tender.status == TenderStatus.SUBMITTED


# --------------------------------------------------------------------------
# Document upload view
# --------------------------------------------------------------------------
class TestDocumentUpload:
    def _upload(self, staff_client, tender, upload, **extra):
        url = reverse("tenders:document_upload", kwargs={"public_id": tender.public_id})
        data = {"title": "Drawings", "revision": "Rev A", "file": upload}
        data.update(extra)
        return staff_client.post(url, data, HTTP_HX_REQUEST="true")

    def test_valid_upload_enqueues_task_and_returns_202(self, staff_client, monkeypatch, db):
        mock_delay = MagicMock()
        monkeypatch.setattr(tender_views.process_document_upload, "delay", mock_delay)
        tender = TenderFactory()
        upload = SimpleUploadedFile(
            "plan.pdf", b"%PDF-1.4\n%test pdf body\n", content_type="application/pdf"
        )

        response = self._upload(staff_client, tender, upload)

        assert response.status_code == 202
        document = TenderDocument.objects.get(tender=tender, title="Drawings")
        assert document.processing_status == DocumentProcessingStatus.PROCESSING
        assert mock_delay.call_count == 1
        assert mock_delay.call_args.args[0] == str(document.public_id)

    def test_oversized_upload_returns_400(self, staff_client, monkeypatch, settings, db):
        monkeypatch.setattr(tender_views.process_document_upload, "delay", MagicMock())
        settings.TENDER_MAX_UPLOAD_BYTES = 8
        tender = TenderFactory()
        upload = SimpleUploadedFile(
            "plan.pdf", b"%PDF-1.4 this is longer than eight bytes", "application/pdf"
        )

        response = self._upload(staff_client, tender, upload)

        assert response.status_code == 400
        assert not TenderDocument.objects.filter(tender=tender).exists()

    def test_disallowed_mime_returns_400(self, staff_client, monkeypatch, db):
        monkeypatch.setattr(tender_views.process_document_upload, "delay", MagicMock())
        tender = TenderFactory()
        # Allowed extension, but the content sniffs as HTML — not permitted.
        upload = SimpleUploadedFile(
            "sneaky.pdf",
            b"<!DOCTYPE html><html><head><title>x</title></head><body>hi</body></html>",
            content_type="application/pdf",
        )

        response = self._upload(staff_client, tender, upload)

        assert response.status_code == 400
        assert not TenderDocument.objects.filter(tender=tender).exists()

    def test_disallowed_extension_returns_400(self, staff_client, monkeypatch, db):
        monkeypatch.setattr(tender_views.process_document_upload, "delay", MagicMock())
        tender = TenderFactory()
        upload = SimpleUploadedFile("malware.exe", b"MZ\x00\x00binary", "application/octet-stream")

        response = self._upload(staff_client, tender, upload)

        assert response.status_code == 400


# --------------------------------------------------------------------------
# process_document_upload task
# --------------------------------------------------------------------------
class TestProcessDocumentUpload:
    def test_marks_previous_same_title_documents_superseded(self, tmp_path, db):
        tender = TenderFactory()
        old = TenderDocumentFactory(
            tender=tender, title="Structural Drawings", revision="Rev A", is_superseded=False
        )
        new = TenderDocumentFactory(
            tender=tender,
            title="Structural Drawings",
            revision="Rev B",
            processing_status=DocumentProcessingStatus.PROCESSING,
        )
        staging = tmp_path / "drawings.pdf"
        staging.write_bytes(b"%PDF-1.4\n%structural drawings\n")

        process_document_upload(str(new.public_id), str(staging), "drawings.pdf")

        old.refresh_from_db()
        new.refresh_from_db()
        assert old.is_superseded is True
        assert new.is_superseded is False
        assert new.processing_status == DocumentProcessingStatus.READY
        assert new.file_size_bytes and new.file_size_bytes > 0
        assert new.mime_type == "application/pdf"
        assert not staging.exists()  # staging cleaned up on success

        new.file.delete(save=False)  # keep the working tree clean


# --------------------------------------------------------------------------
# Access control
# --------------------------------------------------------------------------
class TestAccessControl:
    def _protected_urls(self, tender):
        return [
            reverse("tenders:list"),
            reverse("tenders:create"),
            reverse("tenders:detail", kwargs={"public_id": tender.public_id}),
            reverse("tenders:update", kwargs={"public_id": tender.public_id}),
        ]

    def test_anonymous_is_redirected_to_login(self, client, db):
        tender = TenderFactory()
        for url in self._protected_urls(tender):
            response = client.get(url)
            assert response.status_code == 302
            assert response.url.startswith("/internal/login/")

    def test_authenticated_non_staff_gets_403(self, client, db):
        member = StaffUserFactory(is_staff=False)
        client.force_login(member)
        tender = TenderFactory()
        for url in self._protected_urls(tender):
            response = client.get(url)
            assert response.status_code == 403

    def test_staff_can_view_list(self, staff_client, db):
        TenderFactory()
        response = staff_client.get(reverse("tenders:list"))
        assert response.status_code == 200


# --------------------------------------------------------------------------
# Template rendering smoke tests
# --------------------------------------------------------------------------
class TestStaffPagesRender:
    def test_detail_page_renders(self, staff_client, db):
        tender = TenderFactory(status=TenderStatus.SUBMITTED)
        TenderDocumentFactory(tender=tender, title="RFP", revision="Rev A")
        response = staff_client.get(
            reverse("tenders:detail", kwargs={"public_id": tender.public_id})
        )
        assert response.status_code == 200
        assert response.templates[0].name == "tenders/detail.html"
        assert tender.reference.encode() in response.content

    def test_create_form_renders(self, staff_client, db):
        response = staff_client.get(reverse("tenders:create"))
        assert response.status_code == 200
        assert response.templates[0].name == "tenders/form.html"


# --------------------------------------------------------------------------
# List view context
# --------------------------------------------------------------------------
class TestTenderListView:
    def test_pipeline_value_sums_draft_and_submitted_only(self, staff_client, db):
        TenderFactory(status=TenderStatus.DRAFT, estimated_value=100)
        TenderFactory(status=TenderStatus.SUBMITTED, estimated_value=250)
        TenderFactory(status=TenderStatus.WON, estimated_value=999)  # excluded

        response = staff_client.get(reverse("tenders:list"))
        assert response.status_code == 200
        assert response.context["pipeline_value"] == 350
        assert response.context["status_counts"]["won"] == 1

    def test_htmx_status_filter_returns_partial(self, staff_client, db):
        TenderFactory(status=TenderStatus.WON)
        response = staff_client.get(
            reverse("tenders:list"), {"status": "won"}, HTTP_HX_REQUEST="true"
        )
        assert response.status_code == 200
        assert response.templates[0].name == "tenders/partials/_tender_list.html"


# --------------------------------------------------------------------------
# Create view
# --------------------------------------------------------------------------
class TestTenderCreateView:
    def test_create_sets_created_by_and_reference(self, staff_client, staff_user, db):
        response = staff_client.post(
            reverse("tenders:create"),
            {
                "title": "New Bridge Contract",
                "client_name": "Highways Authority",
                "sector": "infrastructure",
                "description": "Design and build.",
                "deadline": date.today().isoformat(),
                "estimated_value": "1500000",
            },
        )
        assert response.status_code == 302
        tender = Tender.objects.get(title="New Bridge Contract")
        assert tender.created_by == staff_user
        assert tender.reference.startswith("London Summit Consultancy Limited-")
