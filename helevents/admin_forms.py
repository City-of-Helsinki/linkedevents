from django import forms
from django.contrib.admin.widgets import (
    FilteredSelectMultiple,
    RelatedFieldWidgetWrapper,
)
from django.utils.translation import gettext as _
from django_orghierarchy.forms import OrganizationForm

from helevents.models import User


class LocalOrganizationForm(OrganizationForm):
    registration_admins = forms.ModelMultipleChoiceField(
        User.objects.none(), required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["registration_admins"] = forms.ModelMultipleChoiceField(
            User.objects.all(),
            required=False,
            help_text=_(
                "Hold down “Control”, or “Command” on a Mac, to select more than one."
            ),
            widget=RelatedFieldWidgetWrapper(
                FilteredSelectMultiple(
                    verbose_name=_("registration admins"), is_stacked=False
                ),
                rel=User.admin_organizations.rel,
                admin_site=self.user_admin_site,
                **self.wrapper_kwargs,
            ),
        )
        if self.instance.pk:
            self.initial[
                "registration_admins"
            ] = self.instance.registration_admins.all()

    class Meta(OrganizationForm.Meta):
        fields = (
            "data_source",
            "origin_id",
            "classification",
            "name",
            "founding_date",
            "dissolution_date",
            "internal_type",
            "parent",
            "admin_users",
            "registration_admins",
            "regular_users",
            "replaced_by",
        )
