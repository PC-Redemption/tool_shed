from __future__ import annotations

import json
import time
from urllib.parse import urlencode

from django.conf import settings
from django.db import close_old_connections
from django.db.models import F, Q
from django.core.paginator import Paginator
from django.http import HttpRequest, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .auth import dashboard_auth_required, reporter_instance
from .contracts import ContractError, validate_report
from .live import dashboard_revision
from .models import Enrollment, FailureGroup, Project, WorkArtifactSnapshot
from .services import (
    active_attention_items,
    approve_enrollment,
    create_enrollment,
    distinct_efficiency_aggregates,
    ingest_report,
    poll_enrollment,
    recent_changes,
)


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
            if now - keepalive_at >= settings.DASHBOARD_SSE_KEEPALIVE_SECONDS:
                yield ": keepalive\n\n"
                keepalive_at = now

    response = StreamingHttpResponse(stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache, no-transform"
    response["X-Accel-Buffering"] = "no"
    return response


@dashboard_auth_required
def fleet_overview(request: HttpRequest):
    projects = Project.objects.prefetch_related("instances").all()
    attention_items = active_attention_items()
    attention_by_project: dict[object, list[dict]] = {}
    for item in attention_items:
        attention_by_project.setdefault(item["project"].id, []).append(item)
    attention_project_ids = {
        item["project"].id for item in attention_items if item["reason_code"] != "reporter-stale"
    } | set(
        projects.filter(attention_state__in=("attention", "blocked")).values_list("id", flat=True)
    )
    stale_project_ids = {
        item["project"].id for item in attention_items if item["reason_code"] == "reporter-stale"
    }
    counts = {
        "projects": projects.count(),
        "attention": len(attention_project_ids),
        "working": projects.filter(attention_state="working").count(),
        "stale": len(stale_project_ids),
    }
    query = request.GET.get("q", "").strip()
    if query:
        projects = projects.filter(Q(name__icontains=query) | Q(external_id__icontains=query))
    state = request.GET.get("state", "").strip()
    if state == "attention":
        projects = projects.filter(id__in=attention_project_ids)
    elif state == "working":
        projects = projects.filter(attention_state="working")
    elif state == "stale":
        projects = projects.filter(id__in=stale_project_ids)
    project_list = list(projects)
    for project in project_list:
        project.dashboard_attention = attention_by_project.get(project.id, [])
        severities = {item["severity"] for item in project.dashboard_attention}
        project.effective_attention_state = (
            "blocked"
            if "blocked" in severities
            else "attention"
            if "attention" in severities
            else "stale"
            if "stale" in severities
            else project.attention_state
        )
    shown_project_ids = {project.id for project in project_list}
    displayed_attention = [item for item in attention_items if item["project"].id in shown_project_ids]
    if state == "attention":
        displayed_attention = [
            item for item in displayed_attention if item["reason_code"] != "reporter-stale"
        ]
    elif state == "stale":
        displayed_attention = [
            item for item in displayed_attention if item["reason_code"] == "reporter-stale"
        ]
    return render(
        request,
        "fleet/overview.html",
        {
            "projects": project_list,
            "counts": counts,
            "attention_items": displayed_attention,
            "selected_state": state,
        },
    )


def _navigation_redirect(request: HttpRequest):
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(target)
    return redirect("fleet:overview")


@dashboard_auth_required
@require_POST
def project_navigation_preferences(request: HttpRequest):
    scope = request.POST.get("project_scope", "active")
    request.session["fleet_project_scope"] = scope if scope in {"active", "all"} else "active"
    request.session["fleet_show_hidden"] = request.POST.get("show_hidden") == "1"
    return _navigation_redirect(request)


@dashboard_auth_required
@require_POST
def project_visibility(request: HttpRequest, project_id):
    project = get_object_or_404(Project, id=project_id)
    action = request.POST.get("action")
    if action not in {"hide", "show"}:
        return JsonResponse({"status": "invalid-action"}, status=400)
    project.is_hidden = action == "hide"
    project.save(update_fields=("is_hidden", "updated_at"))
    return _navigation_redirect(request)


PLANNING_ORDER_TYPES = {"idea-brief", "program-roadmap"}


@dashboard_auth_required
def project_detail(request: HttpRequest, project_id, tab: str = "overview"):
    if tab not in {"overview", "work", "history", "outcomes", "health"}:
        return JsonResponse({"status": "not-found"}, status=404)
    project = get_object_or_404(Project.objects.prefetch_related("instances"), id=project_id)
    attention_items = active_attention_items(project=project)
    attention_severities = {item["severity"] for item in attention_items}
    project.effective_attention_state = (
        "blocked"
        if "blocked" in attention_severities
        else "attention"
        if "attention" in attention_severities
        else "stale"
        if "stale" in attention_severities
        else project.attention_state
    )
    artifact_type = request.GET.get("type", "").strip()
    status = request.GET.get("status", "").strip()
    planning_supported = artifact_type in PLANNING_ORDER_TYPES
    selected_order = request.GET.get(
        "order", "planned" if planning_supported else "newest"
    ).strip()
    if selected_order not in {"newest", "planned"} or (selected_order == "planned" and not planning_supported):
        selected_order = "newest"
    row_options = ("10", "20", "50", "100", "all")
    selected_rows = request.GET.get("rows", "20").strip().lower()
    if selected_rows not in row_options:
        selected_rows = "20"
    snapshot_by_instance: dict[object, list[WorkArtifactSnapshot]] = {}
    work_page = None
    work_result_count = 0
    page_links: list[dict[str, object]] = []
    previous_page_url = None
    next_page_url = None
    history_page = None
    history_result_count = 0
    history_page_links: list[dict[str, object]] = []
    history_previous_page_url = None
    history_next_page_url = None

    def work_url(page: int) -> str:
        values = {"rows": selected_rows, "page": page}
        if artifact_type:
            values["type"] = artifact_type
        if status:
            values["status"] = status
        if planning_supported:
            values["order"] = selected_order
        return "?" + urlencode(values)

    if tab == "work":
        snapshots = WorkArtifactSnapshot.objects.filter(project=project).select_related("instance")
        if artifact_type:
            snapshots = snapshots.filter(artifact_type=artifact_type)
        if status:
            snapshots = snapshots.filter(
                Q(document_lifecycle=status)
                | Q(outcome_lifecycle=status)
                | Q(outcome_disposition=status)
                | Q(reconciliation_state=status)
            )
        if selected_order == "planned":
            snapshots = snapshots.order_by(
                F("planning_position").asc(nulls_last=True),
                "-source_updated_at",
                "-visible_id",
                "instance_id",
            )
        else:
            snapshots = snapshots.order_by("-source_updated_at", "-visible_id", "instance_id")
        if selected_rows == "all":
            page_snapshots = list(snapshots)
            work_result_count = len(page_snapshots)
        else:
            paginator = Paginator(snapshots, int(selected_rows))
            work_page = paginator.get_page(request.GET.get("page", "1"))
            page_snapshots = list(work_page.object_list)
            work_result_count = paginator.count
            if work_page.has_previous():
                previous_page_url = work_url(work_page.previous_page_number())
            if work_page.has_next():
                next_page_url = work_url(work_page.next_page_number())
            for page_number in paginator.get_elided_page_range(
                work_page.number, on_each_side=2, on_ends=1
            ):
                if page_number == Paginator.ELLIPSIS:
                    page_links.append({"ellipsis": True})
                else:
                    page_links.append(
                        {
                            "number": page_number,
                            "url": work_url(int(page_number)),
                            "current": int(page_number) == work_page.number,
                        }
                    )
        for snapshot in page_snapshots:
            snapshot_by_instance.setdefault(snapshot.instance_id, []).append(snapshot)
    instances = list(project.instances.all())
    if tab == "work" and snapshot_by_instance:
        instances = [instance for instance in instances if instance.id in snapshot_by_instance]
    instance_groups = [
        {"instance": instance, "artifacts": snapshot_by_instance.get(instance.id, [])}
        for instance in instances
    ]
    inventory_digests = {
        instance.work_inventory_digest
        for instance in instances
        if instance.work_inventory_digest
    }
    history = []
    if tab == "history":
        all_history = recent_changes(project)
        history_result_count = len(all_history)

        def history_url(page: int) -> str:
            return "?" + urlencode({"rows": selected_rows, "page": page})

        if selected_rows == "all":
            history = all_history
        else:
            paginator = Paginator(all_history, int(selected_rows))
            history_page = paginator.get_page(request.GET.get("page", "1"))
            history = list(history_page.object_list)
            if history_page.has_previous():
                history_previous_page_url = history_url(history_page.previous_page_number())
            if history_page.has_next():
                history_next_page_url = history_url(history_page.next_page_number())
            for page_number in paginator.get_elided_page_range(
                history_page.number, on_each_side=2, on_ends=1
            ):
                if page_number == Paginator.ELLIPSIS:
                    history_page_links.append({"ellipsis": True})
                else:
                    history_page_links.append(
                        {
                            "number": page_number,
                            "url": history_url(int(page_number)),
                            "current": int(page_number) == history_page.number,
                        }
                    )
    return render(
        request,
        "fleet/project.html",
        {
            "project": project,
            "tab": tab,
            "instance_groups": instance_groups,
            "history": history,
            "attention_items": attention_items,
            "history_viewed_at": timezone.now().isoformat(),
            "inventory_diverged": len(inventory_digests) > 1,
            "selected_type": artifact_type,
            "selected_status": status,
            "selected_rows": selected_rows,
            "selected_order": selected_order,
            "planning_supported": planning_supported,
            "work_page": work_page,
            "work_result_count": work_result_count,
            "page_links": page_links,
            "previous_page_url": previous_page_url,
            "next_page_url": next_page_url,
            "history_page": history_page,
            "history_result_count": history_result_count,
            "history_page_links": history_page_links,
            "history_previous_page_url": history_previous_page_url,
            "history_next_page_url": history_next_page_url,
        },
    )


@dashboard_auth_required
def app_server_view(request: HttpRequest):
    projects = Project.objects.prefetch_related("instances__app_server", "instances__failure_groups").all()
    groups = FailureGroup.objects.select_related("instance", "instance__project")[:100]
    return render(request, "fleet/app_server.html", {"projects": projects, "groups": groups})


@dashboard_auth_required
def work_efficiency_view(request: HttpRequest):
    aggregates = distinct_efficiency_aggregates()
    return render(request, "fleet/work_efficiency.html", {"aggregates": aggregates})
