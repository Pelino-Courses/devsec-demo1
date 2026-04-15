from django.contrib.auth.views import LogoutView, PasswordResetCompleteView, PasswordResetDoneView
from django.urls import path
from django.urls import reverse_lazy

from .views import (
    DashboardView,
    DocumentDownloadView,
    DocumentManageView,
    ProfileManageByIdView,
    ProfileView,
    PrivilegedPortalView,
    UserLoginView,
    UserPasswordChangeDoneView,
    UserPasswordChangeView,
    UserPasswordResetConfirmView,
    UserPasswordResetView,
    home_redirect,
    signup_view,
)

app_name = "venuste"

urlpatterns = [
    path("", home_redirect, name="home"),
    path("signup/", signup_view, name="signup"),
    path("login/", UserLoginView.as_view(), name="login"),
    path(
        "password-reset/",
        UserPasswordResetView.as_view(
            template_name="venuste/password_reset_form.html",
            email_template_name="venuste/password_reset_email.html",
            subject_template_name="venuste/password_reset_subject.txt",
            success_url=reverse_lazy("venuste:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        PasswordResetDoneView.as_view(template_name="venuste/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        UserPasswordResetConfirmView.as_view(
            template_name="venuste/password_reset_confirm.html",
            success_url=reverse_lazy("venuste:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        PasswordResetCompleteView.as_view(template_name="venuste/password_reset_complete.html"),
        name="password_reset_complete",
    ),
    path("logout/", LogoutView.as_view(next_page="venuste:login"), name="logout"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("authorization/", PrivilegedPortalView.as_view(), name="privileged_portal"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("documents/", DocumentManageView.as_view(), name="documents"),
    path("documents/<int:document_id>/download/", DocumentDownloadView.as_view(), name="document_download"),
    path("profiles/<int:profile_id>/", ProfileManageByIdView.as_view(), name="profile_manage"),
    path("password-change/", UserPasswordChangeView.as_view(), name="password_change"),
    path(
        "password-change/done/",
        UserPasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
]
