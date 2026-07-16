from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "tenders"

urlpatterns = [
    # Staff auth entry points live under /internal/ for a self-contained area;
    # they redirect to the canonical allauth views (email/password + Google).
    path(
        "login/",
        RedirectView.as_view(pattern_name="account_login", query_string=True),
        name="login",
    ),
    path(
        "logout/",
        RedirectView.as_view(pattern_name="account_logout", query_string=True),
        name="logout",
    ),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("ably/token/", views.AblyTokenView.as_view(), name="ably_token"),
    path("tenders/", views.TenderListView.as_view(), name="list"),
    path("tenders/create/", views.TenderCreateView.as_view(), name="create"),
    path("tenders/<uuid:public_id>/", views.TenderDetailView.as_view(), name="detail"),
    path("tenders/<uuid:public_id>/edit/", views.TenderUpdateView.as_view(), name="update"),
    path("tenders/<uuid:public_id>/status/", views.TenderStatusUpdateView.as_view(), name="status"),
    path(
        "tenders/<uuid:public_id>/messages/",
        views.TenderMessageCreateView.as_view(),
        name="message_create",
    ),
    path(
        "tenders/<uuid:public_id>/documents/upload/",
        views.DocumentUploadView.as_view(),
        name="document_upload",
    ),
    path(
        "tenders/documents/<uuid:doc_public_id>/supersede/",
        views.DocumentSupersededToggleView.as_view(),
        name="document_supersede",
    ),
    path(
        "tenders/documents/<uuid:doc_public_id>/download/",
        views.TenderDocumentDownloadView.as_view(),
        name="document_download",
    ),
    # AI (local DeepSeek) assistance endpoints (JSON).
    path(
        "tenders/ai/draft-description/",
        views.AIDraftDescriptionView.as_view(),
        name="ai_draft_description",
    ),
    path(
        "tenders/<uuid:public_id>/ai/draft-email/",
        views.AIDraftClientEmailView.as_view(),
        name="ai_draft_email",
    ),
    path("tenders/<uuid:public_id>/ai/ask/", views.AITenderQAView.as_view(), name="ai_ask"),
    path(
        "tenders/ai/jobs/<uuid:job_public_id>/",
        views.AIJobStatusView.as_view(),
        name="ai_job_status",
    ),
]
