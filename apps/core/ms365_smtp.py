"""Microsoft 365 SMTP AUTH via OAuth2 (XOAUTH2), not a mailbox password.

Basic Auth for Exchange Online SMTP AUTH is being retired by Microsoft:
default-disabled for existing tenants end of December 2026, full removal in
the second half of 2027 (see
https://learn.microsoft.com/en-us/exchange/clients-and-mobile-in-exchange-online/deprecation-of-basic-authentication-exchange-online).
So instead of EMAIL_HOST_PASSWORD, this module acquires an app-only OAuth2
access token from Microsoft Entra (client credentials grant, scope
https://outlook.office365.com/.default, permission "SMTP.SendAsApp") and uses
it to authenticate the SMTP connection via the XOAUTH2 SASL mechanism, per
https://learn.microsoft.com/en-us/exchange/client-developer/legacy-protocols/how-to-authenticate-an-imap-pop-smtp-application-by-using-oauth
and
https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-client-creds-grant-flow.

Tenant-side prerequisites (done once, outside this codebase, by whoever
administers the Microsoft 365 tenant):
1. A sending mailbox (a dedicated shared mailbox is recommended, e.g.
   no-reply@yourdomain.com) with SMTP AUTH enabled — Microsoft 365 admin
   center > Users > Active users > select the mailbox > Mail > Manage email
   apps > Authenticated SMTP.
2. A Microsoft Entra app registration granted the Office 365 Exchange Online
   "SMTP.SendAsApp" *application* permission, with tenant admin consent
   granted, and a client secret generated for it.
3. The app's service principal registered in Exchange Online PowerShell
   (New-ServicePrincipal -AppId <client-id> -ObjectId <enterprise-app-object-id>),
   then given SendAs rights on the sending mailbox (Add-RecipientPermission
   -Identity <MS365_SMTP_USER> -Trustee <service-principal-id> -AccessRights SendAs).

MS365_TENANT_ID / MS365_CLIENT_ID / MS365_CLIENT_SECRET / MS365_SMTP_USER are
read from settings (see config/settings/production.py).
"""

from __future__ import annotations

import logging
import smtplib
from collections.abc import Callable

import httpx
from django.conf import settings
from django.core.cache import cache
from django.core.mail.backends.smtp import EmailBackend as DjangoSMTPEmailBackend

logger = logging.getLogger(__name__)

_TOKEN_CACHE_KEY = "ms365:smtp:access_token"
_TOKEN_ENDPOINT = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
_SCOPE = "https://outlook.office365.com/.default"
# Refresh well before Microsoft's own expiry so a token is never used right at
# its boundary (tokens are typically valid ~3599s).
_EXPIRY_SAFETY_MARGIN = 300
_MIN_CACHE_SECONDS = 60


class MS365TokenError(RuntimeError):
    """Raised when an OAuth2 access token for Microsoft 365 SMTP can't be obtained."""


def is_enabled() -> bool:
    return bool(
        getattr(settings, "MS365_TENANT_ID", "")
        and getattr(settings, "MS365_CLIENT_ID", "")
        and getattr(settings, "MS365_CLIENT_SECRET", "")
    )


def get_access_token(*, force_refresh: bool = False) -> str:
    """Return a cached (or freshly acquired) app-only access token for SMTP."""
    if not force_refresh:
        cached = cache.get(_TOKEN_CACHE_KEY)
        if cached:
            return cached

    if not is_enabled():
        raise MS365TokenError(
            "MS365_TENANT_ID / MS365_CLIENT_ID / MS365_CLIENT_SECRET are not configured."
        )

    url = _TOKEN_ENDPOINT.format(tenant_id=settings.MS365_TENANT_ID)
    try:
        response = httpx.post(
            url,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.MS365_CLIENT_ID,
                "client_secret": settings.MS365_CLIENT_SECRET,
                "scope": _SCOPE,
            },
            timeout=getattr(settings, "EMAIL_TIMEOUT", 30),
        )
    except httpx.HTTPError as exc:
        logger.error("Microsoft 365 token request failed", exc_info=True)
        raise MS365TokenError("Could not reach the Microsoft identity platform.") from exc

    payload = response.json() if response.content else {}
    access_token = payload.get("access_token")
    if response.status_code != 200 or not access_token:
        logger.error(
            "Microsoft 365 token request rejected: %s %s",
            response.status_code,
            payload.get("error_description") or payload.get("error") or response.text,
        )
        raise MS365TokenError(
            payload.get("error_description")
            or "Microsoft identity platform rejected the token request."
        )

    expires_in = int(payload.get("expires_in") or 3599)
    cache_timeout = max(expires_in - _EXPIRY_SAFETY_MARGIN, _MIN_CACHE_SECONDS)
    cache.set(_TOKEN_CACHE_KEY, access_token, timeout=cache_timeout)
    return access_token


def build_xoauth2_string(username: str, access_token: str) -> str:
    """SASL XOAUTH2 payload per Microsoft's documented SMTP AUTH format."""
    return f"user={username}\x01auth=Bearer {access_token}\x01\x01"


class Microsoft365EmailBackend(DjangoSMTPEmailBackend):
    """Django SMTP backend that authenticates with XOAUTH2 instead of AUTH LOGIN/PLAIN.

    Mirrors django.core.mail.backends.smtp.EmailBackend.open() exactly, except
    the ``connection.login(username, password)`` call is replaced with an
    OAuth2 XOAUTH2 handshake.
    """

    def open(self) -> bool | None:
        if self.connection:
            return False

        if self._partial_connection is not None:
            self._close_connection(self._partial_connection)
            self._partial_connection = None

        connection_params = {"local_hostname": self._local_hostname()}
        if self.timeout is not None:
            connection_params["timeout"] = self.timeout
        if self.use_ssl:
            connection_params["context"] = self.ssl_context
        try:
            self._partial_connection = self.connection_class(
                self.host, self.port, **connection_params
            )
            if not self.use_ssl and self.use_tls:
                self._partial_connection.starttls(context=self.ssl_context)
            if self.username:
                self._authenticate_xoauth2(self._partial_connection)

            self.connection = self._partial_connection
            self._partial_connection = None
            return True
        except OSError:
            if not self.fail_silently:
                raise
            return None

    def _local_hostname(self) -> str:
        from django.core.mail.utils import DNS_NAME

        return DNS_NAME.get_fqdn()

    def _authenticate_xoauth2(
        self, connection: smtplib.SMTP, *, force_refresh: bool = False
    ) -> None:
        token = get_access_token(force_refresh=force_refresh)
        auth_string = build_xoauth2_string(self.username, token)
        authobject: Callable[[bytes | None], str] = lambda challenge=None: auth_string  # noqa: E731
        try:
            connection.auth("XOAUTH2", authobject, initial_response_ok=False)
        except smtplib.SMTPAuthenticationError:
            if force_refresh:
                raise
            # The cached token may have just expired at the boundary — refresh
            # once and retry before giving up.
            self._authenticate_xoauth2(connection, force_refresh=True)
