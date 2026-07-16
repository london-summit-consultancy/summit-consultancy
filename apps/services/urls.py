from django.urls import path

from . import views

app_name = "services"

urlpatterns = [
    path("", views.ServicesLandingView.as_view(), name="landing"),
    path("<slug:slug>/", views.ServiceDetailView.as_view(), name="detail"),
]
