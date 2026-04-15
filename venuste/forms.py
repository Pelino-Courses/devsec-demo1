from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    UserCreationForm,
)
from django.contrib.auth.models import User
from django.utils.html import strip_tags
from PIL import Image

from .models import UserProfile
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


class ProfileUpdateForm(forms.ModelForm):
    MAX_UPLOAD_SIZE = 2 * 1024 * 1024  # 2MB

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

        try:
            image = Image.open(profile_picture)
            image.verify()
            profile_picture.seek(0)
        except Exception as exc:
            raise forms.ValidationError("Upload a valid image file.") from exc

        return profile_picture

    def clean_bio(self):
        bio = self.cleaned_data.get("bio", "")
        # Store profile bio as plain text to prevent stored markup/script payloads.
        return strip_tags(bio)
