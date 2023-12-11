from modeltranslation.translator import TranslationOptions, translator

from .models import Registration, RegistrationPriceGroup, SignUpPriceGroup


class RegistrationBaseTranslationOptions(TranslationOptions):
    fallback_languages = {"default": ("fi", "sv", "en")}


class RegistrationTranslationOptions(RegistrationBaseTranslationOptions):
    fields = (
        "confirmation_message",
        "instructions",
    )


translator.register(Registration, RegistrationTranslationOptions)


class RegistrationPriceGroupTranslationOptions(RegistrationBaseTranslationOptions):
    fields = ("description",)


translator.register(RegistrationPriceGroup, RegistrationPriceGroupTranslationOptions)


class SignUpPriceGroupTranslationOptions(RegistrationBaseTranslationOptions):
    fields = ("description",)


translator.register(SignUpPriceGroup, RegistrationPriceGroupTranslationOptions)
