from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib import admin

from .models import User


class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        (None, {'fields': ('department_name', 'uuid', 'admin_in_organizations', 'regular_user_in_organizations', 'private_user_in_organizations')}),
    )
    readonly_fields = ('admin_in_organizations', 'regular_user_in_organizations', 'private_user_in_organizations')

    def admin_in_organizations(self, obj):
        return ', '.join([org.name for org in obj.admin_organizations.all()])

    def regular_user_in_organizations(self, obj):
        return ', '.join([org.name for org in obj.organization_memberships.all()])

    def private_user_in_organizations(self, obj):
        return ', '.join([org.name for org in obj.public_memberships.all()])
admin.site.register(User, UserAdmin)
