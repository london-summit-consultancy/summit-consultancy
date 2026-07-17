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
def send_account_email(
    self,
    *,
    subject: str,
    body: str,
    from_email: str,
    to: list[str],
    alternatives: list[list[str]] | None = None,
    reply_to: list[str] | None = None,
    headers: dict[str, str] | None = None,
) -> None:
    """Deliver a pre-rendered django-allauth account email off the request path.

    allauth (email verification, password reset, email-change confirmation) calls
    ``msg.send()`` synchronously *inside* the login/signup view with
    ``fail_silently=False``. Any SMTP failure — including a mail backend that
    isn't configured yet — therefore surfaces as a 500 on the auth request (see
    PublicAccountAdapter.send_mail, which renders the message and enqueues this).
    Only the SMTP I/O runs here; rendering stays in the request where the context
    lives.

    Two guards keep this cheap under production's brokerless eager mode
    (CELERY_TASK_ALWAYS_EAGER=True — ``.delay()`` runs inline in the request):

    * If the MS365 SMTP backend is selected but has no credentials, skip the send
      entirely. Otherwise every attempt blocks ~7s on a doomed office365 handshake
      that can only end in "not authenticated". Configuring MS365 (or attaching a
      Redis worker) turns delivery back on with no code change.
    * On failure, retry only when a real broker is present. Under eager mode a
      ``self.retry`` re-runs this SMTP call inline, piling seconds onto the auth
      request for no benefit, so there we log once and give up — the account is
      already created and (verification being optional) the user is signed in.
    """
    from django.core.mail import EmailMultiAlternatives

    if not _account_email_deliverable():
        logger.info("Account email to %s skipped: mail backend not configured", to)
        return

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=from_email,
            to=to,
            reply_to=reply_to or None,
            headers=headers or None,
        )
        for content, mimetype in alternatives or []:
            msg.attach_alternative(content, mimetype)
        msg.send(fail_silently=False)
    except Exception as exc:
        if getattr(self.request, "is_eager", False):
            logger.warning("Account email to %s not delivered (eager mode, no retry): %s", to, exc)
            return
        raise self.retry(exc=exc) from exc


def _account_email_deliverable() -> bool:
    """False only when the MS365 SMTP backend is selected yet unconfigured.

    That is the one "selected but non-functional" backend in this project; any
    other backend (console in dev, a real SMTP host) is assumed able to deliver,
    so a genuine misconfiguration there still surfaces via a failed send.
    """
    if settings.EMAIL_BACKEND == "apps.core.ms365_smtp.Microsoft365EmailBackend":
        from . import ms365_smtp

        return ms365_smtp.is_enabled()
    return True


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
