from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .auth import token_digest
from .contracts import ContractError
from .models import (
    AppServerAggregate,
    AttentionCondition,
    Enrollment,
    FailureGroup,
    IngestReceipt,
    Instance,
    LifecycleEvent,
    MaterialEvent,
    Project,
    QualificationRun,
    ReporterCredential,
    WorkEfficiencyAggregate,
    WorkArtifactSnapshot,
)


STALE_AFTER = timedelta(minutes=20)
QUALIFICATION_SCOPE = ReporterCredential.Scope.QUALIFICATION_WRITE
WORK_EFFICIENCY_RETENTION_PER_EPOCH = 500
ATTENTION_REASONS = {
    "blocked-work": {
        "title": "Blocked work",
        "severity": "blocked",
        "route": "ts: status",
        "tab": "work",
        "description": "This instance reports blocked Tool Shed work.",
    },
    "unreconciled-outcomes": {
        "title": "Unreconciled outcomes",
        "severity": "attention",
        "route": "ts: status",
        "tab": "outcomes",
        "description": "This instance reports outcome results that are not reconciled.",
    },
    "app-server-failure": {
        "title": "App Server needs attention",
        "severity": "attention",
        "route": "ts: app-server status",
        "tab": "app-server",
        "description": "The latest controlled App Server state is unavailable, unqualified, or has an unrecovered failure.",
    },
    "reporter-stale": {
        "title": "Reporter stale or offline",
        "severity": "stale",
        "route": "ts: dashboard status",
        "tab": "health",
        "description": "This reporting instance has not checked in within the freshness window.",
    },
}

MATERIAL_EVENT_LABELS = {
    "managed-document-update": "Managed work changed",
    "managed-update": "Managed Tool Shed state changed",
    "safety-convergence": "Reporter safety pass converged",
    "quiescent": "Reporter became quiescent",
    "client-connected": "Reporter connected",
    "client-disconnected": "Reporter disconnected",
    "campaign-started": "Campaign started",
    "campaign-completed": "Campaign completed",
    "outcome-reconciled": "Outcome reconciled",
}


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _require_qualification_environment() -> None:
    if settings.DASHBOARD_ENVIRONMENT != "development":
        raise ContractError("qualification operations are restricted to the development environment")


