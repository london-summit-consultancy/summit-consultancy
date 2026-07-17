"""allauth adapters — public accounts.

Signup is open to everyone, by email/password or Google. New accounts are
ordinary public users (``is_staff=False``); the tender tool stays gated behind
``is_staff`` (``apps.tenders.views.StaffRequiredMixin``), so opening signup
never exposes internal tooling. A Google sign-in whose email already has a local
account connects to it (Google verifies the address) instead of creating a
duplicate, which also prevents a stranger from hijacking an email that already
belongs to a password account.
"""

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model
from django.http import HttpRequest

from .tasks import send_account_email


class PublicAccountAdapter(DefaultAccountAdapter):
    """Open email/password signup and route users to the right place on login."""

    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return True

    def send_mail(self, template_prefix: str, email: str, context: dict) -> None:
        # allauth sends account email (verification, password reset, email-change
        # confirmation) synchronously in the request with fail_silently=False, so
        # a slow or failing SMTP call — including an unconfigured backend — turns
        # into a 500 on login/signup. Render here (the context, incl. the signed
        # confirmation URL, only exists in-request), then hand the SMTP I/O to
        # Celery so the request never blocks on or fails from mail delivery.
        msg = self.render_mail(template_prefix, email, context)
        send_account_email.delay(
            subject=msg.subject,
            body=msg.body,
            from_email=msg.from_email,
            to=list(msg.to),
            alternatives=[
                [content, mimetype] for content, mimetype in getattr(msg, "alternatives", [])
            ],
            reply_to=list(msg.reply_to or []),
            headers=dict(msg.extra_headers or {}),
        )

    def get_login_redirect_url(self, request: HttpRequest) -> str:
        # Staff belong in the internal tender tool (settings.LOGIN_REDIRECT_URL);
        # every public member lands back on the marketing site.
        if getattr(request.user, "is_staff", False):
            return super().get_login_redirect_url(request)
        return "/"

    def get_signup_redirect_url(self, request: HttpRequest) -> str:
        # ACCOUNT_SIGNUP_REDIRECT_URL defaults to LOGIN_REDIRECT_URL
        # (/internal/tenders/), but a brand-new account is always is_staff=False,
        # so sending it there is an immediate 403 from StaffRequiredMixin. Route
        # signups the same way as logins: staff to the tool, everyone else home.
        return self.get_login_redirect_url(request)


class PublicSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Open Google signup; fold a Google login into a matching local account."""

    def is_open_for_signup(self, request: HttpRequest, sociallogin) -> bool:
        return True

    def pre_social_login(self, request: HttpRequest, sociallogin) -> None:
        # Already linked to a local user — nothing to do.
        if sociallogin.is_existing:
            return

        email = (sociallogin.account.extra_data.get("email") or "").strip().lower()
        if not email:
            return  # let allauth handle the missing-email case

        user_model = get_user_model()
        try:
            user = user_model.objects.get(email__iexact=email, is_active=True)
        except user_model.DoesNotExist:
            return  # no local account yet — allauth provisions a new public user

        # An account with this (Google-verified) email already exists: attach the
        # Google identity to it rather than minting a second account.
        sociallogin.connect(request, user)
