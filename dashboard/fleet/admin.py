from django.contrib import admin

from .models import Enrollment, Instance, Project, ReporterCredential


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "attention_state", "last_seen")
    search_fields = ("name", "external_id")


@admin.register(Instance)
class InstanceAdmin(admin.ModelAdmin):
    list_display = ("project", "external_id", "platform", "client_version", "last_seen", "quiescent")
    list_filter = ("platform", "quiescent")


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("user_code", "project_name", "platform", "status", "requested_at", "expires_at")
    list_filter = ("status", "platform")
    readonly_fields = ("device_secret_digest",)


@admin.register(ReporterCredential)
class ReporterCredentialAdmin(admin.ModelAdmin):
    list_display = ("instance", "token_prefix", "created_at", "rotated_at", "revoked_at")
    readonly_fields = ("token_digest",)
