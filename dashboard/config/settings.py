from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
DEBUG = os.environ.get("TOOL_SHED_DASHBOARD_DEBUG") == "1"
TESTING = os.environ.get("TOOL_SHED_DASHBOARD_TESTING") == "1"
DASHBOARD_ENVIRONMENT = os.environ.get("TOOL_SHED_DASHBOARD_ENVIRONMENT", "production").strip().lower()
if DASHBOARD_ENVIRONMENT not in {"production", "development"}:
    raise ValueError("TOOL_SHED_DASHBOARD_ENVIRONMENT must be production or development")
DASHBOARD_ALLOW_INSECURE_HTTP = (
    DASHBOARD_ENVIRONMENT == "development"
    and os.environ.get("TOOL_SHED_DASHBOARD_ALLOW_INSECURE_HTTP") == "1"
)
SECRET_KEY = os.environ.get("TOOL_SHED_DASHBOARD_SECRET_KEY", "test-only-dashboard-secret")
ALLOWED_HOSTS = [item for item in os.environ.get("TOOL_SHED_DASHBOARD_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if item]
CSRF_TRUSTED_ORIGINS = [item for item in os.environ.get("TOOL_SHED_DASHBOARD_CSRF_ORIGINS", "").split(",") if item]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "dashboard.fleet",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "dashboard.config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "dashboard" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "dashboard.fleet.context.fleet_navigation",
            ]
        },
    }
]
WSGI_APPLICATION = "dashboard.config.wsgi.application"

if TESTING:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "tool_shed_dashboard"),
            "USER": os.environ.get("POSTGRES_USER", "tool_shed_dashboard"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "postgres"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/dashboard/static/"
STATIC_ROOT = BASE_DIR / "build" / "dashboard-static"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/dashboard/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/dashboard/login/"
SESSION_COOKIE_NAME = os.environ.get("TOOL_SHED_DASHBOARD_SESSION_COOKIE_NAME", "tool_shed_sessionid")
CSRF_COOKIE_NAME = os.environ.get("TOOL_SHED_DASHBOARD_CSRF_COOKIE_NAME", "tool_shed_csrftoken")

DASHBOARD_AUTH_MODE = os.environ.get("TOOL_SHED_DASHBOARD_AUTH_MODE", "local-mfa")
DASHBOARD_REQUIRE_OTP = not TESTING and DASHBOARD_AUTH_MODE == "local-mfa"
DASHBOARD_ENROLLMENT_TTL_SECONDS = 600
DASHBOARD_EVENT_RETENTION_DAYS = int(os.environ.get("TOOL_SHED_DASHBOARD_EVENT_RETENTION_DAYS", "90"))
DASHBOARD_FAILURE_RETENTION_DAYS = int(os.environ.get("TOOL_SHED_DASHBOARD_FAILURE_RETENTION_DAYS", "30"))
DASHBOARD_FAILURE_OCCURRENCE_CAP = int(os.environ.get("TOOL_SHED_DASHBOARD_FAILURE_OCCURRENCE_CAP", "100"))
DASHBOARD_SSE_POLL_SECONDS = float(os.environ.get("TOOL_SHED_DASHBOARD_SSE_POLL_SECONDS", "2"))
DASHBOARD_SSE_MAX_SECONDS = float(os.environ.get("TOOL_SHED_DASHBOARD_SSE_MAX_SECONDS", "55"))
DASHBOARD_SSE_KEEPALIVE_SECONDS = float(os.environ.get("TOOL_SHED_DASHBOARD_SSE_KEEPALIVE_SECONDS", "2"))

if not DEBUG and not TESTING and not DASHBOARD_ALLOW_INSECURE_HTTP:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    X_FRAME_OPTIONS = "DENY"
elif not DEBUG and not TESTING:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0
    X_FRAME_OPTIONS = "DENY"
