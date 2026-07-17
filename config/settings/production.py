import sentry_sdk
from csp.constants import NONCE, NONE, SELF
from sentry_sdk.integrations.django import DjangoIntegration

from .base import *  # noqa: F401, F403
from .base import ALLOWED_HOSTS, DATABASES, env

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

# Fly app hostnames are <app-name>.fly.dev. Rather than pinning the hostname in
# fly.toml's [env] (which drifts the moment the image is deployed to a different
# app via `flyctl deploy -a <other-app>`), always trust the running app's own
# hostname: Fly injects FLY_APP_NAME into every Machine, so <FLY_APP_NAME>.fly.dev
# is authoritative and self-correcting. Any ALLOWED_HOSTS from the env (custom
# domains, extra hosts) is merged on top. Without this, deploying to an app whose
# name differs from the pinned host yields DisallowedHost (400) on every request,
# failing Fly health checks right after the release_command succeeds.
_fly_app_name = env("FLY_APP_NAME", default="")
if _fly_app_name:
    _fly_host = f"{_fly_app_name}.fly.dev"
    if _fly_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS = [*ALLOWED_HOSTS, _fly_host]

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
# These four MS365 secrets are OPTIONAL at settings-import time (default="").
# apps/core/ms365_smtp.py already gates sending on is_enabled() — an empty value
# means the backend cleanly reports "not configured" instead of the whole
# settings module raising ImproperlyConfigured at import. That import-time raise
# is what made `manage.py migrate` (the Fly release_command, which touches only
# the DB and needs no mail creds) crash before any log line flushed. Set them via
# `fly secrets set` to turn email on; until then, outbound mail (all enqueued to
# Celery, never on the request path) fails its task and is retried/logged.
EMAIL_BACKEND = "apps.core.ms365_smtp.Microsoft365EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="smtp.office365.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("MS365_SMTP_USER", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
MS365_TENANT_ID = env("MS365_TENANT_ID", default="")
MS365_CLIENT_ID = env("MS365_CLIENT_ID", default="")
MS365_CLIENT_SECRET = env("MS365_CLIENT_SECRET", default="")

# MS365 SMTP only sends *as* the authenticated mailbox (or an address it holds
# SendAs rights on), so default the visible From header and the inquiry-notice
# recipient to that mailbox. Setting the single MS365_SMTP_USER secret then
# yields a correct From with nothing else to configure; either can still be
# overridden (e.g. a "London Summit Consultancy <info@…>" display-name form).
# The address is never hardcoded here — it arrives only via the Fly secret.
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default=EMAIL_HOST_USER or "noreply@example.com")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
INQUIRY_NOTIFICATION_EMAIL = env(
    "INQUIRY_NOTIFICATION_EMAIL", default=EMAIL_HOST_USER or "info@example.com"
)

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
    # The four R2_* secrets default to "" so the settings module imports without
    # them (the S3 backend is instantiated lazily, only when the staff-only tender
    # tool actually reads/writes a document — never during migrate or on the public
    # site). Set them via `fly secrets set` before using the tender tool in prod.
    "tender_documents": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "bucket_name": env("R2_TENDER_BUCKET_NAME", default=""),
            "endpoint_url": env("R2_ENDPOINT_URL", default=""),
            "access_key": env("R2_ACCESS_KEY_ID", default=""),
            "secret_key": env("R2_SECRET_ACCESS_KEY", default=""),
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

# Redis is optional in production to keep the baseline deployment free of a paid
# Upstash instance. When REDIS_URL is unset, fall back to an in-process cache and
# run Celery tasks eagerly (inline, in the web process) instead of via a broker —
# so a single web Machine serves the whole app with no external broker/cache and
# no separate worker (see bin/start.sh, which then skips honcho/the worker).
# Setting REDIS_URL later flips both back to Redis + a real worker with no code
# change. Eager mode also sidesteps the local-disk tender staging hand-off that a
# separate worker Machine could not see (the task runs in the same process).
if not env("REDIS_URL", default=""):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "summit-locmem",
        }
    }
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = False

# The database is reached over a PgBouncer transaction-pooled endpoint (Neon's
# `-pooler` host), which does not support server-side cursors or psycopg's
# prepared statements — disable both so Django works correctly over the pooler.
# Both are harmless on a direct (non-pooled) connection too. TLS is enforced by
# the DATABASE_URL itself (sslmode=require & channel_binding=require); the
# credential lives only in the encrypted Fly secret, never in code or fly.toml.
DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
DATABASES["default"].setdefault("OPTIONS", {})["prepare_threshold"] = None

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
