# Generated by Django 3.2.19 on 2023-08-09 09:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("registrations", "0017_created_modified_info_to_signup"),
    ]

    operations = [
        migrations.RenameField(
            model_name="signup",
            old_name="name",
            new_name="first_name",
        ),
        migrations.AlterField(
            model_name="signup",
            name="first_name",
            field=models.CharField(
                blank=True,
                default=None,
                max_length=50,
                null=True,
                verbose_name="First name",
            ),
        ),
        migrations.AddField(
            model_name="signup",
            name="last_name",
            field=models.CharField(
                blank=True,
                default=None,
                max_length=50,
                null=True,
                verbose_name="Last name",
            ),
        ),
    ]