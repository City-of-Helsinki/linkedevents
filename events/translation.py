from modeltranslation.translator import translator, TranslationOptions
from .models import Language, Keyword, KeywordSet, Place, Event, Offer, License, Video, Image


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
              'location_extra_info', 'headline', 'secondary_headline', 'provider',
              'provider_contact_info')


translator.register(Event, EventTranslationOptions)


class OfferTranslationOptions(TranslationOptions):
    fields = ('price', 'info_url', 'description')


translator.register(Offer, OfferTranslationOptions)


class LicenseTranslationOptions(TranslationOptions):
    fields = ('name',)


translator.register(License, LicenseTranslationOptions)


class VideoTranslationOptions(TranslationOptions):
    fields = ('name', 'alt_text')


translator.register(Video, VideoTranslationOptions)


class ImageTranslationOptions(TranslationOptions):
    fields = ('alt_text', 'name')

translator.register(Image, ImageTranslationOptions)
