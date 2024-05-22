from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext as _
from django_orghierarchy.admin import OrganizationAdmin
from django_orghierarchy.models import Organization

from registrations.models import WebStoreAccount, WebStoreMerchant

from .forms import LocalOrganizationAdminForm
from .models import User


class WebStoreMerchantInline(admin.StackedInline):
    model = WebStoreMerchant
    extra = 0
    min_num = 0
    verbose_name = _("Merchant")
    verbose_name_plural = _("Merchants")

    def has_delete_permission(self, request, obj=None):
        # A merchant cannot be deleted from Talpa so we only want
        # to allow making a merchant inactive in Linked Events.
        return False

    def get_readonly_fields(self, request, obj=None):
        return ["created_by", "last_modified_by", "merchant_id"]


class WebStoreAccountInline(admin.StackedInline):
    model = WebStoreAccount
    extra = 0
    min_num = 0
    verbose_name = _("Account")
    verbose_name_plural = _("Accounts")

    def has_delete_permission(self, request, obj=None):
        # An account cannot be deleted from Talpa so we only want
        # to allow making an account inactive in Linked Events.
        return False

    def get_readonly_fields(self, request, obj=None):
        return ["created_by", "last_modified_by"]


class LocalOrganizationAdmin(OrganizationAdmin):
    filter_horizontal = ("admin_users", "regular_users")
    form = LocalOrganizationAdminForm
    inlines = (WebStoreMerchantInline, WebStoreAccountInline)

    def get_formsets_with_inlines(self, request, obj=None):
        for inline in self.get_inline_instances(request, obj):
            # Hide WebStoreMerchantInline and WebStoreAccountInline
            # if Talpa integration is not enabled.
            if (
                not (
                    isinstance(inline, WebStoreMerchantInline)
                    or isinstance(inline, WebStoreAccountInline)
                )
                or settings.WEB_STORE_INTEGRATION_ENABLED
            ):
                yield inline.get_formset(request, obj), inline

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)

        user_model = get_user_model()
        user_modeladmin = self.admin_site._registry.get(user_model)
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

    def save_related(self, request, form, formsets, change):
        for formset in formsets:
            if formset.model in (WebStoreMerchant, WebStoreAccount):
                formset.save(commit=False)

                for added_object in formset.new_objects:
                    added_object.created_by = request.user
                    added_object.last_modified_by = request.user

                for changed_object, __ in formset.changed_objects:
                    changed_object.last_modified_by = request.user

        super().save_related(request, form, formsets, change)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        registration_admin_users = form.cleaned_data.get("registration_admin_users", [])
        obj.registration_admin_users.set(registration_admin_users)

        financial_admin_users = form.cleaned_data.get("financial_admin_users", [])
        obj.financial_admin_users.set(financial_admin_users)


class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            None,
            {
                "fields": (
                    "department_name",
                    "uuid",
                    "admin_in_organizations",
                    "registration_admin_in_organizations",
                    "regular_user_in_organizations",
                )
            },
        ),
    )
    readonly_fields = (
        "admin_in_organizations",
        "registration_admin_in_organizations",
        "regular_user_in_organizations",
    )

    def admin_in_organizations(self, obj):
        return ", ".join([org.name for org in obj.admin_organizations.all()])

    def registration_admin_in_organizations(self, obj):
        return ", ".join(
            [org.name for org in obj.registration_admin_organizations.all()]
        )

    def regular_user_in_organizations(self, obj):
        return ", ".join([org.name for org in obj.organization_memberships.all()])


admin.site.unregister(Organization)
admin.site.register(Organization, LocalOrganizationAdmin)


admin.site.register(User, UserAdmin)
