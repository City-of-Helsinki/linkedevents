from django import forms

from registrations.models import RegistrationPriceGroup


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
            self.initial["vat_percentage"] = RegistrationPriceGroup.VatPercentage.VAT_24

    class Meta:
        model = RegistrationPriceGroup
        fields = (
            "price_group",
            "price",
            "vat_percentage",
            "price_without_vat",
            "vat",
        )
