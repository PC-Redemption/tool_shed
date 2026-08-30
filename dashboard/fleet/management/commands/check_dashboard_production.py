from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.checks import run_checks
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django_otp.plugins.otp_totp.models import TOTPDevice


class Command(BaseCommand):
    help = "Fail closed unless the dashboard is ready for authenticated production service."

    def handle(self, *args, **options):
        findings: list[str] = []
        if settings.DEBUG:
            findings.append("debug mode is enabled")
        if settings.SECRET_KEY == "test-only-dashboard-secret" or len(settings.SECRET_KEY) < 50:
            findings.append("a strong dashboard secret key is not configured")
        if not settings.DATABASES["default"].get("PASSWORD"):
            findings.append("the PostgreSQL password is not configured")
        if settings.DASHBOARD_AUTH_MODE not in {"local-mfa", "local-password"}:
            findings.append("the configured authentication mode is unsupported by this release")
        if settings.DASHBOARD_AUTH_MODE == "local-mfa" and not settings.DASHBOARD_REQUIRE_OTP:
            findings.append("multi-factor verification is disabled")
        if settings.DASHBOARD_AUTH_MODE == "local-password" and settings.DASHBOARD_REQUIRE_OTP:
            findings.append("password-only mode unexpectedly requires multi-factor verification")
        if any(item in {"localhost", "127.0.0.1", "testserver"} for item in settings.ALLOWED_HOSTS):
            findings.append("development hosts remain in the production allowlist")
        findings.extend(str(item) for item in run_checks(include_deployment_checks=True) if item.level >= 30)
        try:
            connection.ensure_connection()
            if not get_user_model().objects.filter(is_active=True, is_staff=True).exists():
                findings.append("no active staff maintainer exists")
            if settings.DASHBOARD_AUTH_MODE == "local-mfa" and not TOTPDevice.objects.filter(
                confirmed=True, user__is_active=True, user__is_staff=True
            ).exists():
                findings.append("no confirmed maintainer TOTP device exists")
        except Exception as error:
            findings.append(f"database readiness failed: {type(error).__name__}")
        if findings:
            raise CommandError("dashboard production readiness failed: " + "; ".join(findings))
        self.stdout.write("dashboard production readiness: healthy")
