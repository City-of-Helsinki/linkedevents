from modeltranslation.translator import TranslationOptions, translator

from .models import Registration


class RegistrationTranslationOptions(TranslationOptions):
    fields = (
        "confirmation_message",
        "instructions",
    )
    fallback_languages = {"default": ("fi", "sv", "en")}


translator.register(Registration, RegistrationTranslationOptions)
