from __future__ import annotations

import hashlib
import hmac
from functools import wraps
from typing import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden

from .models import ReporterCredential


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def reporter_credential(request: HttpRequest, *, scope: str):
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    if len(token) < 32:
        return None
    prefix = token[:12]
    candidates = ReporterCredential.objects.select_related("instance", "instance__project").filter(
        token_prefix=prefix, revoked_at__isnull=True, scope=scope
    )
    supplied = token_digest(token)
    for credential in candidates:
        if hmac.compare_digest(credential.token_digest, supplied):
            return credential
    return None


def reporter_instance(request: HttpRequest):
    credential = reporter_credential(request, scope=ReporterCredential.Scope.OPERATIONAL)
    return None if credential is None else credential.instance


def dashboard_auth_required(view: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    @wraps(view)
    def wrapped(request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
        if settings.DASHBOARD_REQUIRE_OTP and not getattr(request.user, "is_verified", lambda: False)():
            return HttpResponseForbidden("Multi-factor verification is required.")
        return view(request, *args, **kwargs)

    return wrapped
