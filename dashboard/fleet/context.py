import hashlib
from pathlib import Path

from .live import dashboard_revision
from .models import Project


_DASHBOARD_JS = Path(__file__).parent / "static" / "fleet" / "dashboard.js"
_DASHBOARD_ASSET_REVISION = hashlib.sha256(_DASHBOARD_JS.read_bytes()).hexdigest()[:12]


def fleet_navigation(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {
            "dashboard_asset_revision": _DASHBOARD_ASSET_REVISION,
            "dashboard_revision": "",
            "fleet_projects": [],
        }
    return {
        "dashboard_asset_revision": _DASHBOARD_ASSET_REVISION,
        "dashboard_revision": dashboard_revision(),
        "fleet_projects": Project.objects.only("id", "name", "attention_state")[:100],
    }
