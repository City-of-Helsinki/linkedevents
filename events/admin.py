from django.contrib import admin
from models import *
from modeltranslation.admin import TranslationAdmin


class EventModelAdmin(TranslationAdmin, reversion.VersionAdmin):
    pass


class CategoryAdmin(TranslationAdmin, reversion.VersionAdmin):
    pass


class PlaceAdmin(TranslationAdmin, reversion.VersionAdmin):
    pass


class OrganizationAdmin(reversion.VersionAdmin):
    pass


class LanguageAdmin(reversion.VersionAdmin):
    pass

admin.site.register(Event, EventModelAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Place, PlaceAdmin)
admin.site.register(Offer)
admin.site.register(Organization, OrganizationAdmin)
admin.site.register(Language, LanguageAdmin)
