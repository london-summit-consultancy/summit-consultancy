from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_inquiry_notification(self, inquiry_id: int) -> None:
    from .models import Inquiry

    try:
        inquiry = Inquiry.objects.select_related("service").get(pk=inquiry_id)
    except Inquiry.DoesNotExist:
        return

    try:
        subject = f"New Inquiry from {inquiry.full_name}"
        body = render_to_string("inquiries/email/notification.txt", {"inquiry": inquiry})
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.INQUIRY_NOTIFICATION_EMAIL],
            fail_silently=False,
        )
    except Exception as exc:
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_inquiry_acknowledgement(self, inquiry_id: int) -> None:
    from .models import Inquiry

    try:
        inquiry = Inquiry.objects.get(pk=inquiry_id)
    except Inquiry.DoesNotExist:
        return

    try:
        subject = "We received your enquiry — London Summit Consultancy"
        body = render_to_string("inquiries/email/acknowledgement.txt", {"inquiry": inquiry})
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[inquiry.email],
            fail_silently=False,
        )
    except Exception as exc:
        raise self.retry(exc=exc) from exc
