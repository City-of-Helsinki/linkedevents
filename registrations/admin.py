from admin_auto_filters.filters import AutocompleteFilter
from django.conf import settings
from django.contrib import admin
from django.utils.translation import gettext as _
from modeltranslation.admin import TranslationAdmin
from reversion.admin import VersionAdmin

from events.admin import PublisherFilter
from events.models import Language
from registrations.forms import RegistrationPriceGroupAdminForm
from registrations.models import (
    PriceGroup,
    Registration,
    RegistrationPriceGroup,
    RegistrationUserAccess,
)


class RegistrationBaseAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        if obj.pk is None:
            obj.created_by = request.user
        else:
            obj.last_modified_by = request.user

        super().save_model(request, obj, form, change)


class EventFilter(AutocompleteFilter):
    title = _("Event")
    field_name = "event"


class RegistrationUserAccessInline(admin.TabularInline):
    model = RegistrationUserAccess
    extra = 1
    verbose_name = _("Participant list user")
    verbose_name_plural = _("Participant list users")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Allow to select only language which has service_language set to true
        if db_field.name == "language":
            kwargs["queryset"] = Language.objects.filter(service_language=True)
        return super(RegistrationUserAccessInline, self).formfield_for_foreignkey(
            db_field, request, **kwargs
        )


class RegistrationPriceGroupInline(admin.TabularInline):
    model = RegistrationPriceGroup
    form = RegistrationPriceGroupAdminForm
    extra = 1
    verbose_name = _("Registration price group")
    verbose_name_plural = _("Registration price groups")


class RegistrationAdmin(RegistrationBaseAdmin, TranslationAdmin, VersionAdmin):
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
    list_display = (
        "id",
        "event",
        "enrolment_start_time",
        "enrolment_end_time",
    )
    list_filter = (EventFilter,)
    autocomplete_fields = ("event",)
    inlines = (RegistrationUserAccessInline, RegistrationPriceGroupInline)

    def get_formsets_with_inlines(self, request, obj=None):
        for inline in self.get_inline_instances(request, obj):
            # hide RegistrationPriceGroupInline if Talpa integration is not enabled
            if (
                not isinstance(inline, RegistrationPriceGroupInline)
                or settings.WEB_STORE_INTEGRATION_ENABLED
            ):
                yield inline.get_formset(request, obj), inline

    def save_related(self, request, form, formsets, change):
        for formset in formsets:
            if formset.model == RegistrationUserAccess:
                formset.save(commit=False)

                for added_registration_user_accesses in formset.new_objects:
                    # Send invitation email if new registration user accesses is added
                    added_registration_user_accesses.send_invitation()

                for [
                    changed_registration_user_access,
                    changed_fields,
                ] in formset.changed_objects:
                    # Send invitation email if email address is changed
                    if "email" in changed_fields:
                        changed_registration_user_access.send_invitation()

        super(RegistrationAdmin, self).save_related(request, form, formsets, change)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ["id", "event"]
        else:
            return ["id"]


admin.site.register(Registration, RegistrationAdmin)


class DefaultPriceGroupListFilter(admin.EmptyFieldListFilter):
    def __init__(self, field, request, params, model, model_admin, field_path):
        super().__init__(field, request, params, model, model_admin, field_path)

        self.title = _("Is default")

    def choices(self, changelist):
        for lookup, title in (
            (None, _("All")),
            ("1", _("Yes")),
            ("0", _("No")),
        ):
            yield {
                "selected": self.lookup_val == lookup,
                "query_string": changelist.get_query_string(
                    {self.lookup_kwarg: lookup}
                ),
                "display": title,
            }


class PriceGroupAdmin(RegistrationBaseAdmin, TranslationAdmin, VersionAdmin):
    fields = (
        "id",
        "publisher",
        "description",
        "is_free",
    )
    list_display = (
        "id",
        "publisher",
        "description",
        "is_free",
        "is_default",
    )
    list_filter = (
        PublisherFilter,
        ("publisher", DefaultPriceGroupListFilter),
        ("is_free", admin.BooleanFieldListFilter),
    )
    search_fields = ("description",)

    def has_change_permission(self, request, obj=None):
        if obj and obj.publisher_id is None:
            return False

        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.publisher_id is None:
            return False

        return super().has_delete_permission(request, obj)

    @admin.display(description=_("Is default"))
    def is_default(self, obj):
        return _("Yes") if obj.publisher_id is None else _("No")

    def get_readonly_fields(self, request, obj=None):
        return ["id"]


if settings.WEB_STORE_INTEGRATION_ENABLED:
    admin.site.register(PriceGroup, PriceGroupAdmin)
