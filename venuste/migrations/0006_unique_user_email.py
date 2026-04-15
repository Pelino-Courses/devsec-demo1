from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("venuste", "0005_passwordresetotp"),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE UNIQUE INDEX IF NOT EXISTS auth_user_email_unique ON auth_user(email);",
            reverse_sql="DROP INDEX IF EXISTS auth_user_email_unique;",
        ),
    ]
