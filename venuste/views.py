from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.contrib.auth.views import LoginView, PasswordChangeDoneView, PasswordChangeView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from .forms import (
    CustomPasswordChangeForm,
    LoginForm,
    ProfileUpdateForm,
    RegistrationForm,
)
from .models import UserProfile

User = get_user_model()


def is_privileged_user(user):
    if not user.is_authenticated:
        return False
    return (
        user.is_superuser
        or user.is_staff
        or user.has_perm("venuste.access_privileged_portal")
        or user.groups.filter(name="instructors").exists()
    )


def get_accessible_profile(user, profile_id):
    profiles = UserProfile.objects.select_related("user")
    if is_privileged_user(user):
        return get_object_or_404(profiles, pk=profile_id)
    return get_object_or_404(profiles, pk=profile_id, user=user)


class UserLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "venuste/dashboard.html"
    login_url = "venuste:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_privileged_user"] = is_privileged_user(self.request.user)
        return context


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "venuste/profile.html"
    login_url = "venuste:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = kwargs.get("form") or ProfileUpdateForm(instance=self.request.user.profile)
        context["is_privileged_user"] = is_privileged_user(self.request.user)
        return context

    def post(self, request, *args, **kwargs):
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("venuste:profile")

        messages.error(request, "Please correct the profile form errors.")
        context = self.get_context_data(form=form)
        return self.render_to_response(context)


class ProfileManageByIdView(LoginRequiredMixin, TemplateView):
    template_name = "venuste/profile_manage.html"
    login_url = "venuste:login"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.target_profile = get_accessible_profile(request.user, kwargs["profile_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["target_profile"] = self.target_profile
        context["is_privileged_user"] = is_privileged_user(self.request.user)
        context["form"] = kwargs.get("form") or ProfileUpdateForm(instance=self.target_profile)
        context["is_owner"] = self.target_profile.user_id == self.request.user.id
        return context

    def post(self, request, *args, **kwargs):
        form = ProfileUpdateForm(request.POST, request.FILES, instance=self.target_profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("venuste:profile_manage", profile_id=self.target_profile.id)

        messages.error(request, "Please correct the profile form errors.")
        return self.render_to_response(self.get_context_data(form=form))


class UserPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = "venuste/password_change.html"
    form_class = CustomPasswordChangeForm
    success_url = reverse_lazy("venuste:password_change_done")


class UserPasswordChangeDoneView(LoginRequiredMixin, PasswordChangeDoneView):
    template_name = "venuste/password_change_done.html"


class PrivilegedPortalView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "venuste/privileged_portal.html"
    raise_exception = True

    def test_func(self):
        return is_privileged_user(self.request.user)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect_to_login(
                self.request.get_full_path(),
                self.get_login_url(),
                self.get_redirect_field_name(),
            )
        return UserPassesTestMixin.handle_no_permission(self)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_users"] = User.objects.count()
        context["total_staff"] = User.objects.filter(is_staff=True).count()
        context["total_superusers"] = User.objects.filter(is_superuser=True).count()
        return context


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("venuste:dashboard")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful. Welcome!")
            return redirect("venuste:dashboard")
        messages.error(request, "Please correct the errors below.")
    else:
        form = RegistrationForm()

    return render(request, "venuste/signup.html", {"form": form})


def home_redirect(request):
    if request.user.is_authenticated:
        return redirect("venuste:dashboard")
    return redirect("venuste:login")
