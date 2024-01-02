from django import forms

from registrations.models import RegistrationPriceGroup


class RegistrationPriceGroupAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.id:
            self.initial["vat_percentage"] = self.instance.vat_percentage
        else:
            self.initial["vat_percentage"] = RegistrationPriceGroup.VatPercentage.VAT_24

        for field in ("price_without_vat", "vat"):
            self.fields[field].disabled = True

    class Meta:
        model = RegistrationPriceGroup
        fields = (
            "price_group",
            "price",
            "vat_percentage",
            "price_without_vat",
            "vat",
        )
