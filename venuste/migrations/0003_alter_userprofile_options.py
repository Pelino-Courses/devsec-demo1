from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("venuste", "0002_userprofile_profile_picture"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="userprofile",
            options={
                "permissions": [
                    (
                        "access_privileged_portal",
                        "Can access privileged authorization portal",
                    )
                ]
            },
        ),
    ]
