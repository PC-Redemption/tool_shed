from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_id = models.UUIDField(unique=True)
    name = models.CharField(max_length=160)
    attention_state = models.CharField(max_length=32, default="unknown")
    current_state = models.JSONField(default=dict)
    state_schema_version = models.PositiveSmallIntegerField(default=1)
    last_seen = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    is_hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-last_seen", "name")

    def __str__(self) -> str:
        return self.name


class Instance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="instances")
    external_id = models.UUIDField()
    platform = models.CharField(max_length=64)
    client_version = models.CharField(max_length=64)
    report_schema_version = models.PositiveSmallIntegerField(default=1)
    last_sequence = models.PositiveBigIntegerField(default=0)
    counter_epoch = models.UUIDField(default=uuid.uuid4)
    last_seen = models.DateTimeField(null=True, blank=True)
    quiescent = models.BooleanField(default=False)
    work_inventory_sequence = models.PositiveBigIntegerField(default=0)
    work_inventory_observed_at = models.DateTimeField(null=True, blank=True)
    work_inventory_digest = models.CharField(max_length=64, blank=True)
    work_inventory_total = models.PositiveIntegerField(default=0)
    work_inventory_truncated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("project", "external_id"), name="unique_project_instance")]
        ordering = ("project__name", "external_id")

    def __str__(self) -> str:
        return f"{self.project.name} / {self.external_id}"


class Enrollment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"
        ISSUED = "issued", "Issued"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project_external_id = models.UUIDField()
    project_name = models.CharField(max_length=160)
    instance_external_id = models.UUIDField()
    platform = models.CharField(max_length=64)
    client_version = models.CharField(max_length=64)
    user_code = models.CharField(max_length=12, unique=True)
    device_secret_digest = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    requested_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    issued_instance = models.OneToOneField(Instance, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ("-requested_at",)


class ReporterCredential(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instance = models.OneToOneField(Instance, on_delete=models.CASCADE, related_name="credential")
    token_prefix = models.CharField(max_length=12, db_index=True)
    token_digest = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    rotated_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    @property
    def active(self) -> bool:
        return self.revoked_at is None


class IngestReceipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE, related_name="receipts")
    idempotency_key = models.UUIDField(unique=True)
    sequence = models.PositiveBigIntegerField()
    payload_digest = models.CharField(max_length=64)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-received_at",)


class MaterialEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="material_events")
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE, related_name="material_events")
    event_kind = models.CharField(max_length=64)
    summary_code = models.CharField(max_length=96)
    occurred_at = models.DateTimeField()
    retained_until = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-occurred_at",)


class WorkArtifactSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="work_artifacts")
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE, related_name="work_artifacts")
    artifact_external_id = models.UUIDField()
    visible_id = models.CharField(max_length=64)
    artifact_type = models.CharField(max_length=32)
    title = models.CharField(max_length=160)
    document_lifecycle = models.CharField(max_length=32)
    outcome_lifecycle = models.CharField(max_length=32, default="unknown")
    outcome_disposition = models.CharField(max_length=48, default="unknown")
    reconciliation_state = models.CharField(max_length=32, default="unknown")
    parent_ids = models.JSONField(default=list)
    produces_ids = models.JSONField(default=list)
    planning_position = models.PositiveIntegerField(null=True, blank=True)
    planning_order_source = models.CharField(max_length=24, default="not-applicable")
    planning_readiness = models.CharField(max_length=24, default="not-applicable")
    source_updated_at = models.DateTimeField()
    observed_at = models.DateTimeField()
    snapshot_sequence = models.PositiveBigIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("instance", "artifact_external_id"),
                name="unique_instance_work_artifact",
            )
        ]
        ordering = ("visible_id",)

class LifecycleEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="lifecycle_events")
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE, related_name="lifecycle_events")
    event_key = models.CharField(max_length=64)
    artifact_external_id = models.UUIDField()
    visible_id = models.CharField(max_length=64)
    artifact_type = models.CharField(max_length=32)
    title = models.CharField(max_length=160)
    transition = models.CharField(max_length=32)
    from_state = models.CharField(max_length=48)
    to_state = models.CharField(max_length=48)
    occurred_at = models.DateTimeField()
    retained_until = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("instance", "event_key"), name="unique_instance_lifecycle_event")
        ]
        ordering = ("-occurred_at", "-created_at")


class AttentionCondition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="attention_conditions")
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE, related_name="attention_conditions")
    reason_code = models.CharField(max_length=48)
    severity = models.CharField(max_length=16)
    active = models.BooleanField(default=True)
    current_count = models.PositiveIntegerField(default=1)
    first_seen = models.DateTimeField()
    last_changed = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    retained_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("instance", "reason_code"),
                condition=models.Q(active=True),
                name="unique_active_instance_attention_reason",
            )
        ]
        ordering = ("-active", "-last_changed", "reason_code")


class AppServerAggregate(models.Model):
    instance = models.OneToOneField(Instance, primary_key=True, on_delete=models.CASCADE, related_name="app_server")
    counter_epoch = models.UUIDField()
    enabled = models.BooleanField(default=False)
    availability_state = models.CharField(max_length=32, default="unknown")
    attempts = models.PositiveBigIntegerField(default=0)
    failures = models.PositiveBigIntegerField(default=0)
    fallbacks = models.PositiveBigIntegerField(default=0)
    last_success = models.DateTimeField(null=True, blank=True)
    last_failure = models.DateTimeField(null=True, blank=True)
    client_version = models.CharField(max_length=64, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class FailureGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE, related_name="failure_groups")
    signature = models.CharField(max_length=64)
    category = models.CharField(max_length=64)
    count = models.PositiveBigIntegerField(default=0)
    first_seen = models.DateTimeField()
    last_seen = models.DateTimeField()
    retained_until = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=("instance", "signature"), name="unique_instance_failure_signature")]
        ordering = ("-last_seen",)


class WorkEfficiencyAggregate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE, related_name="work_efficiency")
    counter_epoch = models.UUIDField()
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    remedial_tokens_actual = models.PositiveBigIntegerField(null=True, blank=True)
    remedial_token_coverage = models.DecimalField(max_digits=5, decimal_places=4)
    remedial_interactions = models.PositiveBigIntegerField(default=0)
    remedial_output_bytes = models.PositiveBigIntegerField(default=0)
    remedial_duration_ms = models.PositiveBigIntegerField(default=0)
    remedial_retries = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("instance", "counter_epoch", "window_start", "window_end"),
                name="unique_instance_efficiency_window",
            )
        ]
        ordering = ("-window_end",)
