# Generated by Django 3.2.22 on 2023-11-02 14:17

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0095_datasource_user_editable_registrations"),
    ]

    operations = [
        migrations.AlterField(
            model_name="event",
            name="type_id",
            field=models.PositiveSmallIntegerField(
                choices=[(1, "General"), (2, "Course"), (3, "Volunteering")],
                db_index=True,
                default=1,
            ),
        ),
    ]
