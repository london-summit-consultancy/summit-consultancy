from pathlib import Path

import environ

env = environ.Env()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.sites",  # required by allauth.socialaccount
    "django.contrib.humanize",  # intcomma for GBP pipeline figures
]

THIRD_PARTY_APPS = [
    "django_htmx",
    "imagekit",
    "django_prose_editor",
    "simple_history",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
]

LOCAL_APPS = [
    "apps.core",
    "apps.services",
    "apps.portfolio",
    "apps.inquiries",
    "apps.tenders",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "csp.middleware.CSPMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",  # required by django-allauth
    "simple_history.middleware.HistoryRequestMiddleware",
]

SITE_ID = 1

AUTH_USER_MODEL = "core.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://pioneer:pioneer@localhost:5432/pioneer")
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Europe/London"
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ("en", "English"),
    ("ar", "العربية"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Django 5.1+ removed STATICFILES_STORAGE / DEFAULT_FILE_STORAGE — the STORAGES
# dict is the only supported configuration. Safe filesystem baseline here;
# production.py overrides with S3 (media) + WhiteNoise manifest (static).
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
    # Confidential tender documents — never mixed with public media. Filesystem
    # baseline here; production.py overrides this with a private Cloudflare R2
    # bucket that serves short-lived signed URLs.
    "tender_documents": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": str(BASE_DIR / "private_media"),
            "base_url": "/private-media/",
        },
    },
}

# Tender document handling (apps.tenders). In local/dev, documents live on the
# filesystem and are streamed by the staff-gated download view. In production
# (R2) the download view redirects to a signed, expiring object URL instead.
TENDER_DOCS_SIGNED_URLS = False
# Uploaded files are written here by the request, then moved to `tender_documents`
# storage by a Celery task (keeps the R2 write off the request cycle). Web and
# worker must share this directory (single-node / shared volume deployment).
TENDER_UPLOAD_STAGING_DIR = str(BASE_DIR / "tender_staging")
TENDER_MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB
TENDER_ALLOWED_UPLOAD_MIME_TYPES = [
    "application/pdf",
    "image/vnd.dwg",  # DWG
    "image/x-dwg",  # DWG (alt)
    "application/acad",  # DWG (alt)
    "image/vnd.dxf",  # DXF
    "application/dxf",  # DXF (alt)
    "model/vnd.ifc",  # IFC
    "application/x-step",  # IFC (sniffed)
    "text/plain",  # IFC/DXF often sniff as plain text
    "application/octet-stream",  # RVT and other binary CAD/BIM
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # DOCX
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # XLSX
    "application/zip",  # DOCX/XLSX/RVT sniff as zip
    "image/png",
    "image/jpeg",
]
# File extensions map to human intent even when MIME sniffing is ambiguous for
# CAD/BIM formats; the upload view validates the extension as the primary gate.
TENDER_ALLOWED_UPLOAD_EXTENSIONS = [
    ".pdf",
    ".dwg",
    ".dxf",
    ".ifc",
    ".rvt",
    ".docx",
    ".xlsx",
    ".png",
    ".jpg",
    ".jpeg",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

FIXTURE_DIRS = [BASE_DIR / "fixtures"]

# Celery
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# Cache
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://localhost:6379/1"),
    }
}

RATELIMIT_USE_CACHE = "default"

# Email
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@example.com")
INQUIRY_NOTIFICATION_EMAIL = env("INQUIRY_NOTIFICATION_EMAIL", default="info@example.com")
EMAIL_TIMEOUT = 30  # seconds — prevents hung SMTP/SES connections from blocking Celery workers

# Admin branding
ADMIN_SITE_HEADER = "London Summit Consultancy Admin"
ADMIN_SITE_TITLE = "London Summit Admin"

