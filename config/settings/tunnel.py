"""Settings for serving the site from your laptop through a Cloudflare Tunnel.

Cloudflare can't host Django directly, so the app runs locally and `cloudflared`
exposes it over an HTTPS URL. This profile is safe to expose (DEBUG off, no
tracebacks) yet needs no AWS — it uses local Postgres, local static/media, and
console email. Run with:

    DJANGO_SETTINGS_MODULE=config.settings.tunnel \
        uv run python manage.py runserver --insecure 0.0.0.0:8000

then in another terminal:  cloudflared tunnel --url http://localhost:8000
"""

import os

from csp.constants import NONCE, NONE, SELF

# Dev-only defaults so no .env is required on the laptop. Override SECRET_KEY via
# the environment for anything beyond a short demo.
os.environ.setdefault(
    "SECRET_KEY",
    "django-insecure-tunnel-demo-3kf9Qx7pLm2vT8wRzN4hJ6yB1cD5sG0aE-change-me",
)
os.environ.setdefault("DATABASE_URL", "postgres://pioneer:pioneer@localhost:5432/pioneer")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from .base import *  # noqa: F401, F403
from .base import env

# Not DEBUG: never leak tracebacks/settings over a public URL.
DEBUG = False

# Cloudflare terminates TLS at its edge and forwards plain HTTP to cloudflared.
# Trust the forwarded scheme so request.is_secure() / CSRF treat it as HTTPS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Quick tunnels get a random *.trycloudflare.com host; the leading dot / wildcard
# matches any subdomain so the config survives the URL changing each run.
ALLOWED_HOSTS = [".trycloudflare.com", "localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = ["https://*.trycloudflare.com"]

# Named tunnel on your own Cloudflare domain? Set TUNNEL_HOST=app.example.com
_tunnel_host = env("TUNNEL_HOST", default="")
if _tunnel_host:
    ALLOWED_HOSTS.append(_tunnel_host)
    CSRF_TRUSTED_ORIGINS.append(f"https://{_tunnel_host}")

# The browser talks HTTPS to Cloudflare, so cookies can be secure-only.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Do NOT force SSL redirect — the origin is plain HTTP and would loop.

# Laptop demo: no AWS. Emails print to the runserver console; uploads & static
# are served locally (runserver --insecure serves /static/ with DEBUG off).
# STORAGES inherited from base.py (filesystem) — never touch S3 from the laptop.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
SERVE_MEDIA = True

# CSP report-only for the public tunnel demo — same directives as production but
# media is served locally (SELF). Report-only so a bad rule never bricks a demo.
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
        "upgrade-insecure-requests": True,
    },
}
