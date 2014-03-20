from django.contrib import admin
from modeltranslation.admin import TranslationAdmin
import reversion
from events.models import Event, Category, Place, Offer, Organization, Language, PostalAddress, Person, \
    OpeningHoursSpecification, GeoInfo


class BaseAdmin(admin.ModelAdmin):
    exclude = ("created_by", "modified_by",)

    def save_model(self, request, obj, form, change):
        if obj.pk is None:
            obj.created_by = request.user
        else:
            obj.modified_by = request.user
        obj.save()


class EventModelAdmin(BaseAdmin, TranslationAdmin, reversion.VersionAdmin):
    pass


class CategoryAdmin(BaseAdmin, TranslationAdmin, reversion.VersionAdmin):
    pass


class PlaceAdmin(BaseAdmin, TranslationAdmin, reversion.VersionAdmin):
    pass


class OfferAdmin(BaseAdmin):
    pass


class OrganizationAdmin(BaseAdmin, reversion.VersionAdmin):
    pass


class LanguageAdmin(BaseAdmin, reversion.VersionAdmin):
    pass


class PersonAdmin(BaseAdmin, reversion.VersionAdmin):
    pass


admin.site.register(Event, EventModelAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Place, PlaceAdmin)
admin.site.register(Offer, OfferAdmin)
admin.site.register(Organization, OrganizationAdmin)
admin.site.register(Language, LanguageAdmin)
admin.site.register(Person, PersonAdmin)
admin.site.register(PostalAddress)
admin.site.register(OpeningHoursSpecification)
admin.site.register(GeoInfo)
