import io
import shutil
import tempfile

from django.contrib.auth.models import Group, Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from PIL import Image


@override_settings()
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
