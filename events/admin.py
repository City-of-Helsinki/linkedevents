from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.gis import admin as geoadmin
from django.contrib.gis.db import models
from django.utils.translation import ugettext as _
from modeltranslation.admin import TranslationAdmin
from reversion.admin import VersionAdmin
from events.models import Event, Keyword, Place, Language, \
    OpeningHoursSpecification, KeywordLabel, Organization, License


class BaseAdmin(admin.ModelAdmin):
    exclude = ("created_by", "modified_by",)

    def save_model(self, request, obj, form, change):
        if obj.pk is None:
            obj.created_by = request.user
        else:
            obj.modified_by = request.user
        obj.save()


class EventModelAdmin(BaseAdmin, TranslationAdmin, VersionAdmin):
    pass


class KeywordAdmin(BaseAdmin, TranslationAdmin, VersionAdmin):
    pass


class PlaceAdmin(geoadmin.GeoModelAdmin, BaseAdmin, TranslationAdmin,
                 VersionAdmin):
    pass


class OrganizationAdmin(BaseAdmin):
    list_display = ('name', 'nr_org_admins')

    formfield_overrides = {
        models.ManyToManyField: {'widget': FilteredSelectMultiple("ylläpitäjät", is_stacked=False)},
    }
    fields = ('admin_users',)

    def nr_org_admins(self, obj):
        return obj.admin_users.count()
    nr_org_admins.short_description = _('Admins')

admin.site.register(Organization, OrganizationAdmin)


class LanguageAdmin(BaseAdmin, VersionAdmin):
    pass


class PersonAdmin(BaseAdmin, VersionAdmin):
    pass


class LicenseAdmin(BaseAdmin, TranslationAdmin, VersionAdmin):
    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['id']
        else:
            return []

admin.site.register(License, LicenseAdmin)
