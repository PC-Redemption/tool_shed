from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django_otp.admin import OTPAdminSite
from django_otp.forms import OTPAuthenticationForm


admin.site.__class__ = OTPAdminSite


urlpatterns = [
    path("dashboard/admin/", admin.site.urls),
    path(
        "dashboard/login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            authentication_form=OTPAuthenticationForm,
        ),
        name="login",
    ),
    path("dashboard/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("dashboard.fleet.urls")),
]
