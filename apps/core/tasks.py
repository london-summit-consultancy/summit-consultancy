import logging
from typing import Any

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def publish_realtime(channel: str, name: str, data: Any) -> None:
    """Fire-and-forget Ably publish (chat + notification fan-out)."""
    from . import realtime

    try:
        realtime.publish(channel, name, data)
    except Exception:
        logger.warning("Ably publish to %s failed", channel, exc_info=True)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_welcome_email(self, user_pk: int) -> None:
    """Branded welcome/invite email for a newly provisioned staff account,
    delivered via the configured backend (SMTP2GO in production)."""
    from .models import User

    try:
        user = User.objects.get(pk=user_pk)
    except User.DoesNotExist:
        return

    try:
        subject = "Welcome to the London Summit Consultancy tender tool"
        body = render_to_string(
            "core/email/welcome.txt",
            {"user": user, "login_url": settings.LOGIN_URL},
        )
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception as exc:
        raise self.retry(exc=exc) from exc
