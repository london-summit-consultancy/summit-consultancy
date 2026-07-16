from django.urls import path

from . import views

app_name = "portfolio"

urlpatterns = [
    path("", views.PortfolioListView.as_view(), name="list"),
    path("<slug:slug>/", views.ProjectDetailView.as_view(), name="detail"),
]
