import pytest
from django.core import mail
from django.urls import reverse

from apps.inquiries.models import Inquiry, InquiryStatus
from apps.portfolio.models import CompletionStatus, Project, Sector
from apps.tenders.models import TenderMessage, TenderStatus
from apps.tenders.tasks import send_client_tender_ack

from .factories import StaffUserFactory, TenderFactory


@pytest.fixture
def staff_client(client, db):
    client.force_login(StaffUserFactory())
    return client


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------
class TestDashboard:
    def test_dashboard_renders_for_staff(self, staff_client, db):
        TenderFactory(status=TenderStatus.WON, estimated_value=100)
        TenderFactory(status=TenderStatus.LOST)
        response = staff_client.get(reverse("tenders:dashboard"))
        assert response.status_code == 200
        assert response.templates[0].name == "tenders/dashboard.html"
        assert response.context["win_rate"] == 50.0

    def test_dashboard_includes_cross_app_analytics(self, staff_client, service, db):
        Inquiry.objects.create(
            full_name="Sarah Jones",
            email="sarah@example.com",
            project_desc="New office development.",
            status=InquiryStatus.CLOSED_WON,
            service=service,
        )
        Inquiry.objects.create(
            full_name="Tom Reed",
            email="tom@example.com",
            project_desc="Warehouse fit-out.",
            status=InquiryStatus.CLOSED_LOST,
        )
        project = Project.objects.create(
            title="City Centre Office Development",
            slug="city-centre-office",
            sector=Sector.CONSTRUCTION,
            completion_status=CompletionStatus.COMPLETED,
            location="Birmingham",
            year=2024,
            summary="A modern office complex in central Birmingham.",
            body="Full project description here.",
            cover_image="",
            is_published=True,
        )
        project.services_used.add(service)

        response = staff_client.get(reverse("tenders:dashboard"))

        assert response.status_code == 200
        assert response.context["total_inquiries"] == 2
        assert response.context["inquiry_win_rate"] == 50.0
        assert response.context["projects_delivered"] == 1
        assert response.context["services_offered"] == 1
        service_demand = response.context["charts"]["service_demand"]
        assert service_demand["labels"] == [service.name]
        assert service_demand["inquiries"] == [1]
        assert service_demand["projects"] == [1]

    def test_dashboard_requires_login(self, client, db):
        response = client.get(reverse("tenders:dashboard"))
        assert response.status_code == 302
        assert response.url.startswith("/internal/login/")


# --------------------------------------------------------------------------
# AI endpoints (Gemini disabled in tests → graceful 503 / validation)
# --------------------------------------------------------------------------
class TestAIEndpoints:
    def test_ask_requires_question(self, staff_client, db):
        tender = TenderFactory()
        url = reverse("tenders:ai_ask", kwargs={"public_id": tender.public_id})
        response = staff_client.post(url, {"question": ""})
        assert response.status_code == 400

    def test_ask_returns_503_when_ai_disabled(self, staff_client, db):
        tender = TenderFactory()
        url = reverse("tenders:ai_ask", kwargs={"public_id": tender.public_id})
        response = staff_client.post(url, {"question": "When is the deadline?"})
        assert response.status_code == 503

    def test_ask_enqueues_job_and_poll_returns_result(
        self, staff_client, settings, monkeypatch, db
    ):
        from apps.core import ai

        settings.DEEPSEEK_BASE_URL = "http://localhost:11434/v1"
        settings.CELERY_TASK_ALWAYS_EAGER = True
        monkeypatch.setattr(ai, "answer_tender_question", lambda *a, **k: "The deadline is Friday.")
        tender = TenderFactory()
        url = reverse("tenders:ai_ask", kwargs={"public_id": tender.public_id})

        response = staff_client.post(url, {"question": "When is the deadline?"})
        assert response.status_code == 202  # enqueued, not answered inline
        poll_url = response.json()["poll_url"]

        # Eager task already ran during the POST, so the job is ready.
        poll = staff_client.get(poll_url)
        assert poll.status_code == 200
        assert poll.json() == {"status": "ready", "result": "The deadline is Friday.", "error": ""}

    def test_ai_job_poll_scoped_to_requester(self, client, settings, monkeypatch, db):
        from apps.core import ai

        settings.DEEPSEEK_BASE_URL = "http://localhost:11434/v1"
        settings.CELERY_TASK_ALWAYS_EAGER = True
        monkeypatch.setattr(ai, "draft_tender_description", lambda *a, **k: "A draft.")
        client.force_login(StaffUserFactory())
        response = client.post(reverse("tenders:ai_draft_description"), {"title": "Bridge"})
        poll_url = response.json()["poll_url"]

        # A different staff user must not be able to read someone else's job.
        client.force_login(StaffUserFactory())
        assert client.get(poll_url).status_code == 404

    def test_draft_description_requires_title(self, staff_client, db):
        response = staff_client.post(reverse("tenders:ai_draft_description"), {"title": ""})
        assert response.status_code == 400

    def test_ai_endpoints_require_staff(self, client, db):
        member = StaffUserFactory(is_staff=False)
        client.force_login(member)
        tender = TenderFactory()
        url = reverse("tenders:ai_ask", kwargs={"public_id": tender.public_id})
        assert client.post(url, {"question": "x"}).status_code == 403


# --------------------------------------------------------------------------
# Chat + Ably token
# --------------------------------------------------------------------------
class TestChat:
    def test_post_message_persists_and_returns_row(self, staff_client, db):
        tender = TenderFactory()
        url = reverse("tenders:message_create", kwargs={"public_id": tender.public_id})
        response = staff_client.post(url, {"body": "Kicking off the bid."})
        assert response.status_code == 200
        assert b"Kicking off the bid." in response.content
        assert TenderMessage.objects.filter(tender=tender).count() == 1

    def test_empty_message_rejected(self, staff_client, db):
        tender = TenderFactory()
        url = reverse("tenders:message_create", kwargs={"public_id": tender.public_id})
        assert staff_client.post(url, {"body": "   "}).status_code == 400

    def test_ably_token_503_when_disabled(self, staff_client, db):
        response = staff_client.get(reverse("tenders:ably_token"))
        assert response.status_code == 503

    def test_message_create_requires_login(self, client, db):
        tender = TenderFactory()
        url = reverse("tenders:message_create", kwargs={"public_id": tender.public_id})
        assert client.post(url, {"body": "hi"}).status_code == 302


# --------------------------------------------------------------------------
# Client "we care" emails
# --------------------------------------------------------------------------
class TestClientEmails:
    def test_client_ack_emails_the_client(self, settings, db):
        settings.SEND_CLIENT_EMAILS = True
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        tender = TenderFactory(client_email="client@example.com")
        send_client_tender_ack(str(tender.public_id))
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["client@example.com"]

    def test_client_ack_skipped_without_email(self, settings, db):
        settings.SEND_CLIENT_EMAILS = True
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        tender = TenderFactory(client_email="")
        send_client_tender_ack(str(tender.public_id))
        assert len(mail.outbox) == 0
