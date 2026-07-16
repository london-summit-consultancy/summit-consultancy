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


class PublicAccountAdapter(DefaultAccountAdapter):
    """Open email/password signup and route users to the right place on login."""

    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return True

    def get_login_redirect_url(self, request: HttpRequest) -> str:
        # Staff belong in the internal tender tool (settings.LOGIN_REDIRECT_URL);
        # every public member lands back on the marketing site.
        if getattr(request.user, "is_staff", False):
            return super().get_login_redirect_url(request)
        return "/"


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
