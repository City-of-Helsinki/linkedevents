from admin_auto_filters.filters import AutocompleteFilter
from django.contrib import admin
from django.utils.translation import ugettext as _
from reversion.admin import VersionAdmin

from registrations.models import Registration


class EventFilter(AutocompleteFilter):
    title = _("Event")
    field_name = "event"


class RegistrationAdmin(VersionAdmin):
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

    def save_model(self, request, obj, form, change):
        if obj.pk is None:
            obj.created_by = request.user
        else:
            obj.last_modified_by = request.user
        obj.save()

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ["id", "event"]
        else:
            return ["id"]


admin.site.register(Registration, RegistrationAdmin)
