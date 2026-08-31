from __future__ import annotations

from django.conf import settings
from django.core.checks import run_checks
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from dashboard.fleet.management.commands.seed_dashboard_development import SYNTHETIC_PROJECTS
from dashboard.fleet.models import Project


class Command(BaseCommand):
    help = "Fail closed unless the dashboard is isolated and ready for plain-HTTP development."

    def handle(self, *args, **options):
        findings: list[str] = []
        if settings.DASHBOARD_ENVIRONMENT != "development":
            findings.append("environment identity is not development")
        if not settings.DASHBOARD_ALLOW_INSECURE_HTTP:
            findings.append("the explicit development HTTP switch is disabled")
        if settings.SECURE_SSL_REDIRECT:
            findings.append("HTTPS redirect remains enabled")
        if settings.SESSION_COOKIE_SECURE or settings.CSRF_COOKIE_SECURE:
            findings.append("secure-only cookies remain enabled")
        if settings.SECURE_HSTS_SECONDS:
            findings.append("HSTS remains enabled")
        if "ts.rookaro.com" in settings.ALLOWED_HOSTS:
            findings.append("the production hostname is present in the development allowlist")
        if "192.168.7.5" not in settings.ALLOWED_HOSTS:
            findings.append("the development LAN address is absent from the allowlist")
        if settings.SECRET_KEY == "test-only-dashboard-secret" or len(settings.SECRET_KEY) < 50:
            findings.append("a strong development dashboard secret key is not configured")
        if not settings.DATABASES["default"].get("PASSWORD"):
            findings.append("the development PostgreSQL password is not configured")
        findings.extend(str(item) for item in run_checks(include_deployment_checks=True) if item.level >= 40)
        try:
            connection.ensure_connection()
            expected = {item[0] for item in SYNTHETIC_PROJECTS}
            observed = set(Project.objects.filter(external_id__in=expected).values_list("external_id", flat=True))
            if observed != expected:
                findings.append("deterministic synthetic development rows are incomplete")
        except Exception as error:
            findings.append(f"database readiness failed: {type(error).__name__}")
        if findings:
            raise CommandError("dashboard development readiness failed: " + "; ".join(findings))
        self.stdout.write("dashboard development readiness: healthy")
