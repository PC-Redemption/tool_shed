from __future__ import annotations

import csv
import io
import json
import time
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.db import close_old_connections
from django.db.models import F, Q
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .auth import dashboard_auth_required, reporter_instance
from .contracts import ContractError, validate_report
from .live import dashboard_revision
from .models import AppServerAggregate, Enrollment, FailureGroup, Instance, Project, WorkArtifactSnapshot
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
    projects = Project.objects.prefetch_related("instances").order_by(
        F("last_activity_at").desc(nulls_last=True),
        F("last_seen").desc(nulls_last=True),
        "name",
    )
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
    query = request.GET.get("q", "").strip()[:80]
    if query:
        projects = projects.filter(
            Q(name__icontains=query)
            | Q(external_id__icontains=query)
            | Q(instances__client_version__icontains=query)
            | Q(work_artifacts__visible_id__icontains=query)
            | Q(work_artifacts__title__icontains=query)
            | Q(work_artifacts__artifact_type__icontains=query)
            | Q(work_artifacts__document_lifecycle__icontains=query)
            | Q(work_artifacts__outcome_lifecycle__icontains=query)
            | Q(work_artifacts__outcome_disposition__icontains=query)
            | Q(work_artifacts__reconciliation_state__icontains=query)
        )
    state = request.GET.get("state", "").strip()
    if state == "attention":
        projects = projects.filter(id__in=attention_project_ids)
    elif state == "working":
        projects = projects.filter(attention_state="working")
    elif state == "stale":
        projects = projects.filter(id__in=stale_project_ids)
    artifact_types = tuple(
        WorkArtifactSnapshot.objects.order_by("artifact_type")
        .values_list("artifact_type", flat=True)
        .distinct()
    )
    selected_type = request.GET.get("type", "").strip()
    if selected_type not in artifact_types:
        selected_type = ""
    if selected_type:
        projects = projects.filter(work_artifacts__artifact_type=selected_type)
    lifecycle_values = (
        "active",
        "working",
        "blocked",
        "completed",
        "terminal",
        "open",
        "reconciled",
        "superseded",
    )
    selected_lifecycle = request.GET.get("lifecycle", "").strip()
    if selected_lifecycle not in lifecycle_values:
        selected_lifecycle = ""
    if selected_lifecycle:
        projects = projects.filter(
            Q(work_artifacts__document_lifecycle=selected_lifecycle)
            | Q(work_artifacts__outcome_lifecycle=selected_lifecycle)
            | Q(work_artifacts__outcome_disposition=selected_lifecycle)
            | Q(work_artifacts__reconciliation_state=selected_lifecycle)
        )
    selected_version = request.GET.get("version", "").strip()[:64]
    if selected_version:
        projects = projects.filter(instances__client_version__iexact=selected_version)
    projects = projects.distinct()
    row_options = ("10", "20", "50", "100", "all")
    selected_rows = request.GET.get("rows", "20").strip().lower()
    if selected_rows not in row_options:
        selected_rows = "20"
    result_count = projects.count()

    def overview_url(page: int) -> str:
        values = {"rows": selected_rows, "page": page}
        for key, value in (
            ("q", query),
            ("state", state),
            ("type", selected_type),
            ("lifecycle", selected_lifecycle),
            ("version", selected_version),
        ):
            if value:
                values[key] = value
        return "?" + urlencode(values)

    project_page = None
    page_links: list[dict[str, object]] = []
    previous_page_url = None
    next_page_url = None
    if selected_rows == "all":
        project_list = list(projects)
    else:
        paginator = Paginator(projects, int(selected_rows))
        project_page = paginator.get_page(request.GET.get("page", "1"))
        project_list = list(project_page.object_list)
        if project_page.has_previous():
            previous_page_url = overview_url(project_page.previous_page_number())
        if project_page.has_next():
            next_page_url = overview_url(project_page.next_page_number())
        for page_number in paginator.get_elided_page_range(project_page.number, on_each_side=2, on_ends=1):
            if page_number == Paginator.ELLIPSIS:
                page_links.append({"ellipsis": True})
            else:
                page_links.append(
                    {
                        "number": page_number,
                        "url": overview_url(int(page_number)),
                        "current": int(page_number) == project_page.number,
                    }
                )
    match_by_project: dict[object, WorkArtifactSnapshot] = {}
    if query or selected_type or selected_lifecycle:
        matches = WorkArtifactSnapshot.objects.filter(project_id__in=[item.id for item in project_list])
        if query:
            matches = matches.filter(
                Q(visible_id__icontains=query)
                | Q(title__icontains=query)
                | Q(artifact_type__icontains=query)
                | Q(document_lifecycle__icontains=query)
                | Q(outcome_lifecycle__icontains=query)
                | Q(outcome_disposition__icontains=query)
                | Q(reconciliation_state__icontains=query)
            )
        if selected_type:
            matches = matches.filter(artifact_type=selected_type)
        if selected_lifecycle:
            matches = matches.filter(
                Q(document_lifecycle=selected_lifecycle)
                | Q(outcome_lifecycle=selected_lifecycle)
                | Q(outcome_disposition=selected_lifecycle)
                | Q(reconciliation_state=selected_lifecycle)
            )
        for match in matches.order_by("-source_updated_at", "-visible_id"):
            match_by_project.setdefault(match.project_id, match)
    for project in project_list:
        project.dashboard_attention = attention_by_project.get(project.id, [])
        project.dashboard_match = match_by_project.get(project.id)
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
            "selected_query": query,
            "selected_type": selected_type,
            "selected_lifecycle": selected_lifecycle,
            "selected_version": selected_version,
            "selected_rows": selected_rows,
            "artifact_types": artifact_types,
            "lifecycle_values": lifecycle_values,
            "version_values": tuple(
                Instance.objects.exclude(client_version="")
                .order_by("client_version")
                .values_list("client_version", flat=True)
                .distinct()
            ),
            "result_count": result_count,
            "project_page": project_page,
            "page_links": page_links,
            "previous_page_url": previous_page_url,
            "next_page_url": next_page_url,
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


