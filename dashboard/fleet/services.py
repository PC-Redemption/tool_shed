from __future__ import annotations

import hashlib
import json
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
    Enrollment,
    FailureGroup,
    IngestReceipt,
    Instance,
    LifecycleEvent,
    MaterialEvent,
    Project,
    ReporterCredential,
    WorkEfficiencyAggregate,
    WorkArtifactSnapshot,
)


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


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


def distinct_efficiency_aggregates(*, limit: int = 200) -> list[WorkEfficiencyAggregate]:
    """Return metric changes, hiding repeated sliding-window snapshots."""
    result: list[WorkEfficiencyAggregate] = []
    latest_by_instance: dict[tuple[object, object], tuple[object, ...]] = {}
    rows = WorkEfficiencyAggregate.objects.select_related("instance", "instance__project")[: max(limit * 10, limit)]
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
    project = locked.project
    project.name = report["project"]["name"]
    project.attention_state = report["state"].pop("attention_state")
    project.current_state = report["state"]
    project.state_schema_version = report["schema_version"]
    project.last_seen = observed
    project.save(update_fields=("name", "attention_state", "current_state", "state_schema_version", "last_seen", "updated_at"))
    locked.platform = report["instance"]["platform"]
    locked.client_version = report["instance"]["client_version"]
    locked.counter_epoch = report["instance"]["counter_epoch"]
    locked.quiescent = report["instance"]["quiescent"]
    locked.report_schema_version = report["schema_version"]
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
    if report["schema_version"] == 2:
        inventory = report["work_inventory"]
        locked.work_inventory_sequence = report["sequence"]
        locked.work_inventory_observed_at = observed
        locked.work_inventory_digest = _digest(inventory)
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
    if report["schema_version"] == 2:
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
    AppServerAggregate.objects.update_or_create(
        instance=locked,
        defaults={
            "counter_epoch": locked.counter_epoch,
            "enabled": app["enabled"],
            "availability_state": app["availability_state"],
            "attempts": app["attempts"],
            "failures": app["failures"],
            "fallbacks": app["fallbacks"],
            "last_success": app["last_success"],
            "last_failure": app["last_failure"],
            "client_version": app["client_version"],
        },
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
    return {"status": "accepted", "sequence": locked.last_sequence}
