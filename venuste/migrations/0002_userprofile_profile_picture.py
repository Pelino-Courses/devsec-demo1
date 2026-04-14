import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("venuste", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="profile_picture",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="profile_pictures/",
                validators=[
                    django.core.validators.FileExtensionValidator(
                        allowed_extensions=["jpg", "jpeg", "png", "webp"]
                    )
                ],
            ),
        ),
    ]
