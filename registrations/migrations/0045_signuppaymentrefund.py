# Generated by Django 4.2.11 on 2024-04-17 13:45

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("registrations", "0044_signuppricegroup_external_order_item_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="SignUpPaymentRefund",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("deleted", models.BooleanField(default=False)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=19)),
                (
                    "created_time",
                    models.DateTimeField(auto_now_add=True, verbose_name="Created at"),
                ),
                (
                    "payment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="refunds",
                        to="registrations.signuppayment",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
