import io
import json
import shutil
import tempfile
import re
from unittest.mock import patch

from django.core.cache import cache
from django.contrib.auth.models import Group, Permission, User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.test import override_settings
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from PIL import Image


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AuthenticationFlowTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._temp_media_root = tempfile.mkdtemp()
        cls._override = override_settings(MEDIA_ROOT=cls._temp_media_root)
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        shutil.rmtree(cls._temp_media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="existinguser",
            email="existing@example.com",
            password="StrongPass123!",
        )

    def _build_test_image(self, name="avatar.png", fmt="PNG"):
        image_stream = io.BytesIO()
        image = Image.new("RGB", (10, 10), color="#4f46e5")
        image.save(image_stream, format=fmt)
        image_stream.seek(0)
        return SimpleUploadedFile(name, image_stream.read(), content_type="image/png")

    def test_registration_success(self):
        response = self.client.post(
            reverse("venuste:signup"),
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "password1": "NewStrongPass123!",
                "password2": "NewStrongPass123!",
            },
            follow=True,
        )
        self.assertTrue(User.objects.filter(username="newuser").exists())
        self.assertRedirects(response, reverse("venuste:dashboard"))

    def test_registration_redirects_to_safe_internal_next_target(self):
        response = self.client.post(
            reverse("venuste:signup"),
            {
                "username": "newuser2",
                "email": "newuser2@example.com",
                "password1": "NewStrongPass123!",
                "password2": "NewStrongPass123!",
                "next": reverse("venuste:profile"),
            },
            follow=True,
        )
        self.assertTrue(User.objects.filter(username="newuser2").exists())
        self.assertRedirects(response, reverse("venuste:profile"))

    def test_registration_rejects_external_next_target(self):
        response = self.client.post(
            reverse("venuste:signup"),
            {
                "username": "newuser3",
                "email": "newuser3@example.com",
                "password1": "NewStrongPass123!",
                "password2": "NewStrongPass123!",
                "next": "https://evil.example/phish",
            },
            follow=True,
        )
        self.assertTrue(User.objects.filter(username="newuser3").exists())
        self.assertRedirects(response, reverse("venuste:dashboard"))

    def test_registration_failure_duplicate_user(self):
        response = self.client.post(
            reverse("venuste:signup"),
            {
                "username": "existinguser",
                "email": "other@example.com",
                "password1": "NewStrongPass123!",
                "password2": "NewStrongPass123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A user with that username already exists")

    def test_login_success(self):
        response = self.client.post(
            reverse("venuste:login"),
            {
                "username": "existinguser",
                "password": "StrongPass123!",
            },
            follow=True,
        )
        self.assertRedirects(response, reverse("venuste:dashboard"))

    def test_login_redirects_to_safe_internal_next_target(self):
        response = self.client.post(
            reverse("venuste:login"),
            {
                "username": "existinguser",
                "password": "StrongPass123!",
                "next": reverse("venuste:profile"),
            },
            follow=True,
        )
        self.assertRedirects(response, reverse("venuste:profile"))

    def test_login_rejects_external_next_target(self):
        response = self.client.post(
            reverse("venuste:login"),
            {
                "username": "existinguser",
                "password": "StrongPass123!",
                "next": "https://evil.example/phish",
            },
            follow=True,
        )
        self.assertRedirects(response, reverse("venuste:dashboard"))

    def test_login_failure(self):
        response = self.client.post(
            reverse("venuste:login"),
            {
                "username": "existinguser",
                "password": "WrongPass123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a correct username and password")

    def test_login_lockout_after_repeated_failures(self):
        lockout_client = Client()

        for _ in range(5):
            response = lockout_client.post(
                reverse("venuste:login"),
                {
                    "username": "existinguser",
                    "password": "WrongPass123!",
                },
            )
            self.assertEqual(response.status_code, 200)

        locked_response = lockout_client.post(
            reverse("venuste:login"),
            {
                "username": "existinguser",
                "password": "StrongPass123!",
            },
        )
        self.assertEqual(locked_response.status_code, 200)
        self.assertContains(
            locked_response,
            "Too many failed login attempts. Try again in 15 minutes.",
        )
        self.assertFalse(lockout_client.session.get("_auth_user_id"))

    def test_login_lockout_expires_after_cooldown(self):
        lockout_client = Client()

        for _ in range(5):
            lockout_client.post(
                reverse("venuste:login"),
                {
                    "username": "existinguser",
                    "password": "WrongPass123!",
                },
            )

        with patch("venuste.throttling.timezone.now") as mocked_now:
            import datetime

            mocked_now.return_value = datetime.datetime(2026, 4, 14, 12, 0, tzinfo=datetime.timezone.utc)
            cache_key_prefix = "login-throttle:account:existinguser"
            state = cache.get(cache_key_prefix)
            self.assertIsNotNone(state)
            mocked_now.return_value = state["locked_until"] + datetime.timedelta(seconds=1)

            response = lockout_client.post(
                reverse("venuste:login"),
                {
                    "username": "existinguser",
                    "password": "StrongPass123!",
                },
                follow=True,
            )

        self.assertRedirects(response, reverse("venuste:dashboard"))
        self.assertTrue(lockout_client.session.get("_auth_user_id"))

    def test_dashboard_requires_authentication(self):
        response = self.client.get(reverse("venuste:dashboard"))
        login_url = reverse("venuste:login")
        self.assertEqual(response.status_code, 302)
        self.assertIn(login_url, response.url)

    def test_password_change_success(self):
        self.client.login(username="existinguser", password="StrongPass123!")
        response = self.client.post(
            reverse("venuste:password_change"),
            {
                "old_password": "StrongPass123!",
                "new_password1": "UpdatedStrongPass123!",
                "new_password2": "UpdatedStrongPass123!",
            },
            follow=True,
        )
        self.assertRedirects(response, reverse("venuste:password_change_done"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("UpdatedStrongPass123!"))

    def test_profile_picture_upload_success(self):
        self.client.login(username="existinguser", password="StrongPass123!")
        image_file = self._build_test_image()

        response = self.client.post(
            reverse("venuste:profile"),
            {
                "bio": "Security-focused developer",
                "profile_picture": image_file,
            },
            follow=True,
        )

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Profile updated successfully.")
        self.assertTrue(bool(self.user.profile.profile_picture))

    def test_profile_picture_upload_rejects_invalid_image(self):
        self.client.login(username="existinguser", password="StrongPass123!")
        fake_image = SimpleUploadedFile(
            "fake.jpg",
            b"not an image",
            content_type="image/jpeg",
        )

        response = self.client.post(
            reverse("venuste:profile"),
            {
                "bio": "Attempt invalid upload",
                "profile_picture": fake_image,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload a valid image")

    def test_anonymous_user_redirected_from_privileged_portal(self):
        response = self.client.get(reverse("venuste:privileged_portal"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("venuste:login"), response.url)

    def test_logout_redirects_to_safe_internal_next_target(self):
        self.client.login(username="existinguser", password="StrongPass123!")
        response = self.client.post(
            reverse("venuste:logout"),
            {"next": reverse("venuste:signup")},
            follow=True,
        )
        self.assertRedirects(response, reverse("venuste:signup"))

    def test_logout_rejects_external_next_target(self):
        self.client.login(username="existinguser", password="StrongPass123!")
        response = self.client.post(
            reverse("venuste:logout"),
            {"next": "https://evil.example/phish"},
            follow=True,
        )
        self.assertRedirects(response, reverse("venuste:login"))

    def test_standard_authenticated_user_denied_privileged_portal(self):
        self.client.login(username="existinguser", password="StrongPass123!")
        response = self.client.get(reverse("venuste:privileged_portal"))
        self.assertEqual(response.status_code, 403)

    def test_staff_user_allowed_privileged_portal(self):
        staff_user = User.objects.create_user(
            username="staffer",
            email="staff@example.com",
            password="StrongPass123!",
            is_staff=True,
        )
        self.client.login(username="staffer", password="StrongPass123!")
        response = self.client.get(reverse("venuste:privileged_portal"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Authorization Portal")
        staff_user.delete()

    def test_instructor_group_user_allowed_privileged_portal(self):
        instructor_user = User.objects.create_user(
            username="instructor",
            email="instructor@example.com",
            password="StrongPass123!",
        )
        instructors, _ = Group.objects.get_or_create(name="instructors")
        permission = Permission.objects.get(codename="access_privileged_portal")
        instructors.permissions.add(permission)
        instructor_user.groups.add(instructors)

        self.client.login(username="instructor", password="StrongPass123!")
        response = self.client.get(reverse("venuste:privileged_portal"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Authorization Portal")
        instructor_user.delete()

    def test_owner_can_access_profile_by_id(self):
        self.client.login(username="existinguser", password="StrongPass123!")
        response = self.client.get(
            reverse("venuste:profile_manage", kwargs={"profile_id": self.user.profile.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Secure Profile Management")

    def test_owner_can_update_profile_by_id(self):
        self.client.login(username="existinguser", password="StrongPass123!")
        response = self.client.post(
            reverse("venuste:profile_manage", kwargs={"profile_id": self.user.profile.id}),
            {
                "bio": "Owner-updated bio",
            },
            follow=True,
        )
        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.profile.bio, "Owner-updated bio")

    def test_standard_user_cannot_view_other_profile_by_id(self):
        other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="StrongPass123!",
        )
        self.client.login(username="existinguser", password="StrongPass123!")
        response = self.client.get(
            reverse("venuste:profile_manage", kwargs={"profile_id": other_user.profile.id})
        )
        self.assertEqual(response.status_code, 404)
        other_user.delete()

    def test_standard_user_cannot_modify_other_profile_by_id(self):
        other_user = User.objects.create_user(
            username="otheruser2",
            email="other2@example.com",
            password="StrongPass123!",
        )
        self.client.login(username="existinguser", password="StrongPass123!")
        response = self.client.post(
            reverse("venuste:profile_manage", kwargs={"profile_id": other_user.profile.id}),
            {
                "bio": "Malicious overwrite attempt",
            },
        )
        other_user.refresh_from_db()
        self.assertEqual(response.status_code, 404)
        self.assertNotEqual(other_user.profile.bio, "Malicious overwrite attempt")
        other_user.delete()

    def test_staff_user_can_access_other_profile_by_id(self):
        other_user = User.objects.create_user(
            username="otheruser3",
            email="other3@example.com",
            password="StrongPass123!",
        )
        staff_user = User.objects.create_user(
            username="staffidor",
            email="staffidor@example.com",
            password="StrongPass123!",
            is_staff=True,
        )
        self.client.login(username="staffidor", password="StrongPass123!")
        response = self.client.get(
            reverse("venuste:profile_manage", kwargs={"profile_id": other_user.profile.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, other_user.username)
        staff_user.delete()
        other_user.delete()

    def test_anonymous_redirected_from_profile_by_id(self):
        response = self.client.get(
            reverse("venuste:profile_manage", kwargs={"profile_id": self.user.profile.id})
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("venuste:login"), response.url)

    def test_password_reset_request_sends_email_for_existing_user(self):
        mail.outbox.clear()
        response = self.client.post(
            reverse("venuste:password_reset"),
            {"email": "existing@example.com"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "If an account exists")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Venuste password reset instructions", mail.outbox[0].subject)

    def test_password_reset_request_does_not_enumerate_missing_user(self):
        mail.outbox.clear()
        response = self.client.post(
            reverse("venuste:password_reset"),
            {"email": "missing@example.com"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "If an account exists")
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_confirm_invalid_token_is_rejected_safely(self):
        response = self.client.get(
            reverse(
                "venuste:password_reset_confirm",
                kwargs={"uidb64": "invalid", "token": "invalid-token"},
            ),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid or Expired Link")

    def test_password_reset_confirm_updates_password(self):
        mail.outbox.clear()
        response = self.client.post(
            reverse("venuste:password_reset"),
            {"email": "existing@example.com"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

        email_body = mail.outbox[0].body
        match = re.search(r"http://testserver(?P<path>/reset/.+/)", email_body)
        self.assertIsNotNone(match)
        reset_path = match.group("path")

        form_response = self.client.get(reset_path, follow=True)
        self.assertEqual(form_response.status_code, 200)
        confirm_path = form_response.request["PATH_INFO"]

        reset_response = self.client.post(
            confirm_path,
            {
                "new_password1": "ResetStrongPass123!",
                "new_password2": "ResetStrongPass123!",
            },
            follow=True,
        )

        self.user.refresh_from_db()
        self.assertEqual(reset_response.status_code, 200)
        self.assertContains(reset_response, "Password Updated")
        self.assertTrue(self.user.check_password("ResetStrongPass123!"))

    def test_password_reset_confirm_rejects_password_mismatch(self):
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        form_response = self.client.get(
            reverse(
                "venuste:password_reset_confirm",
                kwargs={"uidb64": uidb64, "token": token},
            ),
            follow=True,
        )
        confirm_path = form_response.request["PATH_INFO"]
        response = self.client.post(
            confirm_path,
            {
                "new_password1": "ResetStrongPass123!",
                "new_password2": "DifferentStrongPass123!",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The two password fields didn’t match")

    def test_profile_update_rejects_missing_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.login(username="existinguser", password="StrongPass123!")
        response = csrf_client.post(
            reverse("venuste:profile"),
            {
                "bio": "CSRF attack attempt",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_profile_update_accepts_valid_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.login(username="existinguser", password="StrongPass123!")
        csrf_client.get(reverse("venuste:profile"))
        csrf_token = csrf_client.cookies["csrftoken"].value

        response = csrf_client.post(
            reverse("venuste:profile"),
            {
                "bio": "CSRF-safe update",
                "csrfmiddlewaretoken": csrf_token,
            },
        )
        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.user.profile.bio, "CSRF-safe update")

    def test_password_reset_request_rejects_missing_csrf_token(self):
        mail.outbox.clear()
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(
            reverse("venuste:password_reset"),
            {"email": "existing@example.com"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_request_accepts_valid_csrf_token(self):
        mail.outbox.clear()
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.get(reverse("venuste:password_reset"))
        csrf_token = csrf_client.cookies["csrftoken"].value
        response = csrf_client.post(
            reverse("venuste:password_reset"),
            {
                "email": "existing@example.com",
                "csrfmiddlewaretoken": csrf_token,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "If an account exists")
        self.assertEqual(len(mail.outbox), 1)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AuditLoggingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="audituser",
            email="audit@example.com",
            password="StrongPass123!",
        )

    def _parse_log_payloads(self, output_lines):
        payloads = []
        for line in output_lines:
            _, _, json_blob = line.split(":", 2)
            payloads.append(json.loads(json_blob))
        return payloads

    def test_registration_logs_security_event_without_password(self):
        raw_password = "VeryStrongPass123!"
        with self.assertLogs("venuste.security", level="INFO") as captured:
            response = self.client.post(
                reverse("venuste:signup"),
                {
                    "username": "auditregistered",
                    "email": "auditregistered@example.com",
                    "password1": raw_password,
                    "password2": raw_password,
                },
            )

        self.assertEqual(response.status_code, 302)
        serialized_output = "\n".join(captured.output)
        self.assertIn("auth.registration", serialized_output)
        self.assertNotIn(raw_password, serialized_output)

    def test_login_failure_logs_denied_event_without_password(self):
        raw_password = "WrongPass123!"
        with self.assertLogs("venuste.security", level="INFO") as captured:
            response = self.client.post(
                reverse("venuste:login"),
                {"username": "audituser", "password": raw_password},
            )

        self.assertEqual(response.status_code, 200)
        serialized_output = "\n".join(captured.output)
        self.assertIn("auth.login.failure", serialized_output)
        self.assertIn('"outcome": "denied"', serialized_output)
        self.assertNotIn(raw_password, serialized_output)

    def test_logout_logs_security_event(self):
        self.client.login(username="audituser", password="StrongPass123!")

        with self.assertLogs("venuste.security", level="INFO") as captured:
            response = self.client.post(reverse("venuste:logout"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("auth.logout", "\n".join(captured.output))

    def test_password_change_logs_security_event(self):
        self.client.login(username="audituser", password="StrongPass123!")

        with self.assertLogs("venuste.security", level="INFO") as captured:
            response = self.client.post(
                reverse("venuste:password_change"),
                {
                    "old_password": "StrongPass123!",
                    "new_password1": "UpdatedStrongPass123!",
                    "new_password2": "UpdatedStrongPass123!",
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertIn("auth.password.change", "\n".join(captured.output))

    def test_password_reset_request_logs_fingerprinted_identifier(self):
        with self.assertLogs("venuste.security", level="INFO") as captured:
            response = self.client.post(
                reverse("venuste:password_reset"),
                {"email": "audit@example.com"},
            )

        self.assertEqual(response.status_code, 302)
        serialized_output = "\n".join(captured.output)
        self.assertIn("auth.password.reset.requested", serialized_output)
        self.assertIn("email_fingerprint", serialized_output)
        self.assertNotIn("audit@example.com", serialized_output)

    def test_privilege_flag_change_logs_event(self):
        with self.assertLogs("venuste.security", level="INFO") as captured:
            self.user.is_staff = True
            self.user.save()

        payloads = self._parse_log_payloads(captured.output)
        flag_change_payloads = [
            item for item in payloads if item.get("event") == "auth.privilege.user_flags_changed"
        ]
        self.assertTrue(flag_change_payloads)
        self.assertEqual(
            flag_change_payloads[0]["details"]["changes"]["is_staff"]["new"],
            True,
        )

    def test_user_group_membership_change_logs_event(self):
        instructors, _ = Group.objects.get_or_create(name="instructors")

        with self.assertLogs("venuste.security", level="INFO") as captured:
            self.user.groups.add(instructors)

        serialized_output = "\n".join(captured.output)
        self.assertIn("auth.privilege.user_groups_changed", serialized_output)
        self.assertIn("instructors", serialized_output)
