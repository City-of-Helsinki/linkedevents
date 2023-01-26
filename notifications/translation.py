from modeltranslation.translator import TranslationOptions, translator

from .models import NotificationTemplate


class NotificationTemplateTranslationOptions(TranslationOptions):
    fields = ("subject", "body", "html_body")


translator.register(NotificationTemplate, NotificationTemplateTranslationOptions)
