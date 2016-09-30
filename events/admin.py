from django.conf import settings
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.gis.db import models
from django.utils.translation import ugettext as _
from leaflet.admin import LeafletGeoAdmin
from modeltranslation.admin import TranslationAdmin
from reversion.admin import VersionAdmin
from events.api import generate_id
from events.models import Event, Keyword, Place, Language, \
    OpeningHoursSpecification, KeywordLabel, Organization, License, DataSource


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


class HelsinkiGeoAdmin(LeafletGeoAdmin):
    settings_overrides = {
        'DEFAULT_CENTER': (60.171944, 24.941389),
        'DEFAULT_ZOOM': 11,
        'MIN_ZOOM': 3,
        'MAX_ZOOM': 19,
    }


class PlaceAdmin(HelsinkiGeoAdmin, BaseAdmin, TranslationAdmin, VersionAdmin):
    fieldsets = (
        (None, {
            'fields': ('publisher', 'name', 'description', 'info_url', 'position', 'divisions', 'parent')

        }),
        (_('Contact info'), {
            'fields':  ('email', 'telephone', 'contact_type', 'street_address', 'address_locality', 'address_region',
                        'postal_code', 'post_office_box_num')
        }),
    )

    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        # use https CDN instead
        self.openlayers_url = 'https://cdnjs.cloudflare.com/ajax/libs/openlayers/2.13.1/OpenLayers.js'

    def save_model(self, request, obj, form, change):
        system_id = settings.SYSTEM_DATA_SOURCE_ID
        obj.data_source_id = system_id
        if not obj.id:
            obj.id = generate_id(system_id)
        obj.origin_id = obj.id.split(':')[1]

        super().save_model(request, obj, form, change)

admin.site.register(Place, PlaceAdmin)


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


class DataSourceAdmin(BaseAdmin):
    fields = ('id', 'name', 'api_key', 'owner')

admin.site.register(DataSource, DataSourceAdmin)


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
