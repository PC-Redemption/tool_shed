from django.urls import path

from . import views


app_name = "fleet"
urlpatterns = [
    path("dashboard/healthz", views.health, name="health"),
    path("api/v1/enrollment/requests", views.enrollment_request, name="enrollment-request"),
    path("api/v1/enrollment/requests/<uuid:enrollment_id>/poll", views.enrollment_poll, name="enrollment-poll"),
    path("api/v1/enrollment/requests/<uuid:enrollment_id>/decision", views.enrollment_decide, name="enrollment-decide"),
    path("api/v1/reports", views.report_ingest, name="report-ingest"),
    path("api/v1/credentials/revoke", views.reporter_revoke, name="reporter-revoke"),
    path("dashboard/", views.fleet_overview, name="overview"),
    path("dashboard/events/", views.dashboard_events, name="events"),
    path(
        "dashboard/navigation/projects/",
        views.project_navigation_preferences,
        name="project-navigation-preferences",
    ),
    path(
        "dashboard/projects/<uuid:project_id>/visibility/",
        views.project_visibility,
        name="project-visibility",
    ),
    path("dashboard/enrollments/", views.enrollments_view, name="enrollments"),
    path("dashboard/enrollments/<uuid:enrollment_id>/decision", views.enrollment_decision_ui, name="enrollment-decision-ui"),
    path("dashboard/projects/<uuid:project_id>/", views.project_detail, name="project"),
    path("dashboard/projects/<uuid:project_id>/<str:tab>/", views.project_detail, name="project-tab"),
    path("dashboard/app-server/", views.app_server_view, name="app-server"),
    path("dashboard/work-efficiency/", views.work_efficiency_view, name="work-efficiency"),
]