def _semver(value: object) -> tuple[int, int, int] | None:
    parts = str(value or "").removeprefix("v").split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def _instance_health_context(instances: list[object]) -> tuple[list[dict[str, object]], dict[str, object]]:
    current = timezone.now()
    rows: list[dict[str, object]] = []
    for instance in instances:
        health = instance.health_state if isinstance(instance.health_state, dict) else {}
        release = health.get("release") if isinstance(health.get("release"), dict) else {}
        age = current - instance.last_seen if instance.last_seen else None
        reported_state = str(health.get("reporter_state") or "unknown")
        reporter_state = (
            "offline"
            if age is None or age >= timedelta(hours=2)
            else "stale"
            if age >= timedelta(minutes=20)
            else reported_state
        )
        installed = str(release.get("installed_version") or instance.client_version or "unknown")
        stable = release.get("stable_version")
        candidate = release.get("candidate_version")
        pending = int(release.get("pending_candidate_count") or 0)
        awaiting_chains = int(release.get("awaiting_work5_chain_count") or 0)
        candidate_commits = int(release.get("candidate_commit_count") or 0)
        registrations = int(release.get("registration_count") or pending)
        release_chains = (
            release.get("release_chains")
            if isinstance(release.get("release_chains"), list)
            else []
        )
        installed_semver = _semver(installed)
        stable_semver = _semver(stable)
        version_state = (
            "current"
            if stable_semver and installed_semver == stable_semver
            else "candidate"
            if pending and candidate == installed
            else "behind"
            if installed_semver and stable_semver and installed_semver < stable_semver
            else "newer"
            if installed_semver and stable_semver and installed_semver > stable_semver
            else "unknown"
        )
        rows.append(
            {
                "instance": instance,
                "reporter_state": reporter_state,
                "pending_event_count": int(health.get("pending_event_count") or 0),
                "last_delivery_at": parse_datetime(str(health.get("last_delivery_at") or "")),
                "semantic_digest": str(health.get("semantic_digest") or ""),
                "installed_version": installed,
                "stable_version": stable,
                "stable_source": str(release.get("stable_source") or "unknown"),
                "candidate_version": candidate,
                "pending_candidate_count": pending,
                "awaiting_work5_chain_count": awaiting_chains,
                "candidate_commit_count": candidate_commits,
                "registration_count": registrations,
                "release_chains": release_chains,
                "production_version": release.get("production_version"),
                "production_source": str(release.get("production_source") or "unknown"),
                "release_observed_at": parse_datetime(str(release.get("observed_at") or "")),
                "compatibility_state": str(release.get("compatibility_state") or "unknown"),
                "qualification_state": str(release.get("qualification_state") or "unknown"),
                "version_state": version_state,
            }
        )
    reporter_states = {str(row["reporter_state"]) for row in rows}
    installed_versions = {str(row["installed_version"]) for row in rows}
    version_states = {str(row["version_state"]) for row in rows}
    semantic_digests = {str(row["semantic_digest"]) for row in rows if row["semantic_digest"]}
    summary = {
        "instance_count": len(rows),
        "reporter_state": (
            next(iter(reporter_states)) if len(reporter_states) == 1 else "mixed" if rows else "unknown"
        ),
        "version_state": (
            next(iter(version_states))
            if len(version_states) == 1 and len(installed_versions) <= 1
            else "mixed"
            if rows
            else "unknown"
        ),
        "divergence_state": (
            "divergent" if len(semantic_digests) > 1 else "aligned" if semantic_digests else "unknown"
        ),
        "pending_candidate_count": sum(int(row["pending_candidate_count"]) for row in rows),
        "awaiting_work5_chain_count": sum(
            int(row["awaiting_work5_chain_count"]) for row in rows
        ),
        "candidate_commit_count": sum(int(row["candidate_commit_count"]) for row in rows),
        "registration_count": sum(int(row["registration_count"]) for row in rows),
    }
    return rows, summary


