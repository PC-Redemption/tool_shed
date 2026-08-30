from django.conf import settings
from django.contrib import admin
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django_otp.admin import OTPAdminSite
from django_otp.forms import OTPAuthenticationForm


if settings.DASHBOARD_AUTH_MODE == "local-mfa":
    admin.site.__class__ = OTPAdminSite


class DashboardLoginView(auth_views.LoginView):
    template_name = "registration/login.html"

    def get_form_class(self):
        if settings.DASHBOARD_AUTH_MODE == "local-mfa":
            return OTPAuthenticationForm
        return AuthenticationForm


urlpatterns = [
    path("dashboard/admin/", admin.site.urls),
    path("dashboard/login/", DashboardLoginView.as_view(), name="login"),
    path("dashboard/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("dashboard.fleet.urls")),
]
