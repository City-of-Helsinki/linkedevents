# Generated by Django 3.2.20 on 2023-09-20 12:44

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("registrations", "0022_signup_group"),
    ]

    operations = [
        migrations.RenameField(
            model_name="registration",
            old_name="created_at",
            new_name="created_time",
        ),
        migrations.RenameField(
            model_name="registration",
            old_name="last_modified_at",
            new_name="last_modified_time",
        ),
        migrations.RenameField(
            model_name="signup",
            old_name="created_at",
            new_name="created_time",
        ),
        migrations.RenameField(
            model_name="signup",
            old_name="last_modified_at",
            new_name="last_modified_time",
        ),
        migrations.RenameField(
            model_name="signupgroup",
            old_name="created_at",
            new_name="created_time",
        ),
        migrations.RenameField(
            model_name="signupgroup",
            old_name="last_modified_at",
            new_name="last_modified_time",
        ),
    ]
