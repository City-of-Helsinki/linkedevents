from modeltranslation.translator import translator, TranslationOptions
from .models import NotificationTemplate


class NotificationTemplateTranslationOptions(TranslationOptions):
    fields = ('subject', 'body', 'html_body')


translator.register(NotificationTemplate, NotificationTemplateTranslationOptions)
