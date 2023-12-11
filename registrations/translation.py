from modeltranslation.translator import TranslationOptions, translator

from .models import PriceGroup, Registration, SignUpPriceGroup


class RegistrationBaseTranslationOptions(TranslationOptions):
    fallback_languages = {"default": ("fi", "sv", "en")}


class RegistrationTranslationOptions(RegistrationBaseTranslationOptions):
    fields = (
        "confirmation_message",
        "instructions",
    )


translator.register(Registration, RegistrationTranslationOptions)


class PriceGroupTranslationOptions(RegistrationBaseTranslationOptions):
    fields = ("description",)


translator.register(PriceGroup, PriceGroupTranslationOptions)


class SignUpPriceGroupTranslationOptions(RegistrationBaseTranslationOptions):
    fields = ("description",)


translator.register(SignUpPriceGroup, SignUpPriceGroupTranslationOptions)
