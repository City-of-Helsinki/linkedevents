from modeltranslation.translator import translator, TranslationOptions
from .models import *


class LanguageTranslationOptions(TranslationOptions):
    fields = ('name',)


translator.register(Language, LanguageTranslationOptions)


class CategoryTranslationOptions(TranslationOptions):
    fields = ('name', 'description')


translator.register(Category, CategoryTranslationOptions)


class PlaceTranslationOptions(TranslationOptions):
    fields = ('name', 'description', 'street_address', 'address_locality', 'telephone')


translator.register(Place, PlaceTranslationOptions)


class EventTranslationOptions(TranslationOptions):
    fields = ('name', 'description', 'url', 'location_extra_info')


translator.register(Event, EventTranslationOptions)
