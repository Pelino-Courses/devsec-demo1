from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import (
    DashboardView,
    ProfileView,
    UserLoginView,
    UserPasswordChangeDoneView,
    UserPasswordChangeView,
    home_redirect,
    signup_view,
)

app_name = "venuste"

urlpatterns = [
    path("", home_redirect, name="home"),
    path("signup/", signup_view, name="signup"),
    path("login/", UserLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="venuste:login"), name="logout"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("password-change/", UserPasswordChangeView.as_view(), name="password_change"),
    path(
        "password-change/done/",
        UserPasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
]
