from modeltranslation.translator import TranslationOptions, translator

from .models import Registration


class RegistrationTranslationOptions(TranslationOptions):
    fields = (
        "confirmation_message",
        "instructions",
    )


translator.register(Registration, RegistrationTranslationOptions)