OVERVIEW_TYPE_ORDER = {
    "idea-brief": 0,
    "project-map": 1,
    "program-roadmap": 2,
    "campaign": 3,
}
OVERVIEW_TYPE_LABELS = {
    "idea-brief": "Ideas",
    "project-map": "Maps",
    "program-roadmap": "PRMs",
    "campaign": "Campaigns",
}
OVERVIEW_ACTIVE_DOCUMENT_STATES = {
    "active",
    "exploring",
    "promoted",
    "queued",
    "ready",
    "ready-for-prm",
    "working",
}


def _project_overview_context(
    project: Project,
    instances: list[Instance],
    health_summary: dict[str, object],
) -> dict[str, object]:
    """Build one bounded operator snapshot without merging instance inventories."""
    source_instance = max(
        instances,
        key=lambda instance: (
            instance.work_inventory_observed_at or instance.last_seen or instance.created_at,
            str(instance.id),
        ),
        default=None,
    )
    snapshots = (
        list(
            WorkArtifactSnapshot.objects.filter(instance=source_instance).order_by(
                "-source_updated_at", "visible_id"
            )
        )
        if source_instance
        else []
    )

    open_artifacts = [
        artifact
        for artifact in snapshots
        if artifact.outcome_disposition == "open"
        or artifact.outcome_lifecycle == "working"
        or artifact.reconciliation_state == "open"
    ]
    open_artifact_ids = {artifact.id for artifact in open_artifacts}
    open_by_type = []
    lifecycle_rows = []
    for artifact_type, label in OVERVIEW_TYPE_LABELS.items():
        typed = [artifact for artifact in snapshots if artifact.artifact_type == artifact_type]
        active = sum(
            artifact.document_lifecycle in OVERVIEW_ACTIVE_DOCUMENT_STATES for artifact in typed
        )
        completed = sum(artifact.document_lifecycle == "completed" for artifact in typed)
        open_count = sum(artifact.id in open_artifact_ids for artifact in typed)
        open_by_type.append({"type": artifact_type, "label": label, "count": open_count})
        lifecycle_rows.append(
            {
                "type": artifact_type,
                "label": label,
                "active": active,
                "open": open_count,
                "completed": completed,
                "historical": len(typed) - active - completed,
                "total": len(typed),
            }
        )

    by_visible_id = {artifact.visible_id: artifact for artifact in snapshots}
    source_health = (
        source_instance.health_state
        if source_instance and isinstance(source_instance.health_state, dict)
        else {}
    )
    source_release = (
        source_health.get("release")
        if isinstance(source_health.get("release"), dict)
        else {}
    )
    release_chains = (
        source_release.get("release_chains")
        if isinstance(source_release.get("release_chains"), list)
        else []
    )
    release_by_visible_id: dict[str, dict[str, object]] = {}
    presented_release_chains = []
    for chain in release_chains:
        if not isinstance(chain, dict):
            continue
        node_ids = [
            str(chain.get(field))
            for field in ("idea_id", "map_id", "prm_id", "campaign_id")
            if chain.get(field)
        ]
        for node_id in node_ids:
            release_by_visible_id[node_id] = chain
        root_id = str(chain.get("root_id") or (node_ids[0] if node_ids else ""))
        root_artifact = by_visible_id.get(root_id)
        presented_release_chains.append(
            {
                **chain,
                "title": root_artifact.title if root_artifact else root_id,
                "node_ids": node_ids,
                "short_commit": str(chain.get("latest_commit") or "")[:8],
            }
        )
    graph = {visible_id: set() for visible_id in by_visible_id}
    for artifact in snapshots:
        for related_id in [*artifact.parent_ids, *artifact.produces_ids]:
            if related_id in graph:
                graph[artifact.visible_id].add(related_id)
                graph[related_id].add(artifact.visible_id)

    active_chains = []
    visited: set[str] = set()
    for visible_id in graph:
        if visible_id in visited:
            continue
        pending = [visible_id]
        component_ids = []
        while pending:
            candidate = pending.pop()
            if candidate in visited:
                continue
            visited.add(candidate)
            component_ids.append(candidate)
            pending.extend(graph[candidate] - visited)
        component = [by_visible_id[item] for item in component_ids]
        active_component = [
            artifact
            for artifact in component
            if artifact.document_lifecycle in OVERVIEW_ACTIVE_DOCUMENT_STATES
            or artifact.id in open_artifact_ids
        ]
        if not active_component:
            continue
        nodes = sorted(
            component,
            key=lambda artifact: (
                OVERVIEW_TYPE_ORDER.get(artifact.artifact_type, 99),
                artifact.visible_id,
            ),
        )
        current = max(
            active_component,
            key=lambda artifact: (
                OVERVIEW_TYPE_ORDER.get(artifact.artifact_type, -1),
                artifact.source_updated_at,
                artifact.visible_id,
            ),
        )
        root = nodes[0]
        active_chains.append(
            {
                "title": root.title,
                "nodes": nodes,
                "current": current,
                "open_count": sum(artifact.id in open_artifact_ids for artifact in component),
                "updated_at": max(artifact.source_updated_at for artifact in component),
                "release": next(
                    (
                        release_by_visible_id[artifact.visible_id]
                        for artifact in nodes
                        if artifact.visible_id in release_by_visible_id
                    ),
                    None,
                ),
            }
        )
    active_chains.sort(
        key=lambda chain: (chain["updated_at"], chain["current"].visible_id), reverse=True
    )

    planning_queues = []
    for artifact_type, label in (("idea-brief", "Ideas"), ("program-roadmap", "PRMs")):
        items = sorted(
            (
                artifact
                for artifact in snapshots
                if artifact.artifact_type == artifact_type
                and artifact.planning_position is not None
            ),
            key=lambda artifact: (artifact.planning_position, artifact.visible_id),
        )
        planning_queues.append({"type": artifact_type, "label": label, "items": items[:3]})

    reported_open_count = int(project.current_state.get("open_outcome_count") or 0)
    return {
        "source_instance": source_instance,
        "active_chains": active_chains[:5],
        "active_chain_count": len(active_chains),
        "open_by_type": open_by_type,
        "represented_open_count": len(open_artifacts),
        "reported_open_count": reported_open_count,
        "unrepresented_open_count": max(0, reported_open_count - len(open_artifacts)),
        "lifecycle_rows": lifecycle_rows,
        "planning_queues": planning_queues,
        "recent_changes": recent_changes(project, limit=6),
        "health": health_summary,
        "release_chains": presented_release_chains,
        "release_chains_truncated": bool(source_release.get("release_chains_truncated")),
        "awaiting_work5_chain_count": int(
            source_release.get("awaiting_work5_chain_count") or 0
        ),
        "candidate_commit_count": int(source_release.get("candidate_commit_count") or 0),
        "registration_count": int(
            source_release.get("registration_count")
            or source_release.get("pending_candidate_count")
            or 0
        ),
    }


