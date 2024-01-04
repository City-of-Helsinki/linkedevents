from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_orghierarchy", "0011_alter_datasource_user_editable_organizations"),
        ("helevents", "0007_user_financial_admin_organizations"),
    ]

    operations = [
        migrations.CreateModel(
            name="SerializablePublisher",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("django_orghierarchy.organization", models.Model),
        ),
    ]
