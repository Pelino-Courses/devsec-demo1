from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, PasswordChangeDoneView, PasswordChangeView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from .forms import (
    CustomPasswordChangeForm,
    LoginForm,
    ProfileUpdateForm,
    RegistrationForm,
)


class UserLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "venuste/dashboard.html"
    login_url = "venuste:login"


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "venuste/profile.html"
    login_url = "venuste:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = kwargs.get("form") or ProfileUpdateForm(instance=self.request.user.profile)
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


class UserPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = "venuste/password_change.html"
    form_class = CustomPasswordChangeForm
    success_url = reverse_lazy("venuste:password_change_done")


class UserPasswordChangeDoneView(LoginRequiredMixin, PasswordChangeDoneView):
    template_name = "venuste/password_change_done.html"


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
