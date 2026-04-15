from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.contrib.auth.views import (
    LoginView,
    PasswordChangeDoneView,
    PasswordChangeView,
)
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_protect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView

from .audit import fingerprint, log_security_event
from .forms import (
    CustomPasswordChangeForm,
    DocumentUploadForm,
    LoginForm,
    PasswordResetOTPSetForm,
    PasswordResetForm,
    ProfileUpdateForm,
    RegistrationForm,
)
from .models import PasswordResetOTP, UserDocument, UserProfile
from .throttling import PasswordResetThrottle

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


def get_safe_redirect_target(request, default_url):
    redirect_to = request.POST.get("next") or request.GET.get("next")
    if redirect_to and url_has_allowed_host_and_scheme(
        url=redirect_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect_to
    return resolve_url(default_url)


def get_requested_redirect_target(request):
    redirect_to = request.POST.get("next") or request.GET.get("next")
    if redirect_to and url_has_allowed_host_and_scheme(
        url=redirect_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect_to
    return ""


class UserLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return get_safe_redirect_target(self.request, settings.LOGIN_REDIRECT_URL)


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "venuste/dashboard.html"
    login_url = "venuste:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_privileged_user"] = is_privileged_user(self.request.user)
        return context


@method_decorator(csrf_protect, name="dispatch")
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


@method_decorator(csrf_protect, name="dispatch")
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

    def form_valid(self, form):
        response = super().form_valid(form)
        log_security_event(
            "auth.password.change",
            request=self.request,
            actor=self.request.user,
            target=self.request.user,
        )
        return response


class UserPasswordChangeDoneView(LoginRequiredMixin, PasswordChangeDoneView):
    template_name = "venuste/password_change_done.html"


class UserPasswordResetView(TemplateView):
    template_name = "venuste/password_reset_form.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("venuste:dashboard")
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        form = PasswordResetForm(request.POST)
        if not form.is_valid():
            context = {"form": form}
            return self.render_to_response(context)

        username_value = form.cleaned_data["username"]
        email_value = form.cleaned_data["email"]

        throttle = PasswordResetThrottle(request, email_value)
        try:
            throttle.ensure_allowed()
        except ValidationError:
            log_security_event(
                "auth.password.reset.requested",
                request=request,
                outcome="denied",
                details={
                    "reason": "throttled",
                    "email_fingerprint": fingerprint(email_value),
                },
            )
            messages.info(request, "If an account exists with the details provided, we have sent secure reset instructions.")
            return redirect("venuste:password_reset_done")

        matched_users = User.objects.filter(
            username__iexact=username_value,
            email__iexact=email_value,
        ).order_by("id")
        user = matched_users.first()

        if user is None:
            log_security_event(
                "auth.password.reset.requested",
                request=request,
                outcome="user_not_found",
                details={
                    "email_fingerprint": fingerprint(email_value),
                    "username_fingerprint": fingerprint(username_value),
                },
            )
            messages.info(request, "If an account exists with the details provided, we have sent secure reset instructions.")
            return redirect("venuste:password_reset_done")

        duplicate_count = matched_users.count()
        if duplicate_count > 1:
            log_security_event(
                "auth.password.reset.requested",
                request=request,
                outcome="accepted_duplicate_email",
                details={
                    "email_fingerprint": fingerprint(email_value),
                    "username_fingerprint": fingerprint(username_value),
                    "matched_users": duplicate_count,
                    "selected_user_id": user.id,
                },
            )

        throttle.record_attempt()

        otp_code = PasswordResetOTP.generate_otp()
        expires_at = timezone.now() + timezone.timedelta(minutes=10)

        PasswordResetOTP.objects.update_or_create(
            user=user,
            defaults={
                "otp_code": otp_code,
                "expires_at": expires_at,
                "used": False,
            },
        )

        try:
            send_mail(
                subject="Venuste Password Reset - Your OTP Code",
                message=f"""Hello {user.username},

You requested a password reset for your Venuste account.

Your one-time password (OTP) is: {otp_code}

This code will expire in 10 minutes. If you did not request this, you can safely ignore this email.

Thanks,
Venuste Security Team""",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception as exc:
            log_security_event(
                "auth.password.reset.requested",
                request=request,
                outcome="email_send_failed",
                details={
                    "email_fingerprint": fingerprint(email_value),
                    "error": str(exc),
                },
            )
            messages.error(request, "Failed to send reset email. Please try again.")
            return self.render_to_response({"form": form})

        log_security_event(
            "auth.password.reset.requested",
            request=request,
            outcome="accepted",
            details={
                "email_fingerprint": fingerprint(email_value),
                "username_fingerprint": fingerprint(username_value),
            },
        )

        request.session["password_reset_email"] = user.email
        request.session["password_reset_user_id"] = user.id
        messages.success(request, "OTP sent to your email. Please check your inbox.")
        return redirect("venuste:password_reset_confirm")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = PasswordResetForm()
        return context


class PasswordResetConfirmView(TemplateView):
    template_name = "venuste/password_reset_confirm.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("venuste:dashboard")
        if "password_reset_user_id" not in request.session:
            messages.warning(request, "Please request a password reset first.")
            return redirect("venuste:password_reset")
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        user_id = request.session.get("password_reset_user_id")
        if not user_id:
            messages.warning(request, "Please request a password reset first.")
            return redirect("venuste:password_reset")

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, "User not found. Please try again.")
            return redirect("venuste:password_reset")

        form = PasswordResetOTPSetForm(request.POST, user=user)
        if not form.is_valid():
            context = {"form": form}
            return self.render_to_response(context)

        user.set_password(form.cleaned_data["new_password1"])
        user.save(update_fields=["password"])

        try:
            otp_record = PasswordResetOTP.objects.get(user=user)
            otp_record.used = True
            otp_record.save()
        except PasswordResetOTP.DoesNotExist:
            pass

        del request.session["password_reset_email"]
        del request.session["password_reset_user_id"]

        log_security_event(
            "auth.password.reset.completed",
            request=request,
            actor=user,
            target=user,
        )

        messages.success(request, "Password has been reset successfully. Please log in.")
        return redirect("venuste:login")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_id = self.request.session.get("password_reset_user_id")
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                user = None
        context["form"] = kwargs.get("form") or PasswordResetOTPSetForm(user=user)
        return context


class DocumentManageView(LoginRequiredMixin, TemplateView):
    template_name = "venuste/document_manage.html"
    login_url = "venuste:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = kwargs.get("form") or DocumentUploadForm()
        context["documents"] = UserDocument.objects.filter(user=self.request.user)
        return context

    def post(self, request, *args, **kwargs):
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.user = request.user
            document.original_filename = document.file.name
            document.save()
            log_security_event(
                "upload.document.success",
                request=request,
                actor=request.user,
                target=request.user,
                details={"document_id": document.id, "file_name": document.file.name},
            )
            messages.success(request, "Document uploaded successfully.")
            return redirect("venuste:documents")

        messages.error(request, "Please correct the document upload errors.")
        return self.render_to_response(self.get_context_data(form=form))


class DocumentDownloadView(LoginRequiredMixin, View):
    login_url = "venuste:login"

    def get(self, request, document_id):
        documents = UserDocument.objects.select_related("user")
        if is_privileged_user(request.user):
            document = get_object_or_404(documents, pk=document_id)
        else:
            document = get_object_or_404(documents, pk=document_id, user=request.user)

        response = FileResponse(
            document.file.open("rb"),
            as_attachment=True,
            filename=document.original_filename,
        )
        response["X-Content-Type-Options"] = "nosniff"
        log_security_event(
            "upload.document.download",
            request=request,
            actor=request.user,
            target=document.user,
            details={"document_id": document.id},
        )
        return response


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


@csrf_protect
def signup_view(request):
    if request.user.is_authenticated:
        return redirect("venuste:dashboard")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            log_security_event("auth.registration", request=request, actor=user, target=user)
            messages.success(request, "Registration successful. Welcome!")
            return redirect(get_safe_redirect_target(request, "venuste:dashboard"))
        messages.error(request, "Please correct the errors below.")
    else:
        form = RegistrationForm()

    return render(
        request,
        "venuste/signup.html",
        {
            "form": form,
            "next": get_requested_redirect_target(request),
        },
    )


def home_redirect(request):
    if request.user.is_authenticated:
        return redirect("venuste:dashboard")
    return redirect("venuste:login")
