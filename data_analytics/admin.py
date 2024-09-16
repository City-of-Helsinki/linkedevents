from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils import timezone
from knox import crypto
from knox.models import AuthToken
from knox.settings import CONSTANTS, knox_settings

from data_analytics.forms import DataAnalyticsApiTokenAdminForm
from data_analytics.models import DataAnalyticsApiToken

user_model = get_user_model()


class DataAnalyticsApiTokenAdmin(admin.ModelAdmin):
    list_display = ("name", "username", "created", "expiry")
    form = DataAnalyticsApiTokenAdminForm

    def username(self, obj):
        return obj.user.username

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = ["user", "created", "expiry"]

        if obj and obj.digest:
            readonly_fields.append("digest")

        return readonly_fields

    def save_model(self, request, obj, form, change):
        if not change:
            user = user_model.objects.create()
            token = form.cleaned_data["digest"]
            digest = crypto.hash_token(token)

            expiry = None
            if knox_settings.TOKEN_TTL:
                expiry = timezone.now() + knox_settings.TOKEN_TTL

            obj.digest = digest
            obj.token_key = token[: CONSTANTS.TOKEN_KEY_LENGTH]
            obj.user = user
            obj.expiry = expiry

        obj.save()


admin.site.unregister(AuthToken)
admin.site.register(DataAnalyticsApiToken, DataAnalyticsApiTokenAdmin)
