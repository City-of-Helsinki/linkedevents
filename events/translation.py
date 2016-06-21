from modeltranslation.translator import translator, TranslationOptions
from .models import *


class LanguageTranslationOptions(TranslationOptions):
    fields = ('name',)


translator.register(Language, LanguageTranslationOptions)


class KeywordTranslationOptions(TranslationOptions):
    fields = ('name',)


translator.register(Keyword, KeywordTranslationOptions)


class KeywordSetTranslationOptions(TranslationOptions):
    fields = ('name',)


translator.register(KeywordSet, KeywordTranslationOptions)


class PlaceTranslationOptions(TranslationOptions):
    fields = ('name', 'description', 'info_url', 'street_address', 'address_locality', 'telephone')


translator.register(Place, PlaceTranslationOptions)


class EventTranslationOptions(TranslationOptions):
    fields = ('name', 'description', 'short_description', 'info_url',
              'location_extra_info', 'headline', 'secondary_headline', 'provider')


translator.register(Event, EventTranslationOptions)


class OfferTranslationOptions(TranslationOptions):
    fields = ('price', 'info_url', 'description')


translator.register(Offer, OfferTranslationOptions)


class LicenseTranslationOptions(TranslationOptions):
    fields = ('name',)


translator.register(License, LicenseTranslationOptions)
