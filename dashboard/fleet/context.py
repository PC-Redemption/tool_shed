import hashlib
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db.models import F
from django.utils import timezone

from .live import dashboard_revision
from .models import Project


_DASHBOARD_JS = Path(__file__).parent / "static" / "fleet" / "dashboard.js"
_DASHBOARD_CSS = Path(__file__).parent / "static" / "fleet" / "dashboard.css"
_DASHBOARD_ASSET_REVISION = hashlib.sha256(
    _DASHBOARD_JS.read_bytes() + _DASHBOARD_CSS.read_bytes()
).hexdigest()[:12]


def fleet_navigation(request):
    environment = str(settings.DASHBOARD_ENVIRONMENT)
    common = {
        "dashboard_asset_revision": _DASHBOARD_ASSET_REVISION,
        "dashboard_environment": environment,
        "dashboard_is_development": environment == "development",
    }
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {
            **common,
            "dashboard_revision": "",
            "fleet_projects": [],
        }
    project_scope = request.session.get("fleet_project_scope", "active")
    if project_scope not in {"active", "all"}:
        project_scope = "active"
    show_hidden = bool(request.session.get("fleet_show_hidden", False))
    projects = Project.objects.filter(qualification_run__isnull=True)
    if project_scope == "active":
        projects = projects.filter(last_seen__gte=timezone.now() - timedelta(minutes=20))
    if not show_hidden:
        projects = projects.filter(is_hidden=False)
    projects = projects.order_by(
        F("last_activity_at").desc(nulls_last=True),
        F("last_seen").desc(nulls_last=True),
        "name",
    )
    return {
        **common,
        "dashboard_revision": dashboard_revision(),
        "fleet_projects": projects.only(
            "id", "name", "attention_state", "last_activity_at", "last_seen", "is_hidden"
        )[:100],
        "fleet_project_scope": project_scope,
        "fleet_show_hidden": show_hidden,
    }
