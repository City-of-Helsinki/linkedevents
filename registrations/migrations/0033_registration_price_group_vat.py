# Generated by Django 3.2.23 on 2024-01-02 11:31

from decimal import ROUND_HALF_UP, Decimal

from django.db import migrations, models


def calculate_vat_and_price_without_vat(price_group):
    cents = Decimal(".01")

    price_group.price_without_vat = (
        price_group.price / (1 + price_group.vat_percentage / 100)
    ).quantize(cents, ROUND_HALF_UP)

    price_group.vat = (price_group.price - price_group.price_without_vat).quantize(
        cents, ROUND_HALF_UP
    )


def calculate_default_vat_prices_for_existing_price_groups(apps, schema_editor):
    registration_price_group_model = apps.get_model(
        "registrations", "RegistrationPriceGroup"
    )

    for price_group in registration_price_group_model.objects.all():
        calculate_vat_and_price_without_vat(price_group)
        price_group.save(update_fields=["price_without_vat", "vat"])


class Migration(migrations.Migration):
    dependencies = [
        ("registrations", "0032_alter_signuppricegroup_registration_price_group"),
    ]

    operations = [
        migrations.AddField(
            model_name="registrationpricegroup",
            name="price_without_vat",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0"), max_digits=19
            ),
        ),
        migrations.AddField(
            model_name="registrationpricegroup",
            name="vat",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0"), max_digits=19
            ),
        ),
        migrations.AddField(
            model_name="registrationpricegroup",
            name="vat_percentage",
            field=models.DecimalField(
                choices=[
                    (Decimal("25.50"), "25.5 %"),
                    (Decimal("24.00"), "24 %"),
                    (Decimal("14.00"), "14 %"),
                    (Decimal("10.00"), "10 %"),
                    (Decimal("0.00"), "0 %"),
                ],
                decimal_places=2,
                default=Decimal("0"),
                max_digits=4,
            ),
        ),
        migrations.AddField(
            model_name="signuppricegroup",
            name="price_without_vat",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0"), max_digits=19
            ),
        ),
        migrations.AddField(
            model_name="signuppricegroup",
            name="vat",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0"), max_digits=19
            ),
        ),
        migrations.AddField(
            model_name="signuppricegroup",
            name="vat_percentage",
            field=models.DecimalField(
                choices=[
                    (Decimal("25.50"), "25.5 %"),
                    (Decimal("24.00"), "24 %"),
                    (Decimal("14.00"), "14 %"),
                    (Decimal("10.00"), "10 %"),
                    (Decimal("0.00"), "0 %"),
                ],
                decimal_places=2,
                default=Decimal("0"),
                max_digits=4,
            ),
        ),
        migrations.AlterField(
            model_name="registrationpricegroup",
            name="price",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0"), max_digits=19
            ),
        ),
        migrations.AlterField(
            model_name="signuppricegroup",
            name="price",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0"), max_digits=19
            ),
        ),
        migrations.RunPython(
            calculate_default_vat_prices_for_existing_price_groups,
            migrations.RunPython.noop,
        ),
    ]
