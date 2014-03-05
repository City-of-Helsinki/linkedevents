from django.contrib import admin
from models import *
from modeltranslation.admin import TranslationAdmin


class EventModelAdmin(TranslationAdmin, reversion.VersionAdmin):
    pass


class EventCategoryAdmin(TranslationAdmin, reversion.VersionAdmin):
    pass


class EventLocationAdmin(TranslationAdmin, reversion.VersionAdmin):
    pass


class OrganizationAdmin(reversion.VersionAdmin):
    pass


class LanguageAdmin(TranslationAdmin, reversion.VersionAdmin):
    pass

admin.site.register(Event, EventModelAdmin)
admin.site.register(EventCategory, EventCategoryAdmin)
admin.site.register(EventLocation, EventLocationAdmin)
admin.site.register(Organization, OrganizationAdmin)
admin.site.register(Language, LanguageAdmin)
