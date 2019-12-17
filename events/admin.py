from django.conf import settings
from django.contrib import admin
from django.utils.translation import ugettext as _
from leaflet.admin import LeafletGeoAdmin
from modeltranslation.admin import TranslationAdmin
from reversion.admin import VersionAdmin
from events.api import generate_id
from events.models import Place, License, DataSource, Event, Keyword, KeywordSet, Language


class BaseAdmin(admin.ModelAdmin):
    exclude = ("created_by", "modified_by",)

    def save_model(self, request, obj, form, change):
        if obj.pk is None:
            obj.created_by = request.user
        else:
            obj.modified_by = request.user
        obj.save()


class AutoIdBaseAdmin(BaseAdmin):

    def save_model(self, request, obj, form, change):
        system_id = settings.SYSTEM_DATA_SOURCE_ID
        obj.data_source_id = system_id
        if not obj.id:
            obj.id = generate_id(system_id)
        obj.origin_id = obj.id.split(':')[1]

        super().save_model(request, obj, form, change)


class EventAdmin(AutoIdBaseAdmin, TranslationAdmin, VersionAdmin):
    # TODO: location, publisher, keyword, audience, super_event fields with autocomplete
    # TODO: only allow user_editable editable fields
    fields = ('name', 'short_description', 'description', 'location', 'location_extra_info', 'start_time', 'end_time',
              'keywords', 'audience', 'publisher', 'provider', 'provider_contact_info', 'event_status', 'super_event',
              'info_url', 'in_language')
    search_fields = ('name', 'location__name')
    list_display = ('id', 'name', 'start_time', 'end_time', 'publisher', 'location')
    list_filter = ('data_source',)
    ordering = ('-last_modified_time',)


admin.site.register(Event, EventAdmin)


class KeywordAdmin(AutoIdBaseAdmin, TranslationAdmin, VersionAdmin):
    # TODO: publisher field with autocomplete
    # TODO: only allow user_editable editable fields
    fields = ('publisher', 'deprecated', 'name')
    search_fields = ('name',)
    list_display = ('id', 'name', 'n_events')
    list_filter = ('data_source',)
    ordering = ('-n_events',)


admin.site.register(Keyword, KeywordAdmin)


class KeywordSetAdmin(BaseAdmin):
    # TODO: keywords field with autocomplete
    fields = ('data_source', 'origin_id', 'name', 'keywords', 'usage')


admin.site.register(KeywordSet, KeywordSetAdmin)


class HelsinkiGeoAdmin(LeafletGeoAdmin):
    settings_overrides = {
        'DEFAULT_CENTER': (60.171944, 24.941389),
        'DEFAULT_ZOOM': 11,
        'MIN_ZOOM': 3,
        'MAX_ZOOM': 19,
    }


class PlaceAdmin(HelsinkiGeoAdmin, AutoIdBaseAdmin, TranslationAdmin, VersionAdmin):
    # TODO: replaced_by field must be done with autocomplete, 140 000 objects a bit too much to load _:D
    # TODO: only allow user_editable editable fields
    fieldsets = (
        (None, {
            'fields': ('publisher',  'deleted', 'replaced_by', 'name', 'description', 'info_url', 'position')

        }),
        (_('Contact info'), {
            'fields': (
                'email', 'telephone', 'contact_type', 'street_address',
                'address_locality', 'address_region', 'postal_code', 'post_office_box_num')
        }),
    )
    search_fields = ('name', 'street_address')
    list_display = ('id', 'name', 'n_events', 'street_address')
    list_filter = ('data_source',)
    ordering = ('-n_events',)

    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        # use https CDN instead
        self.openlayers_url = 'https://cdnjs.cloudflare.com/ajax/libs/openlayers/2.13.1/OpenLayers.js'


admin.site.register(Place, PlaceAdmin)


class DataSourceAdmin(BaseAdmin, VersionAdmin):
    fields = ('id', 'name', 'api_key', 'owner', 'user_editable')


admin.site.register(DataSource, DataSourceAdmin)


class LanguageAdmin(BaseAdmin, VersionAdmin):
    fields = ('id', 'name')


admin.site.register(Language, LanguageAdmin)


class PersonAdmin(BaseAdmin, VersionAdmin):
    pass


class LicenseAdmin(BaseAdmin, TranslationAdmin, VersionAdmin):
    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['id']
        else:
            return []


admin.site.register(License, LicenseAdmin)
