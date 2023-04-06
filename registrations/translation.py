from modeltranslation.translator import TranslationOptions, translator

from .models import MandatoryField


class MandatoryFieldTranslationOptions(TranslationOptions):
    fields = ("name",)


translator.register(MandatoryField, MandatoryFieldTranslationOptions)