# Authentication / django-allauth — public accounts (email + Google) plus the
# staff-only tender tool. Signup is open to everyone; new members are ordinary
# public users (is_staff=False). The tender tool stays gated behind is_staff
# (StaffRequiredMixin), so opening signup never exposes internal tooling.
# LOGIN_URL keeps the /internal/ alias (it redirects to allauth); the account
# adapter routes staff to the tender tool and everyone else back to the site.
LOGIN_URL = "/internal/login/"
LOGIN_REDIRECT_URL = "/internal/tenders/"  # staff destination; public → "/" via adapter
LOGOUT_REDIRECT_URL = "/"

# Account: email is the identifier, no usernames. Signup is open and users can
# log in immediately; a verification email is still sent (asynchronously, via
# PublicAccountAdapter.send_mail -> Celery) but is not required to sign in.
# "optional" rather than "mandatory" because public accounts are is_staff=False
# and unlock nothing sensitive (the tender tool is gated on is_staff), so gating
# login on a delivered email only creates a dead-end when the mail backend isn't
# configured. Revisit to "mandatory" once outbound email is provisioned and
# verified addresses are actually required.
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_EMAIL_SUBJECT_PREFIX = "[London Summit] "
ACCOUNT_ADAPTER = "apps.core.adapters.PublicAccountAdapter"

# Abuse controls for the now-public endpoints (allauth throttles via the default
# cache — see CACHES/RATELIMIT_USE_CACHE above). Format: "count/period/scope".
ACCOUNT_RATE_LIMITS = {
    "login_failed": "5/5m/ip,5/5m/key",  # brute-force protection
    "signup": "10/h/ip",  # curb bulk account creation
    "confirm_email": "3/5m/key",
    "reset_password": "5/h/ip",
    "reset_password_from_key": "5/h/ip",
}

# Outbound "we care" client emails on tender lifecycle events (never blocks a
# request — always enqueued to Celery). Toggle off in tests.
SEND_CLIENT_EMAILS = env.bool("SEND_CLIENT_EMAILS", default=True)

# Social: Google. Open signup — a Google login for an email that already has a
# local account connects to it (adapter), otherwise it provisions a new public
# user. Credentials come from settings (env), so no SocialApp DB row is required.
SOCIALACCOUNT_ADAPTER = "apps.core.adapters.PublicSocialAccountAdapter"
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": env("GOOGLE_CLIENT_ID", default=""),
            "secret": env("GOOGLE_CLIENT_SECRET", default=""),
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "EMAIL_AUTHENTICATION": True,
    }
}

# Canonical site domain for the sites framework (drives sitemap.xml host now
# that django.contrib.sites is installed). Overridable per environment.
SITE_DOMAIN = env("SITE_DOMAIN", default="localhost:8000")
SITE_NAME = env("SITE_NAME", default="London Summit Consultancy")

# Local DeepSeek 7B (on-prem, OpenAI-compatible endpoint) — powers document
# summaries, client-email drafts, tender Q&A, and description drafting. Runs
# locally for data privacy; nothing is sent to a third-party AI provider.
# Defaults target Ollama; override for vLLM/LM Studio/etc. Degrades gracefully
# when DEEPSEEK_BASE_URL is empty.
DEEPSEEK_BASE_URL = env("DEEPSEEK_BASE_URL", default="http://localhost:11434/v1")
DEEPSEEK_MODEL = env("DEEPSEEK_MODEL", default="deepseek-r1:7b")
DEEPSEEK_API_KEY = env("DEEPSEEK_API_KEY", default="")
# All AI now runs in Celery (never the request path — see apps.tenders AIJob), so
# a single generous timeout is fine: a slow local model can't starve web workers
# or affect the public site.
DEEPSEEK_TIMEOUT = env.int("DEEPSEEK_TIMEOUT", default=120)

# Ably realtime (chat + notifications). Server holds the API key; browsers get
# short-lived tokens from a staff-gated endpoint.
ABLY_API_KEY = env("ABLY_API_KEY", default="")
