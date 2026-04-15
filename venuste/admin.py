from django.contrib import admin

from .models import PasswordResetOTP, UserDocument, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "updated_at")
    search_fields = ("user__username", "user__email")


@admin.register(UserDocument)
class UserDocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "original_filename", "uploaded_at")
    search_fields = ("user__username", "title", "original_filename")
    list_filter = ("uploaded_at",)


@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "expires_at", "used")
    search_fields = ("user__username", "user__email")
    list_filter = ("used", "created_at")
    readonly_fields = ("otp_code", "created_at", "expires_at")

