# Generated by Django 3.2.20 on 2023-08-11 11:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("django_orghierarchy", "0011_alter_datasource_user_editable_organizations"),
        ("helevents", "0005_increase_user_model_name_field_length"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="registration_admin_organizations",
            field=models.ManyToManyField(
                blank=True,
                related_name="registration_admin_users",
                to="django_orghierarchy.Organization",
            ),
        ),
    ]