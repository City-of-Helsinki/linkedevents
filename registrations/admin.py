from admin_auto_filters.filters import AutocompleteFilter
from django.contrib import admin
from django.utils.translation import ugettext as _
from modeltranslation.admin import TranslationAdmin
from reversion.admin import VersionAdmin

import registrations.translation  # noqa: F401
from registrations.models import MandatoryField, Registration


class BaseAdmin(admin.ModelAdmin):
    exclude = (
        "created_by",
        "last_modified_by",
    )

    def save_model(self, request, obj, form, change):
        if obj.pk is None:
            obj.created_by = request.user
        else:
            obj.last_modified_by = request.user
        obj.save()


class MandatoryFieldAdmin(TranslationAdmin, VersionAdmin):
    fields = (
        "id",
        "name",
        "type",
    )
    search_fields = ("name", "id")
    list_display = ("id", "name", "type")

    def has_delete_permission(self, request, obj=None):
        if obj:
            # Don't allow to delete default mandatory fields
            default_mandatory_fields = [
                item[0] for item in MandatoryField.DEFAULT_MANDATORY_FIELDS
            ]
            return not default_mandatory_fields.__contains__(obj.id)
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ["id"]
        else:
            return []


admin.site.register(MandatoryField, MandatoryFieldAdmin)


class EventFilter(AutocompleteFilter):
    title = _("Event")
    field_name = "event"


class RegistrationAdmin(BaseAdmin, VersionAdmin):
    fields = (
        "id",
        "event",
        "enrolment_start_time",
        "enrolment_end_time",
        "minimum_attendee_capacity",
        "maximum_attendee_capacity",
        "waiting_list_capacity",
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

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ["id", "event"]
        else:
            return ["id"]


admin.site.register(Registration, RegistrationAdmin)
