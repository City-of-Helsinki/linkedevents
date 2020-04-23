from django.conf import settings
from django.contrib import admin
from django.utils.translation import ugettext as _
from leaflet.admin import LeafletGeoAdmin
from modeltranslation.admin import TranslationAdmin
from reversion.admin import VersionAdmin
from admin_auto_filters.filters import AutocompleteFilter
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
            if obj.origin_id:
                obj.id = ':'.join([system_id, obj.origin_id])
            else:
                obj.id = generate_id(system_id)
        obj.origin_id = obj.id.split(':')[1]

        super().save_model(request, obj, form, change)


class PublisherFilter(AutocompleteFilter):
    title = 'Publisher'  # display title
    field_name = 'publisher'  # name of the foreign key field


class CreatedByFilter(AutocompleteFilter):
    title = 'Created by'  # display title
    field_name = 'created_by'  # name of the foreign key field


class LocationFilter(AutocompleteFilter):
    title = 'Location'  # display title
    field_name = 'location'  # name of the foreign key field


class EventAdmin(AutoIdBaseAdmin, TranslationAdmin, VersionAdmin):
    # TODO: only allow user_editable editable fields
    fields = ('id', 'data_source', 'origin_id', 'name', 'short_description', 'description', 'location',
              'location_extra_info', 'start_time', 'end_time', 'keywords', 'audience', 'publisher', 'provider',
              'provider_contact_info', 'event_status', 'super_event', 'info_url', 'in_language',
              'publication_status', 'replaced_by', 'deleted')
    search_fields = ('name', 'location__name')
    list_display = ('id', 'name', 'start_time', 'end_time', 'publisher', 'location')
    list_filter = ('data_source', PublisherFilter, CreatedByFilter, LocationFilter)
    ordering = ('-last_modified_time',)
    date_hierarchy = 'end_time'
    autocomplete_fields = ('location', 'keywords', 'audience', 'super_event', 'publisher', 'replaced_by')

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['id', 'data_source', 'origin_id']
        else:
            return ['id', 'data_source']

    class Media:
        pass


admin.site.register(Event, EventAdmin)


class KeywordAdmin(AutoIdBaseAdmin, TranslationAdmin, VersionAdmin):
    # TODO: only allow user_editable editable fields
    fields = ('id', 'data_source', 'origin_id',  'publisher', 'name', 'replaced_by', 'deprecated')
    search_fields = ('name',)
    list_display = ('id', 'name', 'n_events')
    list_filter = ('data_source',)
    ordering = ('-n_events',)
    autocomplete_fields = ('publisher', 'replaced_by')
    readonly_fields = ('id',)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['id', 'data_source', 'origin_id']
        else:
            return ['id', 'data_source']


admin.site.register(Keyword, KeywordAdmin)


class KeywordSetAdmin(AutoIdBaseAdmin):
    fields = ('id', 'data_source', 'origin_id', 'name', 'keywords', 'usage')
    autocomplete_fields = ('keywords', )

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['id', 'origin_id', 'data_source']
        else:
            return ['id', 'data_source']


admin.site.register(KeywordSet, KeywordSetAdmin)


class HelsinkiGeoAdmin(LeafletGeoAdmin):
    settings_overrides = {
        'DEFAULT_CENTER': (60.171944, 24.941389),
        'DEFAULT_ZOOM': 11,
        'MIN_ZOOM': 3,
        'MAX_ZOOM': 19,
    }


class PlaceAdmin(HelsinkiGeoAdmin, AutoIdBaseAdmin, TranslationAdmin, VersionAdmin):
    # TODO: only allow user_editable editable fields
    fieldsets = (
        (None, {
            'fields': ('id', 'data_source', 'origin_id', 'publisher',  'deleted', 'replaced_by', 'name', 'description',
                       'info_url', 'position')

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
    autocomplete_fields = ('replaced_by', 'publisher')

    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        # use https CDN instead
        self.openlayers_url = 'https://cdnjs.cloudflare.com/ajax/libs/openlayers/2.13.1/OpenLayers.js'

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['id', 'data_source', 'origin_id']
        else:
            return ['id', 'data_source']


admin.site.register(Place, PlaceAdmin)


class DataSourceAdmin(BaseAdmin, VersionAdmin):
    fields = ('id', 'name', 'api_key', 'owner', 'user_editable')
    autocomplete_fields = ('owner',)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['id']
        else:
            return []


admin.site.register(DataSource, DataSourceAdmin)


class LanguageAdmin(BaseAdmin, VersionAdmin):
    fields = ('id', 'name')

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['id']
        else:
            return []


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
