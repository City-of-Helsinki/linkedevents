from django import forms
from django.contrib.admin.widgets import (
    FilteredSelectMultiple,
    RelatedFieldWidgetWrapper,
)
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _
from django_orghierarchy.forms import OrganizationForm


class LocalOrganizationAdminForm(OrganizationForm):
    registration_admin_users = forms.ModelMultipleChoiceField(
        get_user_model().objects.all(),
        required=False,
        help_text=_(
            "Hold down “Control”, or “Command” on a Mac, to select more than one."
        ),
        widget=FilteredSelectMultiple(
            verbose_name=_("registration admins"), is_stacked=False
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # This relation is used so that RelatedFieldWidgetWrapper
        # will get the model User from the "rel".
        rel_with_user_model = get_user_model().admin_organizations.rel

        self.fields["registration_admin_users"].widget = RelatedFieldWidgetWrapper(
            self.fields["registration_admin_users"].widget,
            rel=rel_with_user_model,
            admin_site=getattr(self, "user_admin_site", None),
            **getattr(self, "wrapper_kwargs", {}),
        )
        if self.instance.pk:
            self.initial[
                "registration_admin_users"
            ] = self.instance.registration_admin_users.all()

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
            "registration_admin_users",
            "regular_users",
            "replaced_by",
        )
