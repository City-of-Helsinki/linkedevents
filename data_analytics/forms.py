from django import forms
from django.utils.translation import gettext_lazy as _
from knox import crypto

from data_analytics.models import DataAnalyticsApiToken


class DataAnalyticsApiTokenAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "name" in self.fields:
            self.fields["name"].label = _("Unique name")

        if "digest" in self.fields:
            self.fields["digest"].label = _("API token")

            if not self.instance.digest:
                self.initial["digest"] = crypto.create_token_string()
                self.fields["digest"].widget.attrs["readonly"] = True
                self.fields["digest"].help_text = _(
                    "NOTE: Copy this to a secure location and use it as "
                    "the API key in the data analytics system."
                )

    class Meta:
        model = DataAnalyticsApiToken
        fields = (
            "name",
            "digest",
            "user",
            "expiry",
        )
