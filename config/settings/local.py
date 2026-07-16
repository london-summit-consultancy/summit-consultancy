import os

from csp.constants import NONCE, NONE, SELF

# Set dev-only defaults before base.py reads env — .env file is optional in local dev
os.environ.setdefault("SECRET_KEY", "django-insecure-local-dev-only-change-for-production")
os.environ.setdefault("DATABASE_URL", "postgres://pioneer:pioneer@localhost:5432/pioneer")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from .base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# STORAGES is inherited from base.py (plain filesystem static + local media).
# Never point local dev at S3.

# CSP in report-only mode: violations surface in the browser console during
# development without blocking anything. Directives mirror production, but media
# is local (SELF) and no HTTPS upgrade on plain-HTTP localhost.
CONTENT_SECURITY_POLICY_REPORT_ONLY = {
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
    },
}

# Simpler cache for local dev (comment out to test Redis locally)
# CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
