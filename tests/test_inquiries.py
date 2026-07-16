import pytest
from django.urls import reverse

from apps.inquiries.models import Inquiry, InquiryStatus


@pytest.fixture
def inquiry(db):
    return Inquiry.objects.create(
        full_name="Sarah Jones",
        email="sarah@example.com",
        project_desc="New office development.",
        status=InquiryStatus.NEW,
    )


class TestInquiryStateMachine:
    def test_new_to_contacted(self, inquiry):
        inquiry.transition_to(InquiryStatus.CONTACTED)
        assert inquiry.status == InquiryStatus.CONTACTED

    def test_illegal_new_to_won_raises(self, inquiry):
        with pytest.raises(ValueError, match="Cannot transition"):
            inquiry.transition_to(InquiryStatus.CLOSED_WON)

    def test_illegal_new_to_qualified_raises(self, inquiry):
        with pytest.raises(ValueError):
            inquiry.transition_to(InquiryStatus.QUALIFIED)

    def test_contacted_to_qualified(self, inquiry):
        inquiry.transition_to(InquiryStatus.CONTACTED)
        inquiry.transition_to(InquiryStatus.QUALIFIED)
        assert inquiry.status == InquiryStatus.QUALIFIED

    def test_contacted_to_closed_lost(self, inquiry):
        inquiry.transition_to(InquiryStatus.CONTACTED)
        inquiry.transition_to(InquiryStatus.CLOSED_LOST)
        assert inquiry.status == InquiryStatus.CLOSED_LOST

    def test_qualified_to_closed_won(self, inquiry):
        inquiry.transition_to(InquiryStatus.CONTACTED)
        inquiry.transition_to(InquiryStatus.QUALIFIED)
        inquiry.transition_to(InquiryStatus.CLOSED_WON)
        assert inquiry.status == InquiryStatus.CLOSED_WON

    def test_transition_updates_db(self, inquiry):
        inquiry.transition_to(InquiryStatus.CONTACTED)
        refreshed = Inquiry.objects.get(pk=inquiry.pk)
        assert refreshed.status == InquiryStatus.CONTACTED


class TestInquiryAdminTransition:
    """The admin save_model wraps its two writes in one transaction: an invalid
    status transition must roll back the whole edit (including notes).
    ``admin_client`` is pytest-django's superuser-authenticated test client."""

    def _post_data(self, inquiry, **overrides):
        data = {
            "full_name": inquiry.full_name,
            "email": inquiry.email,
            "phone": "",
            "company": "",
            "buyer_type": "",
            "service": "",
            "project_desc": inquiry.project_desc,
            "budget_range": "",
            "status": inquiry.status,
            "notes": inquiry.notes,
            "_save": "Save",
        }
        data.update(overrides)
        return data

    def test_invalid_transition_rolls_back_notes(self, admin_client, inquiry):
        url = reverse("admin:inquiries_inquiry_change", args=[inquiry.pk])
        # new -> qualified is illegal; notes change must NOT persist.
        admin_client.post(
            url, self._post_data(inquiry, status=InquiryStatus.QUALIFIED, notes="Attempted note")
        )
        refreshed = Inquiry.objects.get(pk=inquiry.pk)
        assert refreshed.status == InquiryStatus.NEW
        assert refreshed.notes == ""

    def test_valid_transition_commits(self, admin_client, inquiry):
        url = reverse("admin:inquiries_inquiry_change", args=[inquiry.pk])
        admin_client.post(
            url, self._post_data(inquiry, status=InquiryStatus.CONTACTED, notes="Called client")
        )
        refreshed = Inquiry.objects.get(pk=inquiry.pk)
        assert refreshed.status == InquiryStatus.CONTACTED
        assert refreshed.notes == "Called client"


class TestInquiryForm:
    def test_valid_form(self, db):
        from apps.inquiries.forms import InquiryForm

        form = InquiryForm(
            data={
                "full_name": "Hassan Ahmed",
                "email": "hassan@example.com",
                "project_desc": "Large warehouse development.",
                "website": "",
            }
        )
        assert form.is_valid(), form.errors

    def test_missing_required_fields(self, db):
        from apps.inquiries.forms import InquiryForm

        form = InquiryForm(data={"full_name": "", "email": "", "project_desc": ""})
        assert not form.is_valid()
        assert "full_name" in form.errors
        assert "email" in form.errors
        assert "project_desc" in form.errors


class TestInquiryCreateView:
    def test_get_renders_form(self, client, db):
        url = reverse("inquiries:contact")
        response = client.get(url)
        assert response.status_code == 200

    def test_valid_post_redirects(self, client, db, settings):
        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"
        url = reverse("inquiries:contact")
        response = client.post(
            url,
            {
                "full_name": "Sarah Jones",
                "email": "sarah@example.com",
                "project_desc": "New office development.",
                "website": "",
            },
        )
        assert response.status_code == 302
        assert Inquiry.objects.filter(email="sarah@example.com").exists()

    def test_honeypot_filled_discards_silently(self, client, db):
        url = reverse("inquiries:contact")
        response = client.post(
            url,
            {
                "full_name": "Bot",
                "email": "bot@spam.com",
                "project_desc": "Spam message.",
                "website": "http://spam.com",
            },
        )
        assert response.status_code == 302
        assert not Inquiry.objects.filter(email="bot@spam.com").exists()

    def test_htmx_valid_post_returns_success_partial(self, client, db, settings):
        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"
        url = reverse("inquiries:contact")
        response = client.post(
            url,
            {
                "full_name": "Sarah Jones",
                "email": "sarah@example.com",
                "project_desc": "New office development.",
                "website": "",
            },
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert b"Message Sent" in response.content

    def test_htmx_invalid_post_returns_422(self, client, db):
        url = reverse("inquiries:contact")
        response = client.post(
            url,
            {"full_name": "", "email": "", "project_desc": "", "website": ""},
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 422

    def test_validate_endpoint_returns_error(self, client, db):
        url = reverse("inquiries:validate")
        response = client.post(url, {"email": "not-an-email"})
        assert response.status_code == 200
        assert len(response.content) > 0

    def test_validate_endpoint_returns_empty_for_valid(self, client, db):
        url = reverse("inquiries:validate")
        response = client.post(url, {"email": "valid@example.com"})
        assert response.status_code == 200
        assert response.content == b""
