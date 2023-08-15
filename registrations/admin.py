from admin_auto_filters.filters import AutocompleteFilter
from django.contrib import admin
from django.utils.translation import gettext as _
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

    def has_add_permission(self, request):
        has_default_perms = super().has_add_permission(request)

        if request.user.is_superuser:
            return has_default_perms

        is_registration_admin = request.user.registration_admin_organizations.exists()

        return has_default_perms and is_registration_admin

    def has_change_permission(self, request, obj=None):
        has_default_perms = super().has_change_permission(request, obj)

        if request.user.is_superuser:
            return has_default_perms

        if obj:
            is_registration_admin = obj.can_be_edited_by(request.user)
        else:
            is_registration_admin = (
                request.user.registration_admin_organizations.exists()
            )

        return has_default_perms and is_registration_admin

    def has_delete_permission(self, request, obj=None):
        has_default_perms = super().has_delete_permission(request, obj)

        if request.user.is_superuser:
            return has_default_perms

        if obj:
            is_registration_admin = obj.can_be_edited_by(request.user)
        else:
            is_registration_admin = (
                request.user.registration_admin_organizations.exists()
            )

        return has_default_perms and is_registration_admin

    def has_view_permission(self, request, obj=None):
        has_default_perms = super().has_view_permission(request, obj)
        if request.user.is_superuser:
            return has_default_perms

        if obj:
            is_registration_admin = (
                obj.can_be_edited_by(request.user)
                or obj.created_by_id == request.user.id
            )
        else:
            is_registration_admin = (
                request.user.registration_admin_organizations.exists()
            )

        return has_default_perms and is_registration_admin

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
