from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django_orghierarchy.admin import OrganizationAdmin
from django_orghierarchy.models import Organization

from .forms import LocalOrganizationForm
from .models import User


class LocalOrganizationAdmin(OrganizationAdmin):
    filter_horizontal = ("admin_users", "registration_admins", "regular_users")
    form = LocalOrganizationForm

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)

        user_modeladmin = self.admin_site._registry.get(User)
        wrapper_kwargs = {}
        if user_modeladmin:
            wrapper_kwargs.update(
                can_add_related=user_modeladmin.has_add_permission(request),
                can_change_related=user_modeladmin.has_change_permission(request),
                can_delete_related=user_modeladmin.has_delete_permission(request),
                can_view_related=user_modeladmin.has_view_permission(request),
            )

        form.user_admin_site = user_modeladmin.admin_site
        form.wrapper_kwargs = wrapper_kwargs

        return form

    def save_model(self, request, obj, form, change):
        registration_admins = form.cleaned_data.get("registration_admins")
        obj.registration_admins.clear()
        if registration_admins:
            obj.registration_admins.add(*registration_admins)
        super().save_model(request, obj, form, change)


class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            None,
            {
                "fields": (
                    "department_name",
                    "uuid",
                    "admin_in_organizations",
                    "regular_user_in_organizations",
                )
            },
        ),
    )
    readonly_fields = ("admin_in_organizations", "regular_user_in_organizations")

    def admin_in_organizations(self, obj):
        return ", ".join([org.name for org in obj.admin_organizations.all()])

    def regular_user_in_organizations(self, obj):
        return ", ".join([org.name for org in obj.organization_memberships.all()])


admin.site.unregister(Organization)
admin.site.register(Organization, LocalOrganizationAdmin)

admin.site.register(User, UserAdmin)
