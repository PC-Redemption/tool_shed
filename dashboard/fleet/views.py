from __future__ import annotations

import json
import time
from datetime import timedelta

from django.conf import settings
from django.db import close_old_connections
from django.db.models import Q
from django.http import HttpRequest, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .auth import dashboard_auth_required, reporter_instance
from .contracts import ContractError, validate_report
from .live import dashboard_revision
from .models import Enrollment, FailureGroup, Project
from .services import approve_enrollment, create_enrollment, distinct_efficiency_aggregates, ingest_report, poll_enrollment


def _payload(request: HttpRequest) -> dict:
    if len(request.body) > 262_144:
        raise ContractError("request body exceeds 256 KiB")
    try:
        value = json.loads(request.body or b"{}")
    except json.JSONDecodeError as error:
        raise ContractError("request body must be JSON") from error
    if not isinstance(value, dict):
        raise ContractError("request body must be a JSON object")
    return value


def _error(error: ContractError, status: int = 400) -> JsonResponse:
    return JsonResponse({"schema_version": 1, "status": "error", "error": str(error)}, status=status)


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "healthy", "service": "tool-shed-dashboard", "schema_version": 1})


@csrf_exempt
@require_POST
def enrollment_request(request: HttpRequest) -> JsonResponse:
    try:
        enrollment, secret = create_enrollment(_payload(request))
    except ContractError as error:
        return _error(error)
    return JsonResponse(
        {
            "schema_version": 1,
            "status": enrollment.status,
            "request_id": enrollment.id,
            "user_code": enrollment.user_code,
            "device_secret": secret,
            "expires_at": enrollment.expires_at,
        },
        status=202,
    )


@csrf_exempt
@require_POST
def enrollment_poll(request: HttpRequest, enrollment_id) -> JsonResponse:
    secret = request.headers.get("X-Tool-Shed-Device-Secret", "")
    try:
        result = poll_enrollment(str(enrollment_id), secret)
    except ContractError as error:
        return _error(error, 404)
    return JsonResponse({"schema_version": 1, **result})


@require_POST
@dashboard_auth_required
def enrollment_decide(request: HttpRequest, enrollment_id) -> JsonResponse:
    enrollment = get_object_or_404(Enrollment, id=enrollment_id)
    try:
        payload = _payload(request)
        if set(payload) != {"decision"} or payload["decision"] not in {"approve", "reject"}:
            raise ContractError("decision must be approve or reject")
        decided = approve_enrollment(enrollment, request.user, approved=payload["decision"] == "approve")
    except ContractError as error:
        return _error(error)
    return JsonResponse({"schema_version": 1, "status": decided.status, "request_id": decided.id})


@require_GET
@dashboard_auth_required
def enrollments_view(request: HttpRequest):
    pending = Enrollment.objects.filter(
        status=Enrollment.Status.PENDING,
        expires_at__gt=timezone.now(),
    ).select_related("decided_by")
    return render(request, "fleet/enrollments.html", {"pending_enrollments": pending})


@require_POST
@dashboard_auth_required
def enrollment_decision_ui(request: HttpRequest, enrollment_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id)
    decision = request.POST.get("decision")
    if decision not in {"approve", "reject"}:
        return JsonResponse({"status": "error", "error": "decision must be approve or reject"}, status=400)
    try:
        approve_enrollment(enrollment, request.user, approved=decision == "approve")
    except ContractError as error:
        return JsonResponse({"status": "error", "error": str(error)}, status=409)
    return redirect("fleet:enrollments")


@csrf_exempt
@require_POST
def report_ingest(request: HttpRequest) -> JsonResponse:
    instance = reporter_instance(request)
    if instance is None:
        return JsonResponse({"schema_version": 1, "status": "error", "error": "invalid reporter credential"}, status=401)
    try:
        report = validate_report(_payload(request))
        result = ingest_report(instance, report)
    except ContractError as error:
        return _error(error, 409 if "idempotency" in str(error) or "sequence" in str(error) else 400)
    return JsonResponse({"schema_version": 1, **result})


@csrf_exempt
@require_POST
def reporter_revoke(request: HttpRequest) -> JsonResponse:
    instance = reporter_instance(request)
    if instance is None:
        return JsonResponse({"schema_version": 1, "status": "error", "error": "invalid reporter credential"}, status=401)
    credential = instance.credential
    credential.revoked_at = timezone.now()
    credential.save(update_fields=("revoked_at",))
    return JsonResponse({"schema_version": 1, "status": "revoked"})


@require_GET
@dashboard_auth_required
def dashboard_events(request: HttpRequest) -> StreamingHttpResponse:
    requested_revision = request.GET.get("since", "")

    def stream():
        yield "retry: 5000\n: connected\n\n"
        baseline = dashboard_revision()
        if requested_revision and baseline != requested_revision:
            yield f"id: {baseline}\nevent: dashboard-update\ndata: {baseline}\n\n"
            return
        started = time.monotonic()
        keepalive_at = started
        while time.monotonic() - started < settings.DASHBOARD_SSE_MAX_SECONDS:
            time.sleep(settings.DASHBOARD_SSE_POLL_SECONDS)
            close_old_connections()
            current = dashboard_revision()
            if current != baseline:
                yield f"id: {current}\nevent: dashboard-update\ndata: {current}\n\n"
                return
            now = time.monotonic()
            if now - keepalive_at >= 15:
                yield ": keepalive\n\n"
                keepalive_at = now

    response = StreamingHttpResponse(stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache, no-transform"
    response["X-Accel-Buffering"] = "no"
    return response


@dashboard_auth_required
def fleet_overview(request: HttpRequest):
    projects = Project.objects.prefetch_related("instances").all()
    stale = Q(last_seen__lt=timezone.now() - timedelta(minutes=20)) | Q(last_seen__isnull=True)
    counts = {
        "projects": projects.count(),
        "attention": projects.filter(attention_state__in=("attention", "blocked")).count(),
        "working": projects.filter(attention_state="working").count(),
        "stale": projects.filter(stale).count(),
    }
    query = request.GET.get("q", "").strip()
    if query:
        projects = projects.filter(Q(name__icontains=query) | Q(external_id__icontains=query))
    state = request.GET.get("state", "").strip()
    if state == "attention":
        projects = projects.filter(attention_state__in=("attention", "blocked"))
    elif state == "working":
        projects = projects.filter(attention_state="working")
    elif state == "stale":
        projects = projects.filter(stale)
    return render(request, "fleet/overview.html", {"projects": projects, "counts": counts})


@dashboard_auth_required
def project_detail(request: HttpRequest, project_id, tab: str = "overview"):
    if tab not in {"overview", "work", "outcomes", "health"}:
        return JsonResponse({"status": "not-found"}, status=404)
    project = get_object_or_404(Project.objects.prefetch_related("instances"), id=project_id)
    return render(request, "fleet/project.html", {"project": project, "tab": tab})


@dashboard_auth_required
def app_server_view(request: HttpRequest):
    projects = Project.objects.prefetch_related("instances__app_server", "instances__failure_groups").all()
    groups = FailureGroup.objects.select_related("instance", "instance__project")[:100]
    return render(request, "fleet/app_server.html", {"projects": projects, "groups": groups})


@dashboard_auth_required
def work_efficiency_view(request: HttpRequest):
    aggregates = distinct_efficiency_aggregates()
    return render(request, "fleet/work_efficiency.html", {"aggregates": aggregates})
