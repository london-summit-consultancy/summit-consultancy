from django.urls import path

from . import views

app_name = "inquiries"

urlpatterns = [
    path("", views.InquiryCreateView.as_view(), name="contact"),
    path("sent/", views.InquirySuccessView.as_view(), name="sent"),
    path("validate/", views.InquiryValidateView.as_view(), name="validate"),
]