def _qualification_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    required = {
        "run_id",
        "manifest_digest",
        "candidate_commit",
        "scenario_id",
        "platform",
        "project",
        "instance",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise ContractError("qualification manifest fields are incomplete or unsupported")
    run_id = str(payload.get("run_id") or "")
    digest = str(payload.get("manifest_digest") or "").lower()
    commit = str(payload.get("candidate_commit") or "").lower()
    scenario = str(payload.get("scenario_id") or "")
    platform_name = str(payload.get("platform") or "")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,95}", run_id):
        raise ContractError("qualification run_id is invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ContractError("qualification manifest_digest must be a SHA-256 digest")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ContractError("qualification candidate_commit must be an exact Git commit")
    if not re.fullmatch(r"QH-[0-9]{3}", scenario):
        raise ContractError("qualification scenario_id is invalid")
    if not platform_name or len(platform_name) > 64:
        raise ContractError("qualification platform is invalid")
    project = payload.get("project")
    instance = payload.get("instance")
    if not isinstance(project, dict) or set(project) != {"id", "name"}:
        raise ContractError("qualification project must contain exactly id and name")
    if not isinstance(instance, dict) or set(instance) != {"id", "platform", "client_version"}:
        raise ContractError("qualification instance must contain exactly id, platform, and client_version")
    import uuid

    try:
        project_id = uuid.UUID(str(project.get("id")))
        instance_id = uuid.UUID(str(instance.get("id")))
    except (TypeError, ValueError) as error:
        raise ContractError("qualification project and instance IDs must be UUIDs") from error
    project_name = str(project.get("name") or "").strip()
    instance_platform = str(instance.get("platform") or "").strip()
    client_version = str(instance.get("client_version") or "").strip()
    if not project_name or len(project_name) > 160:
        raise ContractError("qualification project name is invalid")
    if not instance_platform or len(instance_platform) > 64:
        raise ContractError("qualification instance platform is invalid")
    if not client_version or len(client_version) > 64:
        raise ContractError("qualification client version is invalid")
    return {
        "run_id": run_id,
        "manifest_digest": digest,
        "candidate_commit": commit,
        "scenario_id": scenario,
        "platform": platform_name,
        "project": {"id": str(project_id), "name": project_name},
        "instance": {
            "id": str(instance_id),
            "platform": instance_platform,
            "client_version": client_version,
        },
    }


@transaction.atomic
def create_qualification_run(payload: dict[str, Any], *, user=None) -> tuple[QualificationRun, str]:
    _require_qualification_environment()
    manifest = _qualification_manifest(payload)
    run = QualificationRun.objects.select_for_update().filter(run_id=manifest["run_id"]).first()
    if run is not None and (run.manifest_digest != manifest["manifest_digest"] or run.manifest != manifest):
        raise ContractError("qualification run_id was reused with a different manifest")
    if run is not None and run.status != QualificationRun.Status.ACTIVE:
        raise ContractError("qualification run is no longer active")
    if run is None:
        run = QualificationRun.objects.create(
            run_id=manifest["run_id"],
            manifest_digest=manifest["manifest_digest"],
            candidate_commit=manifest["candidate_commit"],
            scenario_id=manifest["scenario_id"],
            platform=manifest["platform"],
            environment="development",
            manifest=manifest,
            expires_at=timezone.now() + timedelta(hours=settings.DASHBOARD_QUALIFICATION_TTL_HOURS),
            created_by=user if getattr(user, "is_authenticated", False) else None,
        )
    project_id = manifest["project"]["id"]
    project = Project.objects.select_for_update().filter(external_id=project_id).first()
    if project is not None and project.qualification_run_id != run.id:
        raise ContractError("qualification project identity collides with operational or foreign-purpose state")
    if project is None:
        project = Project.objects.create(
            external_id=project_id,
            name=manifest["project"]["name"],
            qualification_run=run,
        )
    instance_id = manifest["instance"]["id"]
    instance = Instance.objects.select_for_update().filter(project=project, external_id=instance_id).first()
    if instance is None:
        instance = Instance.objects.create(
            project=project,
            external_id=instance_id,
            platform=manifest["instance"]["platform"],
            client_version=manifest["instance"]["client_version"],
        )
    token = secrets.token_urlsafe(32)
    credential, created = ReporterCredential.objects.update_or_create(
        instance=instance,
        defaults={
            "token_prefix": token[:12],
            "token_digest": token_digest(token),
            "scope": QUALIFICATION_SCOPE,
            "qualification_run": run,
            "revoked_at": None,
        },
    )
    if not created:
        credential.rotated_at = timezone.now()
        credential.save(update_fields=("rotated_at",))
    return run, token


@transaction.atomic
def expire_qualification_run(run_id: str, *, force: bool = False) -> QualificationRun:
    _require_qualification_environment()
    run = QualificationRun.objects.select_for_update().filter(run_id=run_id).first()
    if run is None:
        raise ContractError("qualification run was not found")
    if run.status == QualificationRun.Status.PURGED:
        raise ContractError("purged qualification run cannot be expired")
    now = timezone.now()
    if not force and run.expires_at > now:
        raise ContractError("qualification run has not reached its expiry")
    if run.status != QualificationRun.Status.EXPIRED:
        run.status = QualificationRun.Status.EXPIRED
        run.expired_at = now
        run.save(update_fields=("status", "expired_at", "updated_at"))
    ReporterCredential.objects.filter(qualification_run=run, revoked_at__isnull=True).update(revoked_at=now)
    return run


def _qualification_descendants(run: QualificationRun) -> list[str]:
    project_ids = list(run.projects.order_by("id").values_list("id", flat=True))
    instance_ids = list(Instance.objects.filter(project_id__in=project_ids).order_by("id").values_list("id", flat=True))
    descendants = [f"project:{value}" for value in project_ids]
    descendants += [f"instance:{value}" for value in instance_ids]
    model_queries = (
        ("credential", ReporterCredential.objects.filter(qualification_run=run)),
        ("receipt", IngestReceipt.objects.filter(instance_id__in=instance_ids)),
        ("material-event", MaterialEvent.objects.filter(project_id__in=project_ids)),
        ("work-artifact", WorkArtifactSnapshot.objects.filter(project_id__in=project_ids)),
        ("lifecycle-event", LifecycleEvent.objects.filter(project_id__in=project_ids)),
        ("attention-condition", AttentionCondition.objects.filter(project_id__in=project_ids)),
        ("app-server", AppServerAggregate.objects.filter(instance_id__in=instance_ids)),
        ("failure-group", FailureGroup.objects.filter(instance_id__in=instance_ids)),
        ("work-efficiency", WorkEfficiencyAggregate.objects.filter(instance_id__in=instance_ids)),
    )
    for label, query in model_queries:
        descendants.extend(f"{label}:{value}" for value in query.order_by("pk").values_list("pk", flat=True))
    return sorted(descendants)


def qualification_purge_preview(run_id: str) -> dict[str, Any]:
    _require_qualification_environment()
    run = QualificationRun.objects.filter(run_id=run_id).first()
    if run is None:
        raise ContractError("qualification run was not found")
    if run.status == QualificationRun.Status.PURGED:
        raise ContractError("qualification run is already purged")
    if run.status != QualificationRun.Status.EXPIRED:
        raise ContractError("qualification run must be expired before purge preview")
    if Project.objects.filter(qualification_run=run).exclude(external_id=run.manifest["project"]["id"]).exists():
        raise ContractError("qualification run contains mixed-purpose descendants")
    descendants = _qualification_descendants(run)
    digest = _digest(descendants)
    token = _digest(
        {
            "run_id": run.run_id,
            "manifest_digest": run.manifest_digest,
            "status": run.status,
            "updated_at": run.updated_at.isoformat(),
            "descendant_digest": digest,
            "descendant_count": len(descendants),
        }
    )
    return {
        "run_id": run.run_id,
        "status": run.status,
        "descendant_count": len(descendants),
        "descendant_digest": digest,
        "preview_token": token,
    }


@transaction.atomic
def purge_qualification_run(run_id: str, preview_token: str) -> dict[str, Any]:
    _require_qualification_environment()
    run = QualificationRun.objects.select_for_update().filter(run_id=run_id).first()
    if run is None:
        raise ContractError("qualification run was not found")
    preview = qualification_purge_preview(run_id)
    if not secrets.compare_digest(preview["preview_token"], str(preview_token)):
        raise ContractError("qualification purge preview is stale or does not match the exact descendants")
    run.projects.all().delete()
    run.status = QualificationRun.Status.PURGED
    run.purged_at = timezone.now()
    run.purge_digest = preview["descendant_digest"]
    run.purged_descendant_count = preview["descendant_count"]
    run.save(
        update_fields=(
            "status",
            "purged_at",
            "purge_digest",
            "purged_descendant_count",
            "updated_at",
        )
    )
    return {**preview, "status": run.status, "purged_at": run.purged_at}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _health_material_signature(value: dict[str, Any] | None) -> str:
    material = json.loads(json.dumps(value or {}))
    material.pop("last_delivery_at", None)
    if isinstance(material.get("release"), dict):
        material["release"].pop("observed_at", None)
    return _digest(material)


def _efficiency_signature(value: WorkEfficiencyAggregate | dict[str, Any]) -> tuple[object, ...]:
    def field(name: str) -> object:
        return value[name] if isinstance(value, dict) else getattr(value, name)

    return (
        field("remedial_tokens_actual"),
        Decimal(str(field("remedial_token_coverage"))),
        field("remedial_interactions"),
        field("remedial_output_bytes"),
        field("remedial_duration_ms"),
        field("remedial_retries"),
    )


def distinct_efficiency_aggregates(
    *,
    limit: int = 200,
    since: object | None = None,
    project_id: object | None = None,
    platform: str = "",
    client_version: str = "",
) -> list[WorkEfficiencyAggregate]:
    """Return metric changes, hiding repeated sliding-window snapshots."""
    result: list[WorkEfficiencyAggregate] = []
    latest_by_instance: dict[tuple[object, object], tuple[object, ...]] = {}
    rows = WorkEfficiencyAggregate.objects.filter(
        instance__project__qualification_run__isnull=True
    ).select_related("instance", "instance__project")
    if since is not None:
        rows = rows.filter(window_end__gte=since)
    if project_id is not None:
        rows = rows.filter(instance__project_id=project_id)
    if platform:
        rows = rows.filter(instance__platform=platform)
    if client_version:
        rows = rows.filter(instance__client_version__iexact=client_version)
    rows = rows.order_by("-window_end", "-id")[: max(limit * 10, limit)]
    for item in rows:
        key = (item.instance_id, item.counter_epoch)
        signature = _efficiency_signature(item)
        if latest_by_instance.get(key) == signature:
            continue
        latest_by_instance[key] = signature
        result.append(item)
        if len(result) == limit:
            break
    return result


def _trim_efficiency_history(
    instance: Instance,
    counter_epoch: object,
    *,
    retention: int = WORK_EFFICIENCY_RETENTION_PER_EPOCH,
) -> int:
    """Keep the newest bounded semantic changes for one counter epoch."""
    stale_ids = list(
        WorkEfficiencyAggregate.objects.filter(instance=instance, counter_epoch=counter_epoch)
        .order_by("-window_end", "-id")
        .values_list("id", flat=True)[retention:]
    )
    if not stale_ids:
        return 0
    deleted, _ = WorkEfficiencyAggregate.objects.filter(id__in=stale_ids).delete()
    return deleted


def _attention_observations(state: dict[str, Any], app: dict[str, Any]) -> dict[str, tuple[str, int]]:
    observed: dict[str, tuple[str, int]] = {}
    if state["blocked_count"]:
        observed["blocked-work"] = ("blocked", state["blocked_count"])
    if state["unreconciled_outcome_count"]:
        observed["unreconciled-outcomes"] = ("attention", state["unreconciled_outcome_count"])
    unrecovered_failure = bool(
        app["last_failure"]
        and (app["last_success"] is None or app["last_failure"] > app["last_success"])
    )
    if app["enabled"] and (app["availability_state"] in {"unavailable", "unqualified"} or unrecovered_failure):
        observed["app-server-failure"] = ("attention", max(1, app["failures"]))
    return observed


def _sync_attention_conditions(
    instance: Instance,
    state: dict[str, Any],
    app: dict[str, Any],
    observed_at,
    previous_last_seen,
) -> None:
    current = _attention_observations(state, app)
    active = {
        item.reason_code: item
        for item in AttentionCondition.objects.select_for_update().filter(instance=instance, active=True)
    }
    retention = timedelta(days=settings.DASHBOARD_EVENT_RETENTION_DAYS)
    for reason_code, (severity, count) in current.items():
        condition = active.pop(reason_code, None)
        if condition is None:
            AttentionCondition.objects.create(
                project=instance.project,
                instance=instance,
                reason_code=reason_code,
                severity=severity,
                current_count=count,
                first_seen=observed_at,
                last_changed=observed_at,
            )
        elif condition.current_count != count or condition.severity != severity:
            condition.current_count = count
            condition.severity = severity
            condition.last_changed = observed_at
            condition.save(update_fields=("current_count", "severity", "last_changed"))
    for condition in active.values():
        condition.active = False
        condition.last_changed = observed_at
        condition.resolved_at = observed_at
        condition.retained_until = observed_at + retention
        condition.save(update_fields=("active", "last_changed", "resolved_at", "retained_until"))

    if previous_last_seen and observed_at - previous_last_seen > STALE_AFTER:
        AttentionCondition.objects.create(
            project=instance.project,
            instance=instance,
            reason_code="reporter-stale",
            severity="stale",
            active=False,
            current_count=1,
            first_seen=previous_last_seen + STALE_AFTER,
            last_changed=observed_at,
            resolved_at=observed_at,
            retained_until=observed_at + retention,
        )
    AttentionCondition.objects.filter(active=False, retained_until__lt=timezone.now()).delete()


def active_attention_items(*, project: Project | None = None, now=None) -> list[dict[str, Any]]:
    current_time = now or timezone.now()
    conditions = AttentionCondition.objects.filter(
        active=True, project__qualification_run__isnull=True
    ).select_related("project", "instance")
    instances = Instance.objects.filter(project__qualification_run__isnull=True).select_related("project")
    if project is not None:
        conditions = conditions.filter(project=project)
        instances = instances.filter(project=project)
    items: list[dict[str, Any]] = []
    for condition in conditions:
        reason = ATTENTION_REASONS[condition.reason_code]
        items.append(
            {
                "key": f"condition:{condition.id}",
                "project": condition.project,
                "instance": condition.instance,
                "reason_code": condition.reason_code,
                "title": reason["title"],
                "description": reason["description"],
                "severity": condition.severity,
                "count": condition.current_count,
                "first_seen": condition.first_seen,
                "last_changed": condition.last_changed,
                "last_seen": condition.instance.last_seen,
                "route": reason["route"],
                "detail_tab": reason["tab"],
            }
        )
    cutoff = current_time - STALE_AFTER
    for instance in instances:
        if (
            settings.DASHBOARD_ENVIRONMENT == "development"
            and instance.client_version == "development-seed"
            and instance.health_state.get("synthetic") is True
        ):
            continue
        if instance.last_seen is not None and instance.last_seen >= cutoff:
            continue
        reason = ATTENTION_REASONS["reporter-stale"]
        items.append(
            {
                "key": f"stale:{instance.id}",
                "project": instance.project,
                "instance": instance,
                "reason_code": "reporter-stale",
                "title": reason["title"],
                "description": reason["description"],
                "severity": reason["severity"],
                "count": 1,
                "first_seen": (instance.last_seen + STALE_AFTER) if instance.last_seen else instance.created_at,
                "last_changed": instance.last_seen or instance.created_at,
                "last_seen": instance.last_seen,
                "route": reason["route"],
                "detail_tab": reason["tab"],
            }
        )
    priority = {"blocked": 0, "attention": 1, "stale": 2}
    return sorted(items, key=lambda item: (priority[item["severity"]], item["first_seen"], item["key"]))


def recent_changes(project: Project, *, limit: int = 200) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for event in LifecycleEvent.objects.filter(project=project).select_related("instance")[:limit]:
        changes.append(
            {
                "key": f"lifecycle:{event.id}",
                "kind": "Work lifecycle",
                "title": f"{event.visible_id} · {event.title}",
                "summary": f"{event.transition}: {event.from_state} → {event.to_state}",
                "occurred_at": event.occurred_at,
                "instance": event.instance,
                "source_label": str(event.instance.external_id),
                "detail_tab": "work",
            }
        )
    for event in MaterialEvent.objects.filter(project=project).select_related("instance")[:limit]:
        changes.append(
            {
                "key": f"material:{event.id}",
                "kind": "Tool Shed event",
                "title": MATERIAL_EVENT_LABELS[event.summary_code],
                "summary": event.event_kind.replace("-", " ").capitalize(),
                "occurred_at": event.occurred_at,
                "instance": event.instance,
                "source_label": str(event.instance.external_id),
                "detail_tab": "overview",
            }
        )
    for condition in AttentionCondition.objects.filter(project=project).select_related("instance")[:limit]:
        reason = ATTENTION_REASONS[condition.reason_code]
        state = "Resolved" if condition.resolved_at else "Needs attention"
        changes.append(
            {
                "key": f"attention:{condition.id}:{'resolved' if condition.resolved_at else 'active'}",
                "kind": "Attention",
                "title": reason["title"],
                "summary": f"{state} · {reason['description']}",
                "occurred_at": condition.last_changed,
                "instance": condition.instance,
                "source_label": str(condition.instance.external_id),
                "detail_tab": reason["tab"],
            }
        )
    enrollment_labels = {
        Enrollment.Status.PENDING: "Enrollment requested",
        Enrollment.Status.APPROVED: "Enrollment approved",
        Enrollment.Status.REJECTED: "Enrollment rejected",
        Enrollment.Status.EXPIRED: "Enrollment expired",
        Enrollment.Status.ISSUED: "Reporter credential issued",
    }
    for enrollment in Enrollment.objects.filter(project_external_id=project.external_id)[:limit]:
        changes.append(
            {
                "key": f"enrollment:{enrollment.id}:{enrollment.status}",
                "kind": "Enrollment",
                "title": enrollment_labels[enrollment.status],
                "summary": "Controlled enrollment lifecycle state changed.",
                "occurred_at": enrollment.decided_at or enrollment.requested_at,
                "instance": enrollment.issued_instance,
                "source_label": str(enrollment.instance_external_id),
                "detail_tab": "health",
            }
        )
    for credential in ReporterCredential.objects.filter(instance__project=project).select_related("instance")[:limit]:
        credential_events = [("Reporter credential created", credential.created_at)]
        if credential.rotated_at:
            credential_events.append(("Reporter credential rotated", credential.rotated_at))
        if credential.revoked_at:
            credential_events.append(("Reporter credential revoked", credential.revoked_at))
        for title, occurred_at in credential_events:
            changes.append(
                {
                    "key": f"credential:{credential.id}:{title.rsplit(' ', 1)[-1]}",
                    "kind": "Credential",
                    "title": title,
                    "summary": "Credential metadata only; no secret or token prefix is retained in this feed.",
                    "occurred_at": occurred_at,
                    "instance": credential.instance,
                    "source_label": str(credential.instance.external_id),
                    "detail_tab": "health",
                }
            )
    for failure in FailureGroup.objects.filter(instance__project=project).select_related("instance")[:limit]:
        changes.append(
            {
                "key": f"app-failure:{failure.id}:{failure.count}",
                "kind": "App Server",
                "title": f"{failure.category.replace('-', ' ').title()} failure",
                "summary": f"{failure.count} controlled occurrence{'s' if failure.count != 1 else ''} in this retained group.",
                "occurred_at": failure.last_seen,
                "instance": failure.instance,
                "source_label": str(failure.instance.external_id),
                "detail_tab": "app-server",
            }
        )
    return sorted(changes, key=lambda item: (item["occurred_at"], item["key"]), reverse=True)[:limit]


def create_enrollment(payload: dict[str, Any]) -> tuple[Enrollment, str]:
    required = {"project_id", "project_name", "instance_id", "platform", "client_version"}
    unknown = sorted(set(payload) - required)
    if unknown or set(payload) != required:
        raise ContractError("enrollment request must contain exactly project_id, project_name, instance_id, platform, and client_version")
    import uuid

    try:
        project_id = uuid.UUID(str(payload["project_id"]))
        instance_id = uuid.UUID(str(payload["instance_id"]))
    except (ValueError, TypeError) as error:
        raise ContractError("project_id and instance_id must be UUIDs") from error
    strings = {}
    for field, limit in (("project_name", 160), ("platform", 64), ("client_version", 64)):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
            raise ContractError(f"{field} is invalid")
        strings[field] = value.strip()
    device_secret = secrets.token_urlsafe(32)
    for _ in range(5):
        user_code = secrets.token_hex(4).upper()
        try:
            enrollment = Enrollment.objects.create(
                project_external_id=project_id,
                project_name=strings["project_name"],
                instance_external_id=instance_id,
                platform=strings["platform"],
                client_version=strings["client_version"],
                user_code=user_code,
                device_secret_digest=token_digest(device_secret),
                expires_at=timezone.now() + timedelta(seconds=settings.DASHBOARD_ENROLLMENT_TTL_SECONDS),
            )
            return enrollment, device_secret
        except IntegrityError:
            continue
    raise ContractError("could not allocate an enrollment code")


@transaction.atomic
def poll_enrollment(enrollment_id: str, device_secret: str) -> dict[str, Any]:
    enrollment = Enrollment.objects.select_for_update().filter(id=enrollment_id).first()
    if enrollment is None or not secrets.compare_digest(enrollment.device_secret_digest, token_digest(device_secret)):
        raise ContractError("enrollment request was not found")
    now = timezone.now()
    if enrollment.status == Enrollment.Status.PENDING and enrollment.expires_at <= now:
        enrollment.status = Enrollment.Status.EXPIRED
        enrollment.save(update_fields=("status",))
    if enrollment.status != Enrollment.Status.APPROVED:
        return {"status": enrollment.status, "expires_at": enrollment.expires_at}
    project, _ = Project.objects.update_or_create(
        external_id=enrollment.project_external_id,
        defaults={"name": enrollment.project_name},
    )
    instance, _ = Instance.objects.update_or_create(
        project=project,
        external_id=enrollment.instance_external_id,
        defaults={"platform": enrollment.platform, "client_version": enrollment.client_version},
    )
    ReporterCredential.objects.filter(instance=instance, revoked_at__isnull=True).update(revoked_at=now)
    token = secrets.token_urlsafe(32)
    ReporterCredential.objects.create(instance=instance, token_prefix=token[:12], token_digest=token_digest(token))
    enrollment.status = Enrollment.Status.ISSUED
    enrollment.issued_instance = instance
    enrollment.save(update_fields=("status", "issued_instance"))
    return {"status": "issued", "reporter_token": token, "instance_id": instance.external_id}


@transaction.atomic
def approve_enrollment(enrollment: Enrollment, user, *, approved: bool) -> Enrollment:
    locked = Enrollment.objects.select_for_update().get(id=enrollment.id)
    now = timezone.now()
    if locked.status != Enrollment.Status.PENDING:
        raise ContractError("only pending enrollment requests can be decided")
    if locked.expires_at <= now:
        locked.status = Enrollment.Status.EXPIRED
        locked.save(update_fields=("status",))
        raise ContractError("enrollment request has expired")
    locked.status = Enrollment.Status.APPROVED if approved else Enrollment.Status.REJECTED
    locked.decided_at = now
    locked.decided_by = user
    locked.save(update_fields=("status", "decided_at", "decided_by"))
    return locked


@transaction.atomic
def ingest_report(instance: Instance, report: dict[str, Any]) -> dict[str, Any]:
    locked = Instance.objects.select_for_update().select_related("project").get(id=instance.id)
    if report["project"]["id"] != locked.project.external_id or report["instance"]["id"] != locked.external_id:
        raise ContractError("report identity does not match reporter credential")
    digest = _digest(report)
    existing = IngestReceipt.objects.filter(idempotency_key=report["idempotency_key"]).first()
    if existing:
        if existing.instance_id != locked.id or existing.payload_digest != digest:
            raise ContractError("idempotency key was reused with different content")
        return {"status": "duplicate", "sequence": existing.sequence}
    if report["sequence"] <= locked.last_sequence:
        raise ContractError("report sequence is stale")
    observed = report["observed_at"]
    previous_last_seen = locked.last_seen
    project = locked.project
    previous_inventory_digest = locked.work_inventory_digest
    inventory_digest = (
        _digest(report["work_inventory"]) if report["schema_version"] >= 2 else ""
    )
    health_state = (
        _json_safe(report["instance_health"])
        if report["schema_version"] >= 4
        else None
    )
    material_activity = (
        locked.last_sequence == 0
        or project.name != report["project"]["name"]
        or project.attention_state != report["state"]["attention_state"]
        or project.current_state
        != {key: value for key, value in report["state"].items() if key != "attention_state"}
        or bool(report["material_events"])
        or (report["schema_version"] >= 2 and inventory_digest != previous_inventory_digest)
        or (
            health_state is not None
            and _health_material_signature(health_state)
            != _health_material_signature(locked.health_state)
        )
    )
    project.name = report["project"]["name"]
    project.attention_state = report["state"]["attention_state"]
    project.current_state = {
        key: value for key, value in report["state"].items() if key != "attention_state"
    }
    project.state_schema_version = report["schema_version"]
    project.last_seen = observed
    project_fields = [
        "name",
        "attention_state",
        "current_state",
        "state_schema_version",
        "last_seen",
        "updated_at",
    ]
    if material_activity:
        project.last_activity_at = observed
        project_fields.append("last_activity_at")
    project.save(update_fields=project_fields)
    locked.platform = report["instance"]["platform"]
    locked.client_version = report["instance"]["client_version"]
    locked.counter_epoch = report["instance"]["counter_epoch"]
    locked.quiescent = report["instance"]["quiescent"]
    locked.report_schema_version = max(locked.report_schema_version, report["schema_version"])
    locked.last_sequence = report["sequence"]
    locked.last_seen = observed
    instance_fields = [
        "platform",
        "client_version",
        "counter_epoch",
        "quiescent",
        "report_schema_version",
        "last_sequence",
        "last_seen",
        "updated_at",
    ]
    if report["schema_version"] >= 2:
        inventory = report["work_inventory"]
        locked.work_inventory_sequence = report["sequence"]
        locked.work_inventory_observed_at = observed
        locked.work_inventory_digest = inventory_digest
        locked.work_inventory_total = inventory["total_count"]
        locked.work_inventory_truncated = inventory["truncated"]
        instance_fields.extend(
            (
                "work_inventory_sequence",
                "work_inventory_observed_at",
                "work_inventory_digest",
                "work_inventory_total",
                "work_inventory_truncated",
            )
        )
    if health_state is not None:
        locked.health_state = health_state
        instance_fields.append("health_state")
    locked.save(update_fields=instance_fields)
    IngestReceipt.objects.create(
        instance=locked,
        idempotency_key=report["idempotency_key"],
        sequence=report["sequence"],
        payload_digest=digest,
    )
    event_retention = timedelta(days=settings.DASHBOARD_EVENT_RETENTION_DAYS)
    MaterialEvent.objects.bulk_create(
        [
            MaterialEvent(
                project=project,
                instance=locked,
                event_kind=item["kind"],
                summary_code=item["summary_code"],
                occurred_at=item["occurred_at"],
                retained_until=item["occurred_at"] + event_retention,
            )
            for item in report["material_events"]
        ]
    )
    MaterialEvent.objects.filter(retained_until__lt=timezone.now()).delete()
    if report["schema_version"] >= 2:
        inventory = report["work_inventory"]
        WorkArtifactSnapshot.objects.filter(instance=locked).delete()
        WorkArtifactSnapshot.objects.bulk_create(
            [
                WorkArtifactSnapshot(
                    project=project,
                    instance=locked,
                    artifact_external_id=item["artifact_id"],
                    visible_id=item["visible_id"],
                    artifact_type=item["artifact_type"],
                    title=item["title"],
                    document_lifecycle=item["document_lifecycle"],
                    outcome_lifecycle=item["outcome_lifecycle"],
                    outcome_disposition=item["outcome_disposition"],
                    reconciliation_state=item["reconciliation_state"],
                    parent_ids=item["parent_ids"],
                    produces_ids=item["produces_ids"],
                    planning_position=item["planning_position"],
                    planning_order_source=item["planning_order_source"],
                    planning_readiness=item["planning_readiness"],
                    closure_status=_json_safe(item["closure_status"]),
                    source_updated_at=item["updated_at"],
                    observed_at=observed,
                    snapshot_sequence=report["sequence"],
                )
                for item in inventory["artifacts"]
            ]
        )
        LifecycleEvent.objects.bulk_create(
            [
                LifecycleEvent(
                    project=project,
                    instance=locked,
                    event_key=item["event_key"],
                    artifact_external_id=item["artifact_id"],
                    visible_id=item["visible_id"],
                    artifact_type=item["artifact_type"],
                    title=item["title"],
                    transition=item["transition"],
                    from_state=item["from_state"],
                    to_state=item["to_state"],
                    occurred_at=item["occurred_at"],
                    retained_until=item["occurred_at"] + event_retention,
                )
                for item in report["lifecycle_events"]
            ],
            ignore_conflicts=True,
        )
        LifecycleEvent.objects.filter(retained_until__lt=timezone.now()).delete()
    app = report["app_server"]
    existing_app = AppServerAggregate.objects.filter(instance=locked).first()
    app_defaults = {
        "counter_epoch": locked.counter_epoch,
        "enabled": app["enabled"],
        "availability_state": app["availability_state"],
        "attempts": app["attempts"],
        "failures": app["failures"],
        "fallbacks": app["fallbacks"],
        "last_success": app["last_success"],
        "last_failure": app["last_failure"],
        "client_version": app["client_version"],
    }
    if report["schema_version"] >= 6:
        app_defaults.update(
            {
                "readiness_observed_at": app["readiness_observed_at"],
                "performance": app["performance"],
            }
        )
    elif existing_app and existing_app.readiness_observed_at is not None:
        app_defaults = {
            "counter_epoch": locked.counter_epoch,
            "enabled": app["enabled"],
        }
    AppServerAggregate.objects.update_or_create(
        instance=locked,
        defaults=app_defaults,
    )
    failure_retention = timedelta(days=settings.DASHBOARD_FAILURE_RETENTION_DAYS)
    for item in app["failure_groups"]:
        FailureGroup.objects.update_or_create(
            instance=locked,
            signature=item["signature"],
            defaults={
                "category": item["category"],
                "count": item["count"],
                "first_seen": item["first_seen"],
                "last_seen": item["last_seen"],
                "retained_until": item["last_seen"] + failure_retention,
            },
        )
    FailureGroup.objects.filter(retained_until__lt=timezone.now()).delete()
    _sync_attention_conditions(locked, report["state"], app, observed, previous_last_seen)
    work = report["work_efficiency"]
    latest_efficiency = (
        WorkEfficiencyAggregate.objects.filter(instance=locked, counter_epoch=locked.counter_epoch)
        .order_by("-window_end")
        .first()
    )
    if latest_efficiency is None or _efficiency_signature(latest_efficiency) != _efficiency_signature(work):
        WorkEfficiencyAggregate.objects.update_or_create(
            instance=locked,
            counter_epoch=locked.counter_epoch,
            window_start=work["window_start"],
            window_end=work["window_end"],
            defaults=work,
        )
        _trim_efficiency_history(locked, locked.counter_epoch)
    return {"status": "accepted", "sequence": locked.last_sequence}
