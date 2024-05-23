from decimal import Decimal

from django import forms
from django.conf import settings
from django.utils.translation import gettext as _

from registrations.enums import VatPercentage
from registrations.models import (
    Registration,
    RegistrationPriceGroup,
    RegistrationWebStoreAccount,
    RegistrationWebStoreMerchant,
    VAT_PERCENTAGES,
)

_PRODUCT_MAPPING_FIELDS = (
    "name",
    "company_code",
    "main_ledger_account",
    "balance_profit_center",
    "internal_order",
    "profit_center",
    "project",
    "operation_area",
)


class RegistrationWebStoreMerchantAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["external_merchant_id"].required = False

        if self.instance.pk and self.instance.merchant_id:
            self.initial["external_merchant_id"] = self.instance.merchant.merchant_id

    def has_changed(self):
        return (
            super().has_changed()
            or self.instance.pk
            and self.instance.merchant_id
            and self.instance.external_merchant_id != self.instance.merchant.merchant_id
        )

    def clean(self):
        cleaned_data = super().clean()

        if merchant := cleaned_data.get("merchant"):
            cleaned_data["external_merchant_id"] = merchant.merchant_id

        return cleaned_data

    class Meta:
        model = RegistrationWebStoreMerchant
        fields = (
            "registration",
            "merchant",
            "external_merchant_id",
        )
        widgets = {
            "external_merchant_id": forms.HiddenInput(),
        }


class AccountSelectField(forms.Select):
    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        option = super().create_option(
            name, value, label, selected, index, subindex, attrs
        )

        if value:
            for field in _PRODUCT_MAPPING_FIELDS:
                option["attrs"][f"data-{field}"] = getattr(value.instance, field, "")

        return option


class RegistrationWebStoreAccountAdminForm(forms.ModelForm):
    class Meta:
        model = RegistrationWebStoreAccount

        fields = (
            "registration",
            "account",
        )
        fields += _PRODUCT_MAPPING_FIELDS

        help_texts = {
            "account": _("Account values can be overwritten with the fields below."),
        }

        widgets = {
            "account": AccountSelectField(),
            "name": forms.HiddenInput(),
        }

    class Media:
        js = ("js/set_account_fields.js",)


class RegistrationAdminForm(forms.ModelForm):
    vat_percentage = forms.TypedChoiceField(
        choices=VAT_PERCENTAGES,
        initial=VatPercentage.VAT_24.value,
        coerce=Decimal,
        label=_("VAT percentage for price groups"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not settings.WEB_STORE_INTEGRATION_ENABLED:
            if "vat_percentage" in self.fields:
                del self.fields["vat_percentage"]
        elif self.instance.pk and self.instance.registration_price_groups.exists():
            self.initial["vat_percentage"] = (
                self.instance.registration_price_groups.first().vat_percentage
            )

    class Meta:
        model = Registration
        fields = (
            "id",
            "event",
            "enrolment_start_time",
            "enrolment_end_time",
            "minimum_attendee_capacity",
            "maximum_attendee_capacity",
            "waiting_list_capacity",
            "maximum_group_size",
            "instructions",
            "confirmation_message",
            "audience_min_age",
            "audience_max_age",
            "mandatory_fields",
        )
        if settings.WEB_STORE_INTEGRATION_ENABLED:
            fields += ("vat_percentage",)


class RegistrationPriceGroupAdminForm(forms.ModelForm):
    price = forms.DecimalField(
        required=False, max_digits=19, decimal_places=2, min_value=0
    )
    price_without_vat = forms.DecimalField(
        required=False, disabled=True, max_digits=19, decimal_places=2, min_value=0
    )
    vat = forms.DecimalField(
        required=False, disabled=True, max_digits=19, decimal_places=2, min_value=0
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.id:
            self.initial["vat_percentage"] = self.instance.vat_percentage
        else:
            self.fields["vat_percentage"].choices = [(None, "")] + self.fields[
                "vat_percentage"
            ].choices
            self.initial["vat_percentage"] = None

        self.fields["vat_percentage"].disabled = True
        self.fields["vat_percentage"].required = False

    def has_changed(self):
        return True

    class Meta:
        model = RegistrationPriceGroup
        fields = (
            "price_group",
            "price",
            "vat_percentage",
            "price_without_vat",
            "vat",
        )