@dashboard_auth_required
def project_detail(request: HttpRequest, project_id, tab: str = "overview"):
    if tab not in {"overview", "work", "history", "outcomes", "health"}:
        return JsonResponse({"status": "not-found"}, status=404)
    project = get_object_or_404(Project.objects.prefetch_related("instances"), id=project_id)
    instances = list(project.instances.all())
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
    release_stage = request.GET.get("release_stage", "").strip()
    if release_stage not in {"", "awaiting-work5"}:
        release_stage = ""
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
        if release_stage:
            values["release_stage"] = release_stage
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
        release_chain_by_instance: dict[object, dict[str, dict[str, object]]] = {}
        release_filter = Q()
        for instance in instances:
            health = instance.health_state if isinstance(instance.health_state, dict) else {}
            release = health.get("release") if isinstance(health.get("release"), dict) else {}
            chains = release.get("release_chains") if isinstance(release.get("release_chains"), list) else []
            visible_index: dict[str, dict[str, object]] = {}
            for chain in chains:
                if not isinstance(chain, dict):
                    continue
                for field in ("idea_id", "map_id", "prm_id", "campaign_id"):
                    if chain.get(field):
                        visible_index[str(chain[field])] = chain
            release_chain_by_instance[instance.id] = visible_index
            if release_stage:
                matching_ids = [
                    visible_id
                    for visible_id, chain in visible_index.items()
                    if chain.get("stage") == release_stage
                ]
                if matching_ids:
                    release_filter |= Q(instance_id=instance.id, visible_id__in=matching_ids)
        if release_stage:
            snapshots = snapshots.filter(release_filter) if release_filter else snapshots.none()
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
            snapshot.release_chain = release_chain_by_instance.get(snapshot.instance_id, {}).get(
                snapshot.visible_id
            )
            snapshot_by_instance.setdefault(snapshot.instance_id, []).append(snapshot)
    health_rows, health_summary = _instance_health_context(instances)
    overview = _project_overview_context(project, instances, health_summary) if tab == "overview" else None
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
            "health_rows": health_rows,
            "health_summary": health_summary,
            "overview": overview,
            "selected_type": artifact_type,
            "selected_status": status,
            "selected_release_stage": release_stage,
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
    selected_window = request.GET.get("window", "7d").strip()
    if selected_window not in {"24h", "7d", "30d"}:
        selected_window = "7d"
    rows = []
    totals = {"instances": 0, "ready": 0, "attempts": 0, "completions": 0, "failures": 0, "interruptions": 0, "fallbacks": 0}
    for instance in Instance.objects.select_related("project", "app_server"):
        try:
            aggregate = instance.app_server
        except AppServerAggregate.DoesNotExist:
            aggregate = None
        performance = aggregate.performance if aggregate and isinstance(aggregate.performance, dict) else {}
        metrics = performance.get("windows", {}).get(
            selected_window, {}
        )
        aggregate_attempts = aggregate.attempts if aggregate else 0
        aggregate_failures = aggregate.failures if aggregate else 0
        attempts = int(metrics.get("attempts", aggregate_attempts) or 0)
        completions = int(metrics.get("completions", max(attempts - aggregate_failures, 0)) or 0)
        failures = int(metrics.get("failures", aggregate_failures) or 0)
        interruptions = int(metrics.get("interruptions", 0) or 0)
        input_tokens = int(metrics.get("input_tokens", 0) or 0)
        cached_tokens = int(metrics.get("cached_input_tokens", 0) or 0)
        weighted_milliunits = metrics.get("weighted_usage_milliunits")
        role_metrics = metrics.get("role_metrics", {}) if isinstance(metrics.get("role_metrics"), dict) else {}
        rows.append(
            {
                "aggregate": aggregate,
                "instance": instance,
                "availability_state": aggregate.availability_state if aggregate else "unknown",
                "client_version": aggregate.client_version if aggregate else "unknown",
                "readiness_observed_at": aggregate.readiness_observed_at if aggregate else None,
                "attempts": attempts,
                "completions": completions,
                "failures": failures,
                "interruptions": interruptions,
                "fallbacks": int(metrics.get("fallbacks", aggregate.fallbacks if aggregate else 0) or 0),
                "success_rate": round(completions * 100 / attempts, 1) if attempts else None,
                "p50_ms": metrics.get("duration_p50_ms"),
                "p95_ms": metrics.get("duration_p95_ms"),
                "tokens_per_run": round((input_tokens + int(metrics.get("output_tokens", 0) or 0)) / attempts) if attempts else None,
                "cache_rate": round(cached_tokens * 100 / input_tokens, 1) if input_tokens else None,
                "weighted_usage_per_run": (
                    round(int(weighted_milliunits) / attempts / 1000, 2)
                    if weighted_milliunits is not None and attempts
                    else None
                ),
                "last_execution": parse_datetime(metrics.get("last_execution")) if metrics.get("last_execution") else None,
                "roles": [
                    ("Plan", role_metrics.get("planning", {})),
                    ("Verify", role_metrics.get("verification", {})),
                    ("CAMP", role_metrics.get("camp_execution", {})),
                ],
            }
        )
        totals["instances"] += 1
        totals["ready"] += bool(aggregate and aggregate.availability_state == "available")
        totals["attempts"] += attempts
        totals["completions"] += completions
        totals["failures"] += failures
        totals["interruptions"] += interruptions
        totals["fallbacks"] += rows[-1]["fallbacks"]
    totals["success_rate"] = round(totals["completions"] * 100 / totals["attempts"], 1) if totals["attempts"] else None
    groups = FailureGroup.objects.select_related("instance", "instance__project")[:100]
    return render(
        request,
        "fleet/app_server.html",
        {"rows": rows, "groups": groups, "selected_window": selected_window, "totals": totals},
    )


