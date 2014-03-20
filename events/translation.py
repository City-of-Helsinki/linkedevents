from modeltranslation.translator import translator, TranslationOptions
from models import *


class LanguageTranslationOptions(TranslationOptions):
    fields = ('name',)


translator.register(Language, LanguageTranslationOptions)


class CategoryTranslationOptions(TranslationOptions):
    fields = ('name', 'description')


translator.register(Category, CategoryTranslationOptions)


class PlaceTranslationOptions(TranslationOptions):
    fields = ('name', 'description')


translator.register(Place, PlaceTranslationOptions)


class PostalAddressTranslationOptions(TranslationOptions):
    fields = ('street_address', 'address_locality', 'telephone')


translator.register(PostalAddress, PostalAddressTranslationOptions)


class EventTranslationOptions(TranslationOptions):
    fields = ('name', 'description', 'url')


translator.register(Event, EventTranslationOptions)


class PersonTranslationOptions(TranslationOptions):
    fields = ('name', 'description')


translator.register(Person, PersonTranslationOptions)
