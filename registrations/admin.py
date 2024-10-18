from admin_auto_filters.filters import AutocompleteFilter
from django.conf import settings
from django.contrib import admin
from django.db import transaction
from django.utils.translation import gettext as _
from modeltranslation.admin import TranslationAdmin
from reversion.admin import VersionAdmin

from events.admin import PublisherFilter
from events.models import Language
from registrations.forms import (
    RegistrationAdminForm,
    RegistrationPriceGroupAdminForm,
    RegistrationWebStoreAccountAdminForm,
    RegistrationWebStoreMerchantAdminForm,
)
from registrations.models import (
    VAT_CODE_MAPPING,
    PriceGroup,
    Registration,
    RegistrationPriceGroup,
    RegistrationUserAccess,
    RegistrationWebStoreAccount,
    RegistrationWebStoreMerchant,
    RegistrationWebStoreProductMapping,
)


class RegistrationBaseAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        if obj.pk is None:
            obj.created_by = request.user
        else:
            obj.last_modified_by = request.user

        super().save_model(request, obj, form, change)


class RegistrationWebStoreMerchantAndAccountBaseAdmin(admin.StackedInline):
    extra = 1
    min_num = 0
    max_num = 1

    def has_delete_permission(self, request, obj=None):
        return (
            super().has_delete_permission(request, obj)
            and getattr(obj, "web_store_product_mapping", None) is None
        )


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
    extra = 0
    verbose_name = _("Registration price group")
    verbose_name_plural = _("Registration price groups")


class RegistrationWebStoreMerchantInline(
    RegistrationWebStoreMerchantAndAccountBaseAdmin
):
    model = RegistrationWebStoreMerchant
    form = RegistrationWebStoreMerchantAdminForm
    verbose_name = _("Merchant")
    verbose_name_plural = _("Merchants")


class RegistrationWebStoreAccountInline(
    RegistrationWebStoreMerchantAndAccountBaseAdmin
):
    model = RegistrationWebStoreAccount
    form = RegistrationWebStoreAccountAdminForm
    verbose_name = _("Account")
    verbose_name_plural = _("Accounts")


class RegistrationAdmin(RegistrationBaseAdmin, TranslationAdmin, VersionAdmin):
    form = RegistrationAdminForm
    list_display = (
        "id",
        "event",
        "enrolment_start_time",
        "enrolment_end_time",
    )
    list_filter = (EventFilter,)
    autocomplete_fields = ("event",)
    inlines = (
        RegistrationUserAccessInline,
        RegistrationPriceGroupInline,
        RegistrationWebStoreMerchantInline,
        RegistrationWebStoreAccountInline,
    )

    def get_formsets_with_inlines(self, request, obj=None):
        for inline in self.get_inline_instances(request, obj):
            # hide Talpa-related inline forms if Talpa integration is not enabled
            if settings.WEB_STORE_INTEGRATION_ENABLED or not any(
                [
                    isinstance(inline, RegistrationPriceGroupInline),
                    isinstance(inline, RegistrationWebStoreMerchantInline),
                    isinstance(inline, RegistrationWebStoreAccountInline),
                ]
            ):
                yield inline.get_formset(request, obj), inline

    def save_formset(self, request, form, formset, change):
        if (
            settings.WEB_STORE_INTEGRATION_ENABLED
            and formset.model == RegistrationPriceGroup
        ):
            instances = formset.save(commit=False)

            for obj in formset.deleted_objects:
                obj.delete()

            for instance in instances:
                instance.vat_percentage = form.cleaned_data["vat_percentage"]
                instance.save()
        else:
            super().save_formset(request, form, formset, change)

    @transaction.atomic
    def save_related(self, request, form, formsets, change):
        merchant_or_account_changed = False
        if settings.WEB_STORE_INTEGRATION_ENABLED:
            for formset in formsets:
                if (
                    formset.model
                    in (RegistrationWebStoreMerchant, RegistrationWebStoreAccount)
                    and formset.has_changed()
                ):
                    merchant_or_account_changed = True
                    break

        super().save_related(request, form, formsets, change)

        if (
            settings.WEB_STORE_INTEGRATION_ENABLED
            and getattr(form.instance, "registration_merchant", None)
            and getattr(form.instance, "registration_account", None)
            and (
                not RegistrationWebStoreProductMapping.objects.filter(
                    registration=form.instance,
                    vat_code=VAT_CODE_MAPPING[form.cleaned_data["vat_percentage"]],
                ).exists()
                or merchant_or_account_changed
            )
        ):
            form.instance.create_or_update_web_store_product_mapping_and_accounting()

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