@dashboard_auth_required
def work_efficiency_view(request: HttpRequest):
    windows = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
    selected_window = request.GET.get("window", "7d").strip()
    if selected_window not in {*windows, "all"}:
        selected_window = "7d"
    selected_project = request.GET.get("project", "").strip()
    project_ids = {str(value) for value in Project.objects.values_list("id", flat=True)}
    if selected_project not in project_ids:
        selected_project = ""
    platforms = tuple(
        Instance.objects.exclude(platform="").order_by("platform").values_list("platform", flat=True).distinct()
    )
    selected_platform = request.GET.get("platform", "").strip()
    if selected_platform not in platforms:
        selected_platform = ""
    versions = tuple(
        Instance.objects.exclude(client_version="")
        .order_by("client_version")
        .values_list("client_version", flat=True)
        .distinct()
    )
    selected_version = request.GET.get("version", "").strip()
    if selected_version not in versions:
        selected_version = ""
    since = None if selected_window == "all" else timezone.now() - windows[selected_window]
    filtered = distinct_efficiency_aggregates(
        limit=1001,
        since=since,
        project_id=selected_project or None,
        platform=selected_platform,
        client_version=selected_version,
    )
    export_truncated = len(filtered) > 1000
    filtered = filtered[:1000]
    generated_at = timezone.now()

    def projection(item) -> dict[str, object]:
        return {
            "project": item.instance.project.name,
            "project_id": str(item.instance.project_id),
            "instance_id": str(item.instance.external_id),
            "platform": item.instance.platform,
            "client_version": item.instance.client_version,
            "counter_epoch": str(item.counter_epoch),
            "window_start": item.window_start.isoformat(),
            "window_end": item.window_end.isoformat(),
            "remedial_tokens_actual": item.remedial_tokens_actual,
            "remedial_token_coverage": str(item.remedial_token_coverage),
            "remedial_interactions": item.remedial_interactions,
            "remedial_output_bytes": item.remedial_output_bytes,
            "remedial_duration_ms": item.remedial_duration_ms,
            "remedial_retries": item.remedial_retries,
        }

    filters = {
        "window": selected_window,
        "project": selected_project or None,
        "platform": selected_platform or None,
        "version": selected_version or None,
    }
    export_format = request.GET.get("format", "").strip().lower()
    if export_format == "json":
        response = JsonResponse(
            {
                "schema_version": 1,
                "generated_at": generated_at.isoformat(),
                "row_limit": 1000,
                "truncated": export_truncated,
                "filters": filters,
                "rows": [projection(item) for item in filtered],
            }
        )
        response["Content-Disposition"] = 'attachment; filename="tool-shed-work-efficiency.json"'
        return response
    if export_format == "csv":
        columns = tuple(projection(filtered[0]).keys()) if filtered else (
            "project", "project_id", "instance_id", "platform", "client_version", "counter_epoch",
            "window_start", "window_end", "remedial_tokens_actual", "remedial_token_coverage",
            "remedial_interactions", "remedial_output_bytes", "remedial_duration_ms", "remedial_retries",
        )
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerows(projection(item) for item in filtered)
        response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="tool-shed-work-efficiency.csv"'
        response["X-Tool-Shed-Schema-Version"] = "1"
        response["X-Tool-Shed-Generated-At"] = generated_at.isoformat()
        response["X-Tool-Shed-Row-Limit"] = "1000"
        response["X-Tool-Shed-Truncated"] = "true" if export_truncated else "false"
        return response
    row_options = ("10", "20", "50", "100", "all")
    selected_rows = request.GET.get("rows", "20").strip().lower()
    if selected_rows not in row_options:
        selected_rows = "20"

    def efficiency_url(page: int) -> str:
        values = {"window": selected_window, "rows": selected_rows, "page": page}
        for key, value in (("project", selected_project), ("platform", selected_platform), ("version", selected_version)):
            if value:
                values[key] = value
        return "?" + urlencode(values)

    efficiency_page = None
    page_links: list[dict[str, object]] = []
    previous_page_url = None
    next_page_url = None
    if selected_rows == "all":
        aggregates = filtered
    else:
        paginator = Paginator(filtered, int(selected_rows))
        efficiency_page = paginator.get_page(request.GET.get("page", "1"))
        aggregates = list(efficiency_page.object_list)
        if efficiency_page.has_previous():
            previous_page_url = efficiency_url(efficiency_page.previous_page_number())
        if efficiency_page.has_next():
            next_page_url = efficiency_url(efficiency_page.next_page_number())
        for page_number in paginator.get_elided_page_range(efficiency_page.number, on_each_side=2, on_ends=1):
            if page_number == Paginator.ELLIPSIS:
                page_links.append({"ellipsis": True})
            else:
                page_links.append({"number": page_number, "url": efficiency_url(int(page_number)), "current": int(page_number) == efficiency_page.number})
    export_values = {"window": selected_window}
    for key, value in (("project", selected_project), ("platform", selected_platform), ("version", selected_version)):
        if value:
            export_values[key] = value
    return render(
        request,
        "fleet/work_efficiency.html",
        {
            "aggregates": aggregates,
            "projects": Project.objects.order_by("name").only("id", "name"),
            "platforms": platforms,
            "versions": versions,
            "selected_window": selected_window,
            "selected_project": selected_project,
            "selected_platform": selected_platform,
            "selected_version": selected_version,
            "selected_rows": selected_rows,
            "result_count": len(filtered),
            "export_truncated": export_truncated,
            "export_query": urlencode(export_values),
            "efficiency_page": efficiency_page,
            "page_links": page_links,
            "previous_page_url": previous_page_url,
            "next_page_url": next_page_url,
        },
    )
