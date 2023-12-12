from admin_auto_filters.filters import AutocompleteFilter
from django.contrib import admin
from django.utils.translation import gettext as _
from reversion.admin import VersionAdmin

from events.models import Language
from registrations.models import Registration, RegistrationUserAccess


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


class RegistrationAdmin(VersionAdmin):
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
        "contact_person_mandatory_fields",
    )
    list_display = (
        "id",
        "event",
        "enrolment_start_time",
        "enrolment_end_time",
    )
    list_filter = (EventFilter,)
    autocomplete_fields = ("event",)
    inlines = (RegistrationUserAccessInline,)

    def save_model(self, request, obj, form, change):
        if obj.pk is None:
            obj.created_by = request.user
        else:
            obj.last_modified_by = request.user
        obj.save()

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
