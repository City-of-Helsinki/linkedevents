from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.gis import admin as geoadmin
from django.contrib.gis.db import models
from modeltranslation.admin import TranslationAdmin
from reversion.admin import VersionAdmin
from events.models import Event, Keyword, Place, Language, \
    OpeningHoursSpecification, KeywordLabel, Organization


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

    formfield_overrides = {
        models.ManyToManyField: {'widget': FilteredSelectMultiple("ylläpitäjät", is_stacked=False)},
    }
    fields = ('admin_users',)
admin.site.register(Organization, OrganizationAdmin)


class LanguageAdmin(BaseAdmin, VersionAdmin):
    pass


class PersonAdmin(BaseAdmin, VersionAdmin):
    pass
