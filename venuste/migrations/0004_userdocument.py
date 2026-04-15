import venuste.models
import django.core.validators
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("venuste", "0003_alter_userprofile_options"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=120)),
                ("original_filename", models.CharField(max_length=255)),
                (
                    "file",
                    models.FileField(
                        storage=venuste.models.PrivateMediaStorage(),
                        upload_to=venuste.models.user_document_upload_to,
                        validators=[django.core.validators.FileExtensionValidator(allowed_extensions=["pdf", "txt"])],
                    ),
                ),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-uploaded_at"]},
        ),
    ]
