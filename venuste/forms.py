from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    UserCreationForm,
)
from django.contrib.auth.models import User
from django.utils.html import strip_tags
from PIL import Image

from .models import PasswordResetOTP, UserDocument, UserProfile
from .throttling import LoginThrottle


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email


class LoginForm(AuthenticationForm):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        username = self.data.get("username", "")
        throttle = LoginThrottle(self.request, username)

        try:
            throttle.ensure_allowed()
            cleaned_data = super().clean()
        except ValidationError:
            throttle.record_failure()
            raise

        throttle.record_success()
        return cleaned_data


class CustomPasswordChangeForm(PasswordChangeForm):
    pass


class PasswordResetForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-control"})
    )

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        return email


class OTPVerificationForm(forms.Form):
    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Enter 6-digit OTP",
            "autocomplete": "off",
        }),
        label="OTP Code",
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_otp_code(self):
        otp_code = self.cleaned_data.get("otp_code", "").strip()
        if not otp_code.isdigit() or len(otp_code) != 6:
            raise forms.ValidationError("OTP must be exactly 6 digits.")
        
        if self.user:
            try:
                otp_record = PasswordResetOTP.objects.get(user=self.user)
                if otp_record.otp_code != otp_code:
                    raise forms.ValidationError("Invalid OTP code.")
                if not otp_record.is_valid():
                    raise forms.ValidationError("OTP has expired.")
            except PasswordResetOTP.DoesNotExist:
                raise forms.ValidationError("No OTP found. Please request a new one.")
        
        return otp_code


class ProfileUpdateForm(forms.ModelForm):
    MAX_UPLOAD_SIZE = 2 * 1024 * 1024  # 2MB
    ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
    ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}

    class Meta:
        model = UserProfile
        fields = ("bio", "profile_picture")
        widgets = {
            "bio": forms.TextInput(attrs={"maxlength": 255}),
        }

    def clean_profile_picture(self):
        profile_picture = self.cleaned_data.get("profile_picture")
        if not profile_picture:
            return profile_picture

        if profile_picture.size > self.MAX_UPLOAD_SIZE:
            raise forms.ValidationError("Profile picture must be 2MB or smaller.")

        content_type = getattr(profile_picture, "content_type", "")
        if content_type and content_type.lower() not in self.ALLOWED_IMAGE_MIME_TYPES:
            raise forms.ValidationError("Only JPG, PNG, or WEBP images are allowed.")

        try:
            image = Image.open(profile_picture)
            image_format = (image.format or "").upper()
            image.verify()
            profile_picture.seek(0)
        except Exception as exc:
            raise forms.ValidationError("Upload a valid image file.") from exc

        if image_format not in self.ALLOWED_IMAGE_FORMATS:
            raise forms.ValidationError("Only JPG, PNG, or WEBP images are allowed.")

        return profile_picture

    def clean_bio(self):
        bio = self.cleaned_data.get("bio", "")
        # Store profile bio as plain text to prevent stored markup/script payloads.
        return strip_tags(bio)


class DocumentUploadForm(forms.ModelForm):
    MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB
    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "text/plain",
    }

    class Meta:
        model = UserDocument
        fields = ("title", "file")

    def clean_file(self):
        uploaded_file = self.cleaned_data.get("file")
        if not uploaded_file:
            return uploaded_file

        if uploaded_file.size > self.MAX_UPLOAD_SIZE:
            raise forms.ValidationError("Document must be 5MB or smaller.")

        FileExtensionValidator(allowed_extensions=["pdf", "txt"])(uploaded_file)

        content_type = getattr(uploaded_file, "content_type", "")
        if content_type and content_type.lower() not in self.ALLOWED_MIME_TYPES:
            raise forms.ValidationError("Only PDF and TXT documents are allowed.")

        file_head = uploaded_file.read(2048)
        uploaded_file.seek(0)
        lower_name = uploaded_file.name.lower()

        if lower_name.endswith(".pdf"):
            if not file_head.startswith(b"%PDF-"):
                raise forms.ValidationError("Invalid PDF document content.")
        elif lower_name.endswith(".txt"):
            if b"\x00" in file_head:
                raise forms.ValidationError("Invalid TXT document content.")

        return uploaded_file
