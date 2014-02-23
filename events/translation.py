from modeltranslation.translator import translator, TranslationOptions
from events.models import Language, EventCategory, EventLocation, Event


class LanguageTranslationOptions(TranslationOptions):
    fields = ('name',)
translator.register(Language, LanguageTranslationOptions)


class EventCategoryTranslationOptions(TranslationOptions):
    fields = ('name', 'description')
translator.register(EventCategory, EventCategoryTranslationOptions)


class EventLocationTranslationOptions(TranslationOptions):
    fields = ('name', 'description')
translator.register(EventLocation, EventLocationTranslationOptions)


class EventTranslationOptions(TranslationOptions):
    fields = ('name', 'description')
translator.register(Event, EventTranslationOptions)
