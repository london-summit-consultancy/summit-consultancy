import sentry_sdk
from csp.constants import NONCE, NONE, SELF
from sentry_sdk.integrations.django import DjangoIntegration

from .base import *  # noqa: F401, F403
from .base import ALLOWED_HOSTS, env

DEBUG = False
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Deployed on Fly.io, behind Fly's edge proxy which terminates TLS — trust its
# forwarded-proto header so Django knows the original request was HTTPS
# (drives SECURE_SSL_REDIRECT / secure-cookie behaviour).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Fly app hostnames are stable and known up front (<app-name>.fly.dev, set in
# fly.toml's `app` key), unlike Render's per-deploy hostname — so no dynamic
# detection is needed here. Set ALLOWED_HOSTS via `fly secrets set` to that
# hostname (plus any custom domain once one is attached).
CSRF_TRUSTED_ORIGINS = [
    f"https://{host}" for host in ALLOWED_HOSTS if host and not host.startswith(".")
]

# Transactional email via Microsoft 365 SMTP AUTH, authenticated with OAuth2
# (XOAUTH2) rather than a mailbox password — see apps/core/ms365_smtp.py for
# why (Basic Auth for Exchange Online SMTP AUTH is being retired by
# Microsoft) and for the required Entra app registration / mailbox setup.
# MS365_SMTP_USER is the sending mailbox address (a dedicated shared mailbox
# is recommended); MS365_TENANT_ID / MS365_CLIENT_ID / MS365_CLIENT_SECRET
# identify the Entra app registration used to acquire the access token.
# EMAIL_HOST/PORT/USE_TLS are env-configurable (see fly.toml) rather than
# hardcoded, matching ALLOWED_HOSTS/SITE_DOMAIN/DEEPSEEK_BASE_URL below. The
# default is smtp.office365.com — NOT smtp-mail.outlook.com, which is the
# consumer Outlook.com (personal @outlook.com/@hotmail.com) endpoint, not the
# Microsoft 365 organizational-mailbox one this OAuth setup targets.
EMAIL_BACKEND = "apps.core.ms365_smtp.Microsoft365EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="smtp.office365.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("MS365_SMTP_USER")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
MS365_TENANT_ID = env("MS365_TENANT_ID")
MS365_CLIENT_ID = env("MS365_CLIENT_ID")
MS365_CLIENT_SECRET = env("MS365_CLIENT_SECRET")

# Storage (Django 6 STORAGES dict) — static via WhiteNoise manifest. Public
# media ("default") is NOT overridden here, so it stays on the filesystem
# baseline from base.py (BASE_DIR / "media") — no object storage account
# needed for now. SERVE_MEDIA below makes Django serve /media/ itself.
# Trade-off: this is local disk with no persistent Fly Volume attached, so
# anything uploaded through the admin is lost on the next deploy/restart. Fine
# for a first live deploy; revisit (R2/S3, or a Fly Volume — compatible here
# since this is already a single-Machine process group) before real portfolio
# content depends on it.
SERVE_MEDIA = True
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
    # Confidential tender documents on a *private* Cloudflare R2 bucket, separate
    # from the public media bucket above. No ACLs (R2 has none), signed &
    # expiring URLs (querystring_auth=True) so objects are never world-readable.
    "tender_documents": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "bucket_name": env("R2_TENDER_BUCKET_NAME"),
            "endpoint_url": env("R2_ENDPOINT_URL"),
            "access_key": env("R2_ACCESS_KEY_ID"),
            "secret_key": env("R2_SECRET_ACCESS_KEY"),
            "region_name": "auto",
            "signature_version": "s3v4",
            "addressing_style": "virtual",
            "file_overwrite": False,
            "default_acl": None,
            "querystring_auth": True,
            "querystring_expire": 3600,
            "custom_domain": None,
        },
    },
}

# Tender documents are on R2 — the download view issues a redirect to a signed,
# expiring object URL rather than streaming bytes through the app server.
TENDER_DOCS_SIGNED_URLS = True

# Content Security Policy (django-csp 4.x dict API) — enforced.
# All first-party assets (fonts, HTMX, CSS, JS, and now media too) are
# self-hosted, so scripts, styles, and images are locked to 'self'. The two
# inline <script> blocks (theme no-FOUC + portfolio lightbox) carry
# {{ request.csp_nonce }}.
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": [NONE],
        "script-src": [SELF, NONCE],
        "style-src": [SELF],
        "font-src": [SELF],
        "img-src": [SELF, "data:"],
        "media-src": [SELF],
        "connect-src": [SELF],
        "form-action": [SELF],
        "frame-ancestors": [NONE],
        "base-uri": [NONE],
        "manifest-src": [SELF],
        "upgrade-insecure-requests": True,
    },
}

# Sentry
_sentry_dsn = env("SENTRY_DSN", default="")
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
