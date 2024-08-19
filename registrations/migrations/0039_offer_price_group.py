# Generated by Django 3.2.23 on 2024-03-08 14:41

from decimal import Decimal
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0098_datasource_user_editable_registration_price_groups"),
        ("registrations", "0038_soft_deletable_registrations_models"),
    ]

    operations = [
        migrations.CreateModel(
            name="OfferPriceGroup",
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
                (
                    "price",
                    models.DecimalField(
                        decimal_places=2, default=Decimal("0"), max_digits=19
                    ),
                ),
                (
                    "price_without_vat",
                    models.DecimalField(
                        decimal_places=2, default=Decimal("0"), max_digits=19
                    ),
                ),
                (
                    "vat_percentage",
                    models.DecimalField(
                        choices=[
                            (Decimal("25.50"), "25.5 %"),
                            (Decimal("24.00"), "24 %"),
                            (Decimal("14.00"), "14 %"),
                            (Decimal("10.00"), "10 %"),
                            (Decimal("0.00"), "0 %"),
                        ],
                        decimal_places=2,
                        default=Decimal("0.00"),
                        max_digits=4,
                    ),
                ),
                (
                    "vat",
                    models.DecimalField(
                        decimal_places=2, default=Decimal("0"), max_digits=19
                    ),
                ),
                (
                    "offer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="offer_price_groups",
                        to="events.offer",
                    ),
                ),
                (
                    "price_group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="offer_price_groups",
                        to="registrations.pricegroup",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="offerpricegroup",
            constraint=models.UniqueConstraint(
                fields=("offer", "price_group"), name="unique_offer_price_group"
            ),
        ),
    ]
