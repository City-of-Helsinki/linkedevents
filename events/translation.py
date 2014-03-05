from modeltranslation.translator import translator, TranslationOptions
from models import *


class LanguageTranslationOptions(TranslationOptions):
    fields = ('name',)
translator.register(Language, LanguageTranslationOptions)


class EventCategoryTranslationOptions(TranslationOptions):
    fields = ('name', 'description')
translator.register(EventCategory, EventCategoryTranslationOptions)


class PlaceTranslationOptions(TranslationOptions):
    fields = ('name', 'description')
translator.register(Place, PlaceTranslationOptions)


class EventTranslationOptions(TranslationOptions):
    fields = ('name', 'description')
translator.register(Event, EventTranslationOptions)
